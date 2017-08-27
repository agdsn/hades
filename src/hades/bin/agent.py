import argparse
import os
import sys
import textwrap

# noinspection PyUnresolvedReferences
from hades.agent import tasks
from hades.agent.tasks import app
from hades.common.cli import ArgumentParser, parser as common_parser
from hades.config.loader import load_config


class Formatter(argparse.HelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        actions = list(actions)
        actions.append(argparse.Action([], dest='worker_options',
                                       metavar='worker options', nargs='?'))
        super().add_usage(usage, actions, groups, prefix)


def main():
    description = textwrap.dedent(
        """
        Run the hades agent (Celery worker).

        All arguments except -c/--config and -A/--app are passed to the Celery
        worker as is. You may not provide the -A/--app argument.
        """
    )
    parser = ArgumentParser(description=description,
                            formatter_class=Formatter,
                            parents=[common_parser])
    parser.add_argument('-A', '--app', dest='app', help=argparse.SUPPRESS)
    args, argv = parser.parse_known_args()
    if args.config:
        os.environ['HADES_CONFIG'] = args.config
    app.config_from_object(load_config(args.config))
    if args.app:
        parser.error("You may not provide the -A/--app worker argument")
    argv.insert(0, parser.prog)
    argv.extend(['-A', 'hades.bin.agent:app'])
    return app.worker_main(argv)


if __name__ == '__main__':
    sys.exit(main())
else:
    app.config_from_object(load_config())
