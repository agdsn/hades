"""Functionality for the Hades command-line utilities in :mod:`hades.bin`."""
import argparse
import functools
import inspect
import logging.handlers
import os
import sys
import typing
from gettext import gettext as _

from hades import constants


class ArgumentParser(argparse.ArgumentParser):
    """ArgumentParser subclass that exists with :data:`os.EX_USAGE` exit code if
    parsing fails."""
    def error(self, message):
        self.print_usage(sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self.exit(os.EX_USAGE, _('%(prog)s: error: %(message)s\n') % args)


class VersionAction(argparse.Action):
    # noinspection PyShadowingBuiltins
    def __init__(self,
                 option_strings,
                 version_info=None,
                 dest=argparse.SUPPRESS,
                 default=argparse.SUPPRESS,
                 help="show program's version number, configure options, copyright notice and exit"):
        super(VersionAction, self).__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            help=help)
        self.version_info = version_info

    def __call__(self, parser: argparse.ArgumentParser, namespace: argparse.Namespace, values, option_string=None):
        version_info = self.version_info
        print(version_info)
        parser.exit()


VERBOSITY_LEVELS = (
    logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG, logging.NOTSET
)
DEFAULT_VERBOSITY = 1

parser = ArgumentParser(add_help=False)
parser.add_argument('-c', '--config', default=None, help="Path to config file")
parser.add_argument(
    "-v",
    "--verbose",
    dest="verbosity",
    default=DEFAULT_VERBOSITY,
    action="count",
    help=(
        f"Be more verbose (use up to "
        f"{len(VERBOSITY_LEVELS) - DEFAULT_VERBOSITY}) times"
    ),
)
parser.add_argument(
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
parser.add_argument(
    "-V",
    "--version",
    action=VersionAction,
    version_info=inspect.cleandoc(
        """
        {PACKAGE_NAME} version {PACKAGE_VERSION}
        Configure Options: {CONFIGURE_ARGS}

        Copyright (c) 2015-2020 {PACKAGE_AUTHOR}

        THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
        IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
        FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
        AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
        LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
        OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
        THE SOFTWARE.
        """
    ).format(
        PACKAGE_NAME=constants.PACKAGE_NAME,
        PACKAGE_VERSION=constants.PACKAGE_VERSION,
        CONFIGURE_ARGS=constants.CONFIGURE_ARGS,
        PACKAGE_AUTHOR=constants.PACKAGE_AUTHOR,
    )
)
parser.add_argument(
    "--syslog",
    nargs="?",
    const="/dev/log",
    metavar="SOCKET",
    help=(
        "Log to syslog instead of stderr. CRITICAL messages will still be "
        "logged on stderr too. A path to the log socket may be provided, "
        "defaults to /dev/log otherwise."
    ),
)


def setup_cli_logging(program, args):
    """
    Setup logging for CLI applications, that do not configure logging
    themselves.

    Set log level using command-line options parsed with :data:`parser`, the
    :std:envvar:`HADES_VERBOSITY` environment variable or finally the default
    value :data:`DEFAULT_VERBOSITY`.

    Messages are logged to stderr by default, but can also be logged to syslog.

    The possible log level settings are:

    - :data:`logging.ERROR` is the minimum log level.
    - :data:`logging.CRITICAL` will always also be logged to STDERR even if
      logging to syslog.
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
        verbosity = os.environ.get('HADES_VERBOSITY', DEFAULT_VERBOSITY)
        try:
            verbosity = int(verbosity)
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
        verbosity = args.verbosity
    if verbosity < 0:
        messages.append(
            functools.partial(
                logging.root.critical,
                "Verbosity may not be negative"
            )
        )
    effective_verbosity = max(0, min(len(VERBOSITY_LEVELS) - 1, verbosity))
    level = VERBOSITY_LEVELS[effective_verbosity]
    if level <= logging.DEBUG:
        fmt = ("[%(asctime)s] %(levelname)s in %(filename)s:%(lineno)d: "
               "%(message)s")
    else:
        fmt = "%(message)s"
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.name = "stderr"
    if args.syslog is not None:
        # Also log critical messages to stderr
        stderr_handler.setLevel(logging.CRITICAL)
        syslog_handler = logging.handlers.SysLogHandler(address=args.syslog)
        syslog_handler.name = "syslog"
        handlers = [syslog_handler, stderr_handler]
    else:
        handlers = [stderr_handler]
    logging.basicConfig(level=level, style='%', format=fmt, handlers=handlers)
    # Log collected messages
    for message in messages:
        message()


def reset_cli_logging():
    """Reset root logger configuration"""
    root = logging.root
    for h in root.handlers:
        try:
            h.acquire()
            h.flush()
            h.close()
        except (OSError, ValueError):
            pass
        finally:
            h.release()
        root.removeHandler(h)
    for f in root.filters:
        root.removeFilter(f)
