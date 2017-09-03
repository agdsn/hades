import collections
import itertools
import logging
import os
import types
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
        return self._config.values()

    def items(self):
        return self._config.items()

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


_config = None


def is_config_loaded() -> bool:
    return _config is not None


def get_config(*, runtime_checks: bool = False,
               option_cls: Optional[OptionMeta] = None) -> Config:
    if _config is None:
        raise RuntimeError("Config has not been loaded")
    config = Config(_config, runtime_checks=runtime_checks)
    if option_cls is not None:
        config = config.of_type(option_cls)
    return config


def load_config(filename: Optional[str] = None, *, runtime_checks: bool = False,
                option_cls: Optional[OptionMeta] = None) -> Config:
    config = AttributeAccessibleDict(OptionMeta.get_defaults())
    if filename is None:
        filename = os.environ.get(
            'HADES_CONFIG', os.path.join(constants.pkgsysconfdir, 'config.py'))
    d = types.ModuleType(__package__ + '.config_pseudo_module')
    d.__file__ = filename
    try:
        with open(filename) as f:
            exec(compile(f.read(), filename, 'exec'), d.__dict__)
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
    config.update((name, getattr(d, name))
                  for name in dir(d) if is_option_name(name))
    config = CallableEvaluator(config)
    OptionMeta.check_config(config)
    global _config
    _config = config
    return get_config(runtime_checks=runtime_checks, option_cls=option_cls)
