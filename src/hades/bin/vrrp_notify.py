#!/usr/bin/env python3
"""Keepalived notification receiver.

Invoked by keepalived, if the state of VRRP instances changes.
"""
import logging
import os
import sys
import textwrap
import typing as t
from contextlib import closing

import kombu

from hades.agent import create_app
from hades.common.cli import ArgumentParser, common_parser
from hades.config import Config, ConfigError, load_config, print_config_error

logger = logging.getLogger('hades.bin.vrrp_notify')


# noinspection PyUnusedLocal
def notify_auth(config: Config, state: str, priority: int) -> int:
    return os.EX_OK


# noinspection PyUnusedLocal
def notify_root(config: Config, state: str, priority: int) -> int:
    app = create_app(config)
    queue_name = config.HADES_CELERY_NODE_QUEUE
    exchange_name = config.HADES_CELERY_RPC_EXCHANGE
    exchange_type = config.HADES_CELERY_RPC_EXCHANGE_TYPE
    routing_key = config.HADES_CELERY_ROUTING_KEY_MASTERS_SITE
    exchange = kombu.Exchange(exchange_name, exchange_type, no_declare=True)
    with closing(app.connection(connect_timeout=1)) as connection:
        queue = app.amqp.queues[queue_name]
        bound_queue = queue.bind(connection.default_channel)
        if state == 'MASTER':
            logger.info(
                "Binding node queue %s to RPC exchange %s with site masters "
                "routing key %s",
                queue_name,
                exchange_name,
                routing_key,
            )
            bound_queue.bind_to(exchange=exchange, routing_key=routing_key)
        else:
            logger.info(
                "Unbinding node queue %s from RPC exchange %s with site "
                "masters routing key %s",
                queue_name,
                exchange_name,
                routing_key,
            )
            bound_queue.unbind_from(exchange=exchange, routing_key=routing_key)
    return os.EX_OK


# noinspection PyUnusedLocal
def notify_unauth(config: Config, state: str, priority: int) -> int:
    return os.EX_OK


HANDLERS: t.Dict[str, t.Callable[[Config, str, int], int]] = {
    "hades-auth": notify_auth,
    "hades-root": notify_root,
    "hades-unauth": notify_unauth,
}


def create_parser() -> ArgumentParser:
    description = textwrap.dedent(
        """
        Hades keepalived VRRP notify script.
        
        This script is called by keepalived, if a VRRP instance's state changes.
        """
    )
    parser = ArgumentParser(description=description,
                            parents=[common_parser])
    parser.add_argument('type', choices=['GROUP', 'INSTANCE'],
                        help="Type indication")
    parser.add_argument(
        "name",
        help="The name of the group or instance",
        choices=HANDLERS.keys(),
    )
    parser.add_argument('state', choices=['MASTER', 'BACKUP', 'FAULT'],
                        help="The state it's transitioning to")
    parser.add_argument('priority', type=int, help="The priority value")
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    logger.fatal("Transitioning %s to %s with priority %d", args.name,
                 args.state, args.priority)
    try:
        config = load_config(args.config, runtime_checks=True)
    except ConfigError as e:
        print_config_error(e)
        return os.EX_CONFIG
    return HANDLERS[args.name](config, args.state, args.priority)


if __name__ == '__main__':
    sys.exit(main())
