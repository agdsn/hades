import types
from typing import Union

from hades.config.base import (
    Compute, ConfigOptionError, MissingOptionError, Option, coerce,
)


class equal_to(Compute):
    def __init__(self, other: Union[str, type(Option)]):
        super().__init__()
        self.other_name = coerce(other)
        if not isinstance(self.other_name, str):
            raise TypeError("Expected Option subclass or str, was {}"
                            .format(type(self.other_name)))

    def __call__(self, config):
        try:
            return config[self.other_name]
        except MissingOptionError as e:
            raise ConfigOptionError(
                "Can not set equal to option {}, option is not defined"
                .format(self.other_name), option=self.option.__name__
            ) from e


class deferred_format(Compute):
    """
    Evaluate a format string using values from others config options.

    Names of options are given as positional arguments and the corresponding
    values can be referred to using numbers in the format string.
    Keywords arguments can be used as well to bind other option values to
    specific names that are available in the format string.
    """

    def __init__(self, fmt_string, *args: Union[str, type(Option)],
                 **kwargs: Union[str, type(Option)]):
        """
        :param fmt_string:
        :param args:
        :param kwargs:
        :return:
        """
        super().__init__()
        self.fmt_string = fmt_string
        self.args = tuple(coerce(arg) for arg in args)
        self.kwargs = {k: coerce(v) for k, v in kwargs}

    def __call__(self, config):
        fmt_args = tuple(config[a] for a in self.args)
        fmt_kwargs = {k: config[v] for k, v in self.kwargs}
        return self.fmt_string.format(*fmt_args, **fmt_kwargs)
