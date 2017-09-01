import collections
import logging
import os
import types
from typing import Optional

# noinspection PyUnresolvedReferences
import hades.config.options
from hades import constants
from hades.config.base import ConfigError, OptionMeta, is_option_name
from hades.config.check import check_option

logger = logging.getLogger(__name__)


class ConfigObject(collections.MutableMapping):
    """
    An object suitable to be loaded by Flask or Celery.
    """
    def __init__(self, d):
        super().__init__()
        self.__dict__.update(d)

    def __iter__(self):
        return iter(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def __bool__(self):
        return bool(self.__dict__)

    def __contains__(self, x):
        return x in self.__dict__

    def __getitem__(self, item):
        return self.__dict__[item]

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __delitem__(self, key):
        del self.__dict__[key]

    def keys(self):
        return self.__dict__.keys()

    def values(self):
        return self.__dict__.values()

    def items(self):
        return self.__dict__.items()

    def category_(self, category):
        return type(self)((name, value) for name, value in self.items()
                          if name in OptionMeta.options
                          and OptionMeta.options[name].category == category)


class CheckWrapper(collections.Mapping):
    """Wrapper around a config object that executes check functions if options
    are accessed."""

    def __init__(self, config: ConfigObject, *, runtime_checks: bool = True):
        super().__init__()
        self._config = config
        self._runtime_checks = runtime_checks

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
            check_option(self._config, option, value, self._runtime_checks)

    def __dir__(self):
        attributes = super().__dir__().copy()
        attributes.extend(attribute for attribute in dir(self._config)
                          if attribute not in dir)
        return attributes

    def __bool__(self):
        return bool(self._config)

    def __len__(self):
        len(self._config)

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

    def category_(self, category):
        return type(self)(self._config.category_(category),
                          runtime_checks=self._runtime_checks)


def get_defaults():
    return ConfigObject((name, option.default)
                        for name, option in OptionMeta.options.items()
                        if option.has_default)


def check_config(config, runtime_checks=False):
    for name, option in OptionMeta.options.items():
        if option.required and name not in config:
            raise ConfigError("required option", option=name)
    for name, value in config.items():
        option = OptionMeta.options.get(name)
        if option:
            check_option(config, option, value, runtime_checks=runtime_checks)


def evaluate_callables(config):
    """Option values may be callables that are evaluated after the full config
    has been loaded. They receive the config and the name of the option as
    arguments"""
    for name, value in config.items():
        if callable(value):
            config[name] = value(config)


_config = None


def is_config_loaded() -> bool:
    return _config is not None


def get_config(*, runtime_checks: bool = False,
               category: Optional[str] = None) -> CheckWrapper:
    if _config is None:
        raise RuntimeError("Config has not been loaded")
    if category is None:
        config = _config
    else:
        config = _config.category_(category)
    return CheckWrapper(config, runtime_checks=runtime_checks)


def load_config(filename: Optional[str] = None, *,
                runtime_checks: bool = False,
                category: Optional[str] = None) -> CheckWrapper:
    config = get_defaults()
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
    evaluate_callables(config)
    check_config(config)
    global _config
    _config = config
    return get_config(runtime_checks=runtime_checks, category=category)
