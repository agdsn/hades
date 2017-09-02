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


# noinspection PyUnresolvedReferences
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
        if not abstract and 'default' in attributes:
            attributes['has_default'] = True
        class_ = super(OptionMeta, mcs).__new__(mcs, name, bases, attributes)
        if class_.has_default and class_.required:
            raise TypeError("required options can't have defaults")
        if not abstract:
            mcs.options[name] = class_
        return class_

    # noinspection PyUnusedLocal
    def __init__(cls, name, bases, attributes, abstract=False):
        super().__init__(name, bases, attributes)

    @classmethod
    def check_config(mcs, config, runtime_checks=False):
        for name, option in mcs.options.items():
            if option.required and name not in config:
                raise ConfigError("required option", option=name)
        for name, value in config.items():
            option = mcs.options.get(name)
            if option:
                option.check_option(config, value,
                                    runtime_checks=runtime_checks)

    def check_option(self, config, value, runtime_checks=False):
        if self.type is not None and not isinstance(value, self.type):
            expected = qualified_name(self.type)
            got = qualified_name(type(value))
            raise OptionCheckError("Must be a subtype of {}, was {}"
                                   .format(expected, got), option=self.__name__)
        if self.static_check:
            self.static_check(config, value)
        if runtime_checks and self.runtime_check:
            self.runtime_check(config, value)


class Option(object, metaclass=OptionMeta, abstract=True):
    has_default = False
    required = False
    default = None
    type = None
    category = "hades"
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


class OptionCheckError(ConfigError):
    pass
