import collections
import importlib.abc
import importlib.machinery
import importlib.util
import itertools
import logging
import os
import pathlib
import sys
from typing import Any, Iterable, Optional, Tuple, Union

# noinspection PyUnresolvedReferences
import hades.config.options
from hades import constants
from hades.config.base import ConfigError, OptionMeta, is_option_name

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
        attributes = super().__dir__()
        self_attributes = set(attributes)
        attributes.extend(attribute for attribute in self.keys()
                          if attribute not in self_attributes)
        return attributes


class Config(collections.Mapping):
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
        value = self._config[key]
        self._verify(key, value)
        return value

    def _verify(self, key, value):
        option = OptionMeta.options.get(key)
        if option:
            option.check_option(self._config, value, self._runtime_checks)

    def __dir__(self):
        attributes = super().__dir__()
        self_attributes = set(attributes)
        attributes.extend(attribute for attribute in dir(self._config)
                          if attribute not in self_attributes)
        return attributes

    def __len__(self):
        return len(self._config)

    def __contains__(self, x):
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
    Intercept attribute and dict item access. If the return value would be a
    callable value, call the value with self as the only argument.

    Internally a stack of item names, that are looked up, is maintained to
    detect infinite recursion.
    """
    __slots__ = ('_stack',)

    def __init__(self,
                 config: Union[collections.Mapping, Iterable[Tuple[Any, Any]]]):
        super().__init__(config)
        object.__setattr__(self, '_stack', [])

    def __getitem__(self, key):
        value = super().__getitem__(key)
        value = self._evaluate(key, value)
        return value

    def _evaluate(self, key, value):
        if key in self._stack:
            raise ConfigError("Option recursion {} -> {}"
                              .format('->'.join(self._stack), key),
                              option=key)
        self._stack.append(key)
        if callable(value):
            self[key] = value = value(self)
        self._stack.pop()
        return value

    def values(self):
        return itertools.starmap(self._evaluate, super().items())

    def items(self):
        return zip(self.keys(), self.values())


def is_config_loaded() -> bool:
    return 'hades_config' in sys.modules


def get_config(*, runtime_checks: bool = False,
               option_cls: Optional[OptionMeta] = None) -> Config:
    try:
        module = sys.modules['hades_config']
    except KeyError:
        raise RuntimeError("Config has not been loaded") from None
    config = Config(module.hades_config, runtime_checks=runtime_checks)
    if option_cls is not None:
        config = config.of_type(option_cls)
    return config


def load_config(filename: Optional[str] = None, *, runtime_checks: bool = False,
                option_cls: Optional[OptionMeta] = None) -> Config:
    if is_config_loaded():
        raise RuntimeError("Config already loaded")
    config = AttributeAccessibleDict(OptionMeta.get_defaults())
    if filename is None:
        filename = os.environ.get(
            'HADES_CONFIG', os.path.join(constants.pkgsysconfdir, 'config.py'))
    filepath = pathlib.Path(filename).resolve()
    filename = str(filepath)
    package = 'hades_config'
    loader = importlib.machinery.SourceFileLoader(package, filename)
    module = importlib.util.module_from_spec(importlib.machinery.ModuleSpec(
        package, loader, origin=filename, is_package=True
    ))
    module.__file__ = filename
    module.__doc__ = "Config pseudo module"
    sys.modules[package] = module

    try:
        loader.exec_module(module)
    except FileNotFoundError:
        logger.exception("Config file %s not found", filename)
        raise
    except PermissionError:
        logger.exception("Can't open config file %s (Permission denied)",
                         filename)
        raise
    except IsADirectoryError:
        logger.exception("Config file %s is a directory", filename)
        raise
    except IOError as e:
        logger.exception("Config file %s (I/O error): %s", filename, str(e))
        raise
    except (SyntaxError, TypeError) as e:
        logger.exception("Config file %s has errors: %s", filename, str(e))
        raise
    config.update((name, getattr(module, name))
                  for name in dir(module) if is_option_name(name))
    config = CallableEvaluator(config)
    OptionMeta.check_config(config)
    module.hades_config = config
    return get_config(runtime_checks=runtime_checks, option_cls=option_cls)
