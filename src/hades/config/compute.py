from typing import Union, Type

from .base import (
    Compute,
    ConfigOptionError,
    MissingOptionError,
    Option,
    coerce,
    option_reference,
)


# noinspection PyPep8Naming
class equal_to(Compute):
    def __init__(self, other: Union[str, Type[Option]]):
        super().__init__()
        self.other_name = coerce(other)
        if not isinstance(self.other_name, str):
            raise TypeError("Expected Option subclass or str, was {}"
                            .format(type(self.other_name)))

        self.__doc__ = "Equal to {}".format(option_reference(self.other_name))

    def __call__(self, config):
        try:
            return config[self.other_name]
        except MissingOptionError as e:
            raise ConfigOptionError(
                "Can not set equal to option {}, option is not defined"
                .format(self.other_name), option=self.option.__name__
            ) from e


# noinspection PyPep8Naming
class deferred_format(Compute):
    """
    Evaluate a format string using values from others config options.

    Names of options are given as positional arguments and the corresponding
    values can be referred to using numbers in the format string.
    Keywords arguments can be used as well to bind other option values to
    specific names that are available in the format string.
    """

    def __init__(self, fmt_string, *a: Union[str, Type[Option]],
                 **kw: Union[str, Type[Option]]):
        """
        :param fmt_string:
        :param args:
        :param kwargs:
        :return:
        """
        super().__init__()
        self.fmt_string = fmt_string
        self.args = tuple(coerce(arg) for arg in a)
        self.kwargs = {k: coerce(v) for k, v in kw.items()}

        args, kwargs = "", ""
        if self.args:
            args = (
                ", with {} as positional {}".format(
                    ', '.join(option_reference(opt) for opt in self.args),
                    "arguments" if len(self.args) > 1 else "argument")
            )

        if self.kwargs:
            kwargs = (
                ", with {} as keyword {}"
                .format(', '.join("{}={}".format(
                    key, option_reference(opt))
                    for key, opt in self.kwargs.items()),
                 "arguments" if len(self.args) > 1 else "argument")
            )

        self.__doc__ = (
            "Will be computed from the format string :python:`{!r}`{}{}."
            .format(self.fmt_string, args, kwargs)
        )

    def __call__(self, config):
        fmt_args = tuple(config[a] for a in self.args)
        fmt_kwargs = {k: config[v] for k, v in self.kwargs.items()}
        return self.fmt_string.format(*fmt_args, **fmt_kwargs)
