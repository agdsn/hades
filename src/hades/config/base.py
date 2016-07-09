class OptionMeta(type):
    """
    Metaclass for options.

    Classes with this metaclass, which are named not declared abstract by
    setting the abstract keyword argument are added to the :attr:`.options`
    dictionary.
    """
    options = {}

    def __new__(mcs, name, bases, attributes, abstract=False):
        if name in mcs.options:
            raise TypeError("An option named {} is already defined."
                            .format(name))
        class_ = super(OptionMeta, mcs).__new__(mcs, name, bases, attributes)
        if not abstract:
            mcs.options[name] = class_
        return class_

    # noinspection PyUnusedLocal
    def __init__(cls, name, bases, attributes, abstract=False):
        super().__init__(name, bases, attributes)


class Option(object, metaclass=OptionMeta, abstract=True):
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
