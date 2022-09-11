import collections.abc
import importlib.abc
import importlib.machinery
import importlib.util
import itertools
import logging
import os
import pathlib
import sys
import traceback
import typing as t
from logging import Logger
from types import TracebackType
from typing import Any, Iterable, Optional, Tuple, Union

from hades import constants

# Force-load all config options
# noinspection PyUnresolvedReferences
from . import options
from .base import (
    Compute,
    ConfigError,
    ConfigOptionError,
    OptionMeta,
    is_option_name,
)

CONFIG_PACKAGE_NAME = 'hades_config'
DEFAULT_CONFIG = os.path.join(constants.pkgsysconfdir, 'config', '__init__.py')

logger = logging.getLogger(__name__)


class AttributeAccessibleDict(dict):
    """
    A dictionary whose contents can also be accessed by attribute lookup.
    """
    __slots__ = ()

    def __getattr__(self, item):
        try:
            return self.__getitem__(item)
        except KeyError:
            raise AttributeError("'{}' object has no attribute '{}'"
                                 .format(type(self).__name__, item)) from None

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __delattr__(self, item):
        try:
            self.__delitem__(item)
        except KeyError:
            raise AttributeError("'{}' object has no attribute '{}'"
                                 .format(type(self).__name__, item)) from None

    def __dir__(self):
        attributes = list(super().__dir__())
        self_attributes = set(attributes)
        attributes.extend(attribute for attribute in self.keys()
                          if attribute not in self_attributes)
        return attributes


class Config(collections.abc.Mapping):
    """
    Config object that allows dict-style and attribute-style access to an
    underlying dictionary and optionally verifies the options that are accessed.
    """
    __slots__ = ('_config', '_runtime_checks',)

    def __init__(self, config: AttributeAccessibleDict, *,
                 runtime_checks: bool = True):
        super().__init__()
        object.__setattr__(self, '_config', config)
        object.__setattr__(self, '_runtime_checks', runtime_checks)

    def __getattr__(self, item):
        value = getattr(self._config, item)
        self._verify(item, value)
        return value

    def __getitem__(self, key):
        if isinstance(key, OptionMeta):
            key = key.__name__
        value = self._config[key]
        self._verify(key, value)
        return value

    def _verify(self, key, value):
        option = OptionMeta.options.get(key)
        if option:
            option.check_option(self._config, value, self._runtime_checks)

    def __dir__(self):
        attributes = list(super().__dir__())
        self_attributes = set(attributes)
        attributes.extend(attribute for attribute in dir(self._config)
                          if attribute not in self_attributes)
        return attributes

    def __len__(self):
        return len(self._config)

    def __contains__(self, x):
        if isinstance(x, OptionMeta):
            key = x.__name__
        return x in self._config

    def __iter__(self):
        return iter(self._config)

    def keys(self):
        return self._config.keys()

    def values(self):
        return itertools.starmap(self._evaluate, self._config.items())

    def items(self):
        return zip(self._config.keys(), self.values())

    def of_type(self, option_cls: OptionMeta):
        config_cls = type(self._config)
        config = config_cls({
            name: value
            for name, value in self.items()
            if name in OptionMeta.options
            and issubclass(OptionMeta.options[name], option_cls)
        })
        return type(self)(config, runtime_checks=self._runtime_checks)


class CallableEvaluator(AttributeAccessibleDict):
    """
    Intercept attribute and dict item access. If the return value would be an
    instance of :class:`Compute`, call the compute object with self as the only
    argument.

    Internally a stack of item names, that are looked up, is maintained to
    detect infinite recursion.
    """
    __slots__ = ('_stack',)

    def __init__(self,
                 config: Union[collections.abc.Mapping, Iterable[Tuple[Any, Any]]]):
        super().__init__(config)
        object.__setattr__(self, '_stack', [])

    def __getitem__(self, key):
        value = super().__getitem__(key)
        value = self._evaluate(key, value)
        return value

    def _evaluate(self, key, value):
        if key in self._stack:
            raise ConfigOptionError("Option recursion {} => {}"
                                    .format(' => '.join(self._stack), key),
                                    option=key)
        self._stack.append(key)
        if isinstance(value, Compute):
            self[key] = value = value(self)
        self._stack.pop()
        return value

    def values(self):
        return itertools.starmap(self._evaluate, super().items())

    def items(self):
        return zip(self.keys(), self.values())


def is_config_loaded() -> bool:
    return CONFIG_PACKAGE_NAME in sys.modules


def get_config(*, runtime_checks: bool = False,
               option_cls: Optional[OptionMeta] = None) -> Config:
    try:
        module = sys.modules[CONFIG_PACKAGE_NAME]
    except KeyError:
        raise RuntimeError("Config has not been loaded") from None
    config = Config(module.hades_config, runtime_checks=runtime_checks)
    if option_cls is not None:
        config = config.of_type(option_cls)
    return config


class ConfigLoadError(ConfigError):
    """Exception class for errors during config file loading."""

    def __init__(self, *args, filename):
        self.filename = filename
        super().__init__(*args)

    def report_error(self, fallback_logger: Logger) -> None:
        logger = self.logger or fallback_logger

        root_config = pathlib.PurePath(self.filename)
        message = self._build_message(root_config)
        if logger.getEffectiveLevel() > logging.INFO:
            logger.critical(
                "Error while loading config file %s: %s.\n"
                "Have you forgotten to run this script as a suitable hades user?",
                root_config,
                message,
            )
            logger.critical("Hint: Increase verbosity for a full traceback.")
            return
        logger.info(
            "Error while loading config file %s: %s",
            root_config,
            message,
            exc_info=self,
        )

    def _build_message(self, root_config: pathlib.PurePath) -> str:
        root_config_dir = root_config.parent
        # TODO more elegant would be to let the user pass the cause to the constructor,
        # but this works as well (as long as it is called after the `raise … from cause`)
        cause = self.__cause__
        if cause is None:
            return str(self)

        if isinstance(cause, ImportError) and (
            config := _config_from_module_name(cause, root_config_dir)
        ):
            if config == root_config:
                return "File could not be imported"
            return f"The file {config} could not be imported"

        if isinstance(cause, SyntaxError):
            return _format_cause(cause)

        tb = (cause or self).__traceback__
        filename, lineno, funcname, src = _origin(tb, root_config_dir)
        return f'File "{filename}", line {lineno}\n{_format_cause(cause)}'


def _format_cause(cause: Optional[BaseException]) -> str:
    return "".join(
        traceback.format_exception_only(
            type(cause) if cause is not None else None, cause
        )
    ).strip()


def _config_from_module_name(
    cause: ImportError,
    root_config_dir: pathlib.PurePath,
) -> t.Optional[t.Union[str, pathlib.PurePath]]:
    if cause.name is not None:
        top, sep, tail = cause.name.partition('.')
        if top == CONFIG_PACKAGE_NAME:
            if tail == '':
                return '__init__.py'
            else:
                return root_config_dir / (tail.replace('.', '/') + '.py')
    return None


def _origin(
        tb: t.Optional[TracebackType],
        root_config_dir: pathlib.PurePath,
) -> t.Union[traceback.FrameSummary, t.Tuple[str, int, str, str]]:
    """Try to find the originating config in the traceback"""
    tb_info = traceback.extract_tb(tb)
    for filename, lineno, funcname, src in reversed(tb_info):
        if filename is not None:
            try:
                pathlib.PurePath(filename).relative_to(root_config_dir)
            except ValueError:
                pass
            else:
                return filename, lineno, funcname, src
    return tb_info[-1]


def print_config_error(e: ConfigError):
    import warnings
    warnings.warn(f"Use {type(e).__name__}.report_error() instead", DeprecationWarning)
    e.report_error(logger)


class _safe_install:
    def __init__(self, module):
        self.module = module

    def __enter__(self):
        sys.modules[self.module.__package__] = self.module
        self.dont_write_bytecode = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        return self

    def __exit__(self, *exc):
        sys.dont_write_bytecode = self.dont_write_bytecode
        if any(v is not None for v in exc):
            try:
                del sys.modules[CONFIG_PACKAGE_NAME]
            except KeyError:
                pass


def load_config(filename: Optional[str] = None, *, runtime_checks: bool = False,
                option_cls: Optional[OptionMeta] = None) -> Config:
    if is_config_loaded():
        raise RuntimeError("Config already loaded")
    config = AttributeAccessibleDict(OptionMeta.get_defaults())
    if filename is None:
        filename = os.environ.get('HADES_CONFIG', DEFAULT_CONFIG)

    module_path = pathlib.Path(filename).resolve()
    if module_path.is_dir():
        module_name = '__init__'
        module_path = module_path / '__init__.py'
    else:
        if module_path.suffix != '.py':
            raise ConfigLoadError("The file must have a .py extension.",
                                  filename=str(module_path))
        module_name = module_path.stem
        if not module_name.isidentifier():
            raise ConfigLoadError("The name of the config file is not a valid "
                                  "Python identifier.",
                                  filename=str(module_path))
    module_qualname = "{}.{}".format(CONFIG_PACKAGE_NAME, module_name)
    package_path = module_path.with_name('__init__.py')
    loader = importlib.machinery.SourceFileLoader(CONFIG_PACKAGE_NAME,
                                                  str(package_path))
    package_module = importlib.util.module_from_spec(
        importlib.machinery.ModuleSpec(
            CONFIG_PACKAGE_NAME, loader, origin=str(package_path),
            is_package=True
        )
    )
    package_module.__file__ = str(package_path)
    package_module.__doc__ = "Config pseudo package"
    package_module.__path__ = [str(package_path.parent)]

    try:
        with _safe_install(package_module):
            if package_path.exists():
                loader.exec_module(package_module)
            module = importlib.import_module(module_qualname)
    except Exception as e:
        raise ConfigLoadError(filename=str(module_path)) from e
    config.update((name, getattr(module, name))
                  for name in dir(module) if is_option_name(name))
    config = CallableEvaluator(config)
    OptionMeta.check_config(config)
    package_module.hades_config = config  # type: ignore
    return get_config(runtime_checks=runtime_checks, option_cls=option_cls)
