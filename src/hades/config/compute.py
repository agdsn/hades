from hades.config.base import ConfigError, MissingOptionError, coerce


def equal_to(other):
    other_name = coerce(other)
    if not isinstance(other_name, str):
        raise TypeError("Expected Option subclass or str, was {}"
                        .format(type(other_name)))

    def f(config, name):
        try:
            return config[other_name]
        except MissingOptionError as e:
            raise ConfigError("Can not set equal to option {}, option is not "
                              "defined".format(other_name), option=name) from e
    return f


def deferred_format(fmt_string, *args, **kwargs):
    """
    Evaluate a format string using values from others config options.

    Names of options are given as positional arguments and the corresponding
    values can be referred to using numbers in the format string.
    Keywords arguments can be used as well to bind other option values to
    specific names that are available in the format string.
    :param fmt_string:
    :param args:
    :param kwargs:
    :return:
    """
    args = tuple(coerce(arg) for arg in args)
    kwargs = {k: coerce(v) for k, v in kwargs}

    def f(config, name):
        fmt_args = tuple(config[a] for a in args)
        fmt_kwargs = {k: config[v] for k, v in kwargs}
        return fmt_string.format(*fmt_args, **fmt_kwargs)
    return f
