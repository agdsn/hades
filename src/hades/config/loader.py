import collections
import logging
import os
import types

from hades.common.util import memoize
from hades.config.check import check_option
from hades.config.options import OptionMeta

logger = logging.getLogger(__name__)


def from_object(obj):
    return {name: getattr(obj, name) for name in dir(obj) if name.isupper()}


class ConfigObject(collections.Mapping):
    """
    An object suitable to be loaded by Flask or Celery.
    """
    def __init__(self, d):
        self._data = d
        for name, value in d.items():
            setattr(self, name, value)

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def __contains__(self, x):
        return x in self._data

    def __getitem__(self, item):
        return self._data[item]

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()


class CheckWrapper(collections.Mapping):
    """Wrapper around a config object that executes check functions if options
    are accessed."""

    def __init__(self, config, runtime_checks=True):
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


def get_defaults():
    return {name: option.default for name, option in OptionMeta.options.items()
            if option.default is not None}


def check_config(config, runtime_checks=False):
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
            config[name] = value(config, name)


@memoize
def get_config():
    config = get_defaults()
    try:
        filename = os.environ['HADES_CONFIG']
    except KeyError:
        return ConfigObject(config)
    d = types.ModuleType('hades.config.user')
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
    config.update(from_object(d))
    evaluate_callables(config)
    check_config(config)
    return ConfigObject(config)
