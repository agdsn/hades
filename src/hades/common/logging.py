"""Common logging utilities."""
import logging
import time
import typing as t


class RFC3389UTCFormatter(logging.Formatter):
    """A formatter that formats time in RFC3389 and UTC."""

    converter = time.gmtime
    default_time_format = "%Y-%m-%dT%H:%M:%S"
    """strftime-format string for RFC3389 with separator T"""
    default_msec_format = "%s.%03dZ"
    """Append RFC3389 milliseconds with dot and UTC time zone designator"""

    def __init__(
        self,
        fmt: t.Optional[str] = None,
        *,
        style: t.Literal["%", "{", "$"] = "%",
        validate: bool = True,
        defaults: t.Optional[t.Mapping[str, t.Any]] = None,
    ) -> None:
        """
        See :meth:`logging.Formatter.__init__` for argument documentation.

        The signature was modified deliberately as follows:

        * The `datefmt` argument has been omitted.
        * All arguments following `fmt` are keyword-only (`style`, `validate`)
          to prevent accidental passing positional `datefmt`.
        """
        super().__init__(fmt, style=style, validate=validate, defaults=defaults)


plain_formatter = RFC3389UTCFormatter("%(message)s")
"""Formatter that produces only the log message"""

stderr_debug_formatter = RFC3389UTCFormatter(
    "[%(asctime)s] %(levelname)s:%(filename)s:%(lineno)d:%(message)s"
)
"""Formatter for extensive debug output to stderr"""

syslog_debug_formatter = RFC3389UTCFormatter("%(filename)s:%(lineno)d:%(message)s")
"""Formatter for extensive debug output to syslog"""
