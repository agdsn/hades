import argparse
import logging
import os
import sys
from gettext import gettext as _

from hades import constants


class ArgumentParser(argparse.ArgumentParser):
    """
    ArgumentParser subclass that exists with os.EX_USAGE exit code if parsing
    fails.
    """
    def error(self, message):
        self.print_usage(sys.stderr)
        args = {'prog': self.prog, 'message': message}
        self.exit(os.EX_USAGE, _('%(prog)s: error: %(message)s\n') % args)


parser = ArgumentParser(add_help=False)
parser.add_argument('-c', '--config', default=None, help="Path to config file")
parser.add_argument('-v', '--verbose', dest='verbosity',
                    default=None, action='count', help='Be more verbose')
parser.add_argument('-q', '--quiet', dest='verbosity',
                    action='store_const', const=0, help='Be quiet')
parser.add_argument('-V', '--version', action='version',
                    version=constants.PACKAGE_VERSION)
VERBOSITY_LEVELS = [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
DEFAULT_VERBOSITY = 1


def setup_cli_logging(program, args):
    """
    Setup logging for CLI applications, that do not configure logging
    themselves.

    Flask and Celery are quite opinionated about logging, so this function
    should probably not be called in their launchers.
    :param program: The name of the program
    :param args: The parsed arguments of the program
    """
    reset_cli_logging()
    if args.verbosity is None:
        verbosity = os.environ.get('HADES_VERBOSITY', DEFAULT_VERBOSITY)
        try:
            verbosity = int(verbosity)
        except ValueError:
            verbosity = DEFAULT_VERBOSITY
    else:
        verbosity = args.verbosity
    effective_verbosity = max(0, min(len(VERBOSITY_LEVELS) - 1, verbosity))
    level = VERBOSITY_LEVELS[effective_verbosity]
    if level <= logging.DEBUG:
        fmt = ("[%(asctime)s] %(levelname)s in %(filename)s:%(lineno)d: "
               "%(message)s")
    else:
        fmt = "%(message)s"
    logging.basicConfig(level=level, style='%', format=fmt, stream=sys.stderr)


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
