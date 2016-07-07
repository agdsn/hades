class OptionMeta(type):
    """Metaclass for options. Classes that derive from options are registered
    in a global dict"""
    options = {}

    def __new__(mcs, name, bases, attributes):
        if name in mcs.options:
            raise TypeError("An option named {} is already defined."
                            .format(name))
        class_ = super(OptionMeta, mcs).__new__(mcs, name, bases, attributes)
        mcs.options[name] = class_
        return class_


class Option(object, metaclass=OptionMeta):
    default = None
    type = None
    runtime_check = None
    static_check = None


class ConfigError(Exception):
    def __init__(self, *args, option=None, **kwargs):
        super(ConfigError, self).__init__(*args, **kwargs)
        self.option = option

    def __str__(self):
        return "{}: {}".format(self.option, super(ConfigError, self).__str__())


class MissingOptionError(ConfigError):
    def __init__(self, *args, **kwargs):
        super(MissingOptionError, self).__init__(*args, **kwargs)


def coerce(value):
    if isinstance(value, type) and issubclass(value, Option):
        return value.__name__
    else:
        return value
