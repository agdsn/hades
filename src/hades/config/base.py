import re


option_name_regex = re.compile(r'\A[A-Z][A-Z0-9_]*\Z', re.ASCII)


def is_option_name(name):
    """
    Check if a given object is a valid option name.

    Valid option names are restricted to ASCII, start with an uppercase letter
    followed by uppercase letters (A-Z), digits (0-9) or the underscore (_).
    :param name: Name
    :return: True, if name is string and a valid option name, False otherwise
    :rtype: bool
    """
    return isinstance(name, str) and option_name_regex.match(name)


def qualified_name(type_):
    if type_.__module__ is None or type_.__module__ == 'builtins':
        return type_.__qualname__
    else:
        return type_.__module__ + '.' + type_.__qualname__


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
            raise TypeError("option named {} already defined as {}."
                            .format(name, qualified_name(mcs.options[name])))
        if not abstract and not is_option_name(name):
            raise TypeError('not a valid option name')
        class_ = super(OptionMeta, mcs).__new__(mcs, name, bases, attributes)
        if not abstract:
            mcs.options[name] = class_
        return class_

    # noinspection PyUnusedLocal
    def __init__(cls, name, bases, attributes, abstract=False):
        super().__init__(name, bases, attributes)


class Option(object, metaclass=OptionMeta, abstract=True):
    required = False
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
