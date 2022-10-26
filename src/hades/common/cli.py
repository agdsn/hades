"""Functionality for the Hades command-line utilities in :mod:`hades.bin`."""
import argparse
import functools
import inspect
import logging.handlers
import os
import socket
import sys
import typing
import urllib.parse
from gettext import gettext as _

import systemd.journal

from hades import constants

from .logging import (
    plain_formatter,
    stderr_debug_formatter,
    syslog_debug_formatter,
)

T = typing.TypeVar("T")


class ArgumentParser(argparse.ArgumentParser):
    """ArgumentParser subclass that exists with :data:`os.EX_USAGE` exit code if
    parsing fails and uses a custom version action for different formatting."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.register("action", "version", VersionAction)

    def error(self, message: str) -> typing.NoReturn:
        self.print_usage(sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self.exit(os.EX_USAGE, _('%(prog)s: error: %(message)s\n') % args)


class VersionAction(argparse.Action):
    warranty_notice = """
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
    THE SOFTWARE.
    """

    # noinspection PyShadowingBuiltins
    def __init__(
        self,
        option_strings: typing.Sequence[str],
        version: None = None,
        dest: str = argparse.SUPPRESS,
        default: typing.Union[T, str, None] = argparse.SUPPRESS,
        help: str = "show program's version number, configure options, copyright notice and exit",
    ) -> None:
        if version is not None:
            raise ValueError("version may not be overriden")
        super(VersionAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: typing.Union[str, typing.Sequence[typing.Any], None],
        option_string: typing.Optional[str] = None,
    ) -> None:
        formatter = argparse.RawDescriptionHelpFormatter(parser.prog)
        formatter.add_text(
            f"{constants.PACKAGE_NAME} version {constants.PACKAGE_VERSION}"
            f"\nConfigure Options: {constants.CONFIGURE_ARGS}"
        )
        formatter.add_text(
            f"Copyright (c) 2015-2022 {constants.PACKAGE_AUTHOR}"
        )
        formatter.add_text(inspect.cleandoc(self.warranty_notice))
        print(formatter.format_help())
        parser.exit()


def syslog_url(v: str) -> dict[str, typing.Any]:
    """Convert syslog CLI argument URL into
    :class:`logging.handlers.SyslogHandler` `kwargs`."""
    # If argparse catches ValueError or TypeError, it swallows the actual
    # exception message and prints only 'invalid %(type)s value: %(value)r',
    # whereas ArgumentTypeError prints the actual exception message. A bare
    # ValueError or TypeError reaching the argparse is therefore considered a
    # bug.
    try:
        return _syslog_url(v)
    except (ValueError, TypeError) as e:
        raise AssertionError(f"Unhandled {type(e)} error") from e


def _syslog_url(v: str) -> dict[str, typing.Any]:
    try:
        url = urllib.parse.urlsplit(v)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"Failed to parse URL {v!r}: {e}"
        ) from e
    result: dict[str, typing.Any] = {}
    if url.query:
        try:
            parameters = urllib.parse.parse_qsl(
                url.query,
                keep_blank_values=True,
                errors="strict",
                strict_parsing=True,
            )
        except ValueError as e:
            raise argparse.ArgumentTypeError(
                f"Failed to parse query: {url.query!r}: {e}"
            ) from e
        extra_parameters = []
        for name, value in parameters:
            if name == 'facility':
                if value not in logging.handlers.SysLogHandler.facility_names:
                    raise argparse.ArgumentTypeError(
                        f"Illegal facility: {value!r}"
                    )
                result["facility"] = value
            else:
                extra_parameters.append(f"{name!r}={value!r}")
        if extra_parameters:
            raise argparse.ArgumentTypeError(
                f"Extra query parameters: {' '.join(extra_parameters)}"
            )
    scheme = url.scheme
    illegal_components: tuple[str, ...]
    if scheme in ("tcp", "udp"):
        illegal_components = ("username", "password", "path", "fragment")
        try:
            port = url.port
        except ValueError as e:
            raise argparse.ArgumentTypeError(
                f"Illegal port: {url.netloc}"
            ) from e
        hostname = "localhost" if url.hostname is None else url.hostname
        if scheme == "tcp":
            port = logging.handlers.SYSLOG_TCP_PORT if port is None else port
            socktype = socket.SOCK_STREAM
        else:
            port = logging.handlers.SYSLOG_UDP_PORT if port is None else port
            socktype = socket.SOCK_DGRAM
        result["socktype"] = socktype
        result["address"] = (hostname, port)
    elif scheme == "unix":
        illegal_components = ("netloc", "fragment")
        try:
            result["address"] = urllib.parse.unquote(url.path, errors="strict")
        except UnicodeDecodeError as e:
            raise argparse.ArgumentTypeError(
                f"Could not decode path {url.path!r}: {e}"
            ) from e
    else:
        raise argparse.ArgumentTypeError(f"Unsupported scheme: {scheme!r}")

    if any(getattr(url, c) for c in illegal_components):
        illegal_values = " ".join(
            f"{c}={v!r}" for c in illegal_components if (v := getattr(url, c))
        )
        raise argparse.ArgumentTypeError(
            f"Scheme {scheme!r} may not have {illegal_values}"
        )

    return result


VERBOSITY_LEVELS = (
    logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG, logging.NOTSET
)
DEFAULT_VERBOSITY = 1

common_parser = ArgumentParser(add_help=False)
common_parser.add_argument(
    "-c", "--config", default=None, help="Path to config file"
)
logging_group = common_parser.add_argument_group(
    title="logging options",
    description=f"""
    Logging level (verbosity) and logging target options. The default level is
    {logging.getLevelName(VERBOSITY_LEVELS[DEFAULT_VERBOSITY])} and the default
    target is stderr.
    """,
)
logging_group.add_argument(
    "-v",
    "--verbose",
    dest="verbosity",
    default=DEFAULT_VERBOSITY,
    action="count",
    help=(
        f"Be more verbose (use up to "
        f"{len(VERBOSITY_LEVELS) - DEFAULT_VERBOSITY - 1}) times"
    ),
)
logging_group.add_argument(
    "-q",
    "--quiet",
    dest="verbosity",
    action="store_const",
    const=0,
    help=(
        f"Be quiet ({logging.getLevelName(VERBOSITY_LEVELS[0])} and higher "
        f"will still be logged)"
    ),
)
common_parser.add_argument(
    "-V",
    "--version",
    action="version",
)
stderr_action = logging_group.add_argument(
    "--stderr",
    dest="stderr",
    action="store_true",
    default=None,
    help="Log to stderr.",
)
logging_group.add_argument(
    "--no-stderr",
    dest="stderr",
    action="store_false",
    default=None,
    help="Never log to stderr (not even CRITICAL messages if stderr is a tty).",
)
syslog_action = logging_group.add_argument(
    "--syslog",
    nargs=argparse.OPTIONAL,
    default=None,
    type=syslog_url,
    const=syslog_url("unix:///dev/log"),
    metavar="URL",
    help=(
        "Log to syslog via TCP, UDP or UNIX socket. Defaults to "
        "unix:///dev/log if no URL is specified. Supported URL schemes are "
        "tcp, udp, and unix. The syslog facility may specified via the "
        "facility query parameter. CRITICAL messages will still be logged "
        "on stderr too, if stderr is a tty."
    ),
)
journal_action = logging_group.add_argument(
    "--journal",
    action="store_true",
    help=(
        "Log to systemd journal. CRITICAL messages will still be logged on "
        "stderr too, if stderr is a tty."
    ),
)


def setup_cli_logging(program: str, args: argparse.Namespace) -> None:
    """
    Setup logging for CLI applications, that do not configure logging
    themselves.

    Set log level using command-line options parsed with :data:`parser`, the
    :std:envvar:`HADES_VERBOSITY` environment variable or finally the default
    value :data:`DEFAULT_VERBOSITY`.

    Messages are logged to stderr by default, but can also be logged via the
    syslog or systemd journal protocol.

    The possible log level settings are:

    - :data:`logging.ERROR` is the minimum log level.
    - :data:`logging.CRITICAL` will also be logged to stderr, if stderr is a
      terminal, even if other targets are enabled.
    - :data:`logging.WARNING` is the default logging level, but can be
      suppressed with ``-q``/``--quiet`` or ``HADES_VERBOSITY=0``.
    - Each ``-v``/``--verbose`` increases the verbosity by one level.

    When the log level is lower than or equal to :data:`logging.DEBUG` also the
    time, the log level and the filename are logged in addition to log message.

    Flask and Celery have their own opinionated logging mechanisms. Logging
    should probably be reset via :func:`reset_cli_logging` before handing over
    control to them.

    :param program: The name of the program
    :param args: The parsed arguments of the program with :data:`parser` or a
     subparser.
    """
    # Collect log messages until after we have finished setting up, so that we
    # can log them properly
    messages: list[typing.Callable[[], None]] = []
    reset_cli_logging()
    if args.verbosity is None:
        verbosity_ = os.environ.get('HADES_VERBOSITY', DEFAULT_VERBOSITY)
        try:
            verbosity = int(verbosity_)
        except ValueError as e:
            verbosity = DEFAULT_VERBOSITY
            messages.append(
                functools.partial(
                    logging.root.critical,
                    "Illegal logging level %s",
                    exc_info=e,
                )
            )
    else:
        verbosity = typing.cast(int, args.verbosity)
    if verbosity < 0:
        messages.append(
            functools.partial(
                logging.root.critical,
                "Verbosity may not be negative"
            )
        )
    effective_verbosity = max(0, min(len(VERBOSITY_LEVELS) - 1, verbosity))
    level = VERBOSITY_LEVELS[effective_verbosity]
    handlers = list[logging.Handler]()

    if args.journal:
        journal_handler = systemd.journal.JournalHandler(
            SYSLOG_IDENTIFIER=program,
        )
        journal_handler.name = "journal"
        # The journal handler already includes all interesting metadata in
        # specific journal fields, e.g. CODE_FILE, CODE_LINE, CODE_FUNC,
        # EXCEPTION_TEXT, EXCEPTION_INFO and more. There is no need to clobber
        # the message field with other data, even in debug mode.
        # See systemd.journal-fields(7) for a list of available fields.
        journal_handler.setFormatter(plain_formatter)
        handlers.append(journal_handler)

    if args.stderr or (args.stderr is None and sys.stderr.isatty()):
        stderr_handler = logging.StreamHandler(stream=sys.stderr)
        stderr_handler.name = "stderr"
        stderr_handler.setFormatter(
            plain_formatter if level > logging.DEBUG else stderr_debug_formatter
        )
        # If not explicitly enabled, log only critical messages to stderr
        if args.stderr is None:
            stderr_handler.setLevel(logging.CRITICAL)
        handlers.append(stderr_handler)

    if args.syslog:
        syslog_handler = logging.handlers.SysLogHandler(**args.syslog)
        syslog_handler.name = "syslog"
        syslog_handler.ident = program
        syslog_handler.setFormatter(
            plain_formatter if level > logging.DEBUG else syslog_debug_formatter
        )
        handlers.append(syslog_handler)

    root = logging.root
    root.setLevel(level)
    for h in handlers:
        root.addHandler(h)
    # Log collected messages
    for message in messages:
        message()


def reset_cli_logging() -> None:
    """Reset root logger configuration"""
    root = logging.root
    for h in root.handlers:
        h.acquire()
        try:
            h.flush()
            h.close()
        except (OSError, ValueError):
            pass
        finally:
            h.release()
        root.removeHandler(h)
    for f in root.filters:
        root.removeFilter(f)
