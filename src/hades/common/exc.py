import functools
import logging
import os
import sys
import typing as t
from contextlib import contextmanager
from logging import Logger


RESTART_PREVENTING_EXCEPTIONS = frozenset(
    (os.EX_CONFIG, os.EX_USAGE, os.EX_UNAVAILABLE)
)


class HadesSetupError(Exception):
    preferred_exit_code = os.EX_UNAVAILABLE

    def __init__(self, *args, logger: t.Optional[Logger] = None):
        super().__init__(*args)
        self.logger = logger

    def __init_subclass__(cls, **kwargs: dict[str, t.Any]) -> None:
        super().__init_subclass__(**kwargs)
        if "preferred_exit_code" not in cls.__dict__:
            return
        if cls.__dict__["preferred_exit_code"] not in RESTART_PREVENTING_EXCEPTIONS:
            raise ValueError(
                "Subclasses of HadesSetupException can only provide exit codes"
                " known to prevent a restart (see `RestartPreventExitStatus=` in systemd.service(5))"
            )

    def report_error(self, fallback_logger: Logger) -> None:
        """Emit helpful log messages about this error."""
        logger = self.logger or fallback_logger
        logger.critical("Error in setup: %s", str(self), exc_info=self)


class HadesUsageError(HadesSetupError):
    preferred_exit_code = os.EX_USAGE

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)


@contextmanager
def handle_setup_errors(logger: logging.Logger) -> t.Generator[None, None, None]:
    """If a :class:`HadesSetupError` occurs, report it and call :func:`sys.exit` accordingly."""
    try:
        yield
    except HadesSetupError as e:
        e.report_error(fallback_logger=logger)
        sys.exit(e.preferred_exit_code)


F = t.TypeVar("F", bound=t.Callable[..., t.Any])


def handles_setup_errors(logger: logging.Logger) -> t.Callable[[F], F]:
    def decorator(f: F) -> F:
        @functools.wraps(f)
        def wrapped(*a, **kw):
            with handle_setup_errors(logger):
                f(*a, **kw)

        return t.cast(F, wrapped)

    return decorator
