#!/usr/bin/env python3
"""Keepalived notification receiver.

Invoked by keepalived, if the state of VRRP instances changes.
"""
import logging
import os
import sys
import textwrap
import typing as t

import kombu

from hades.agent import create_app
from hades.common.cli import ArgumentParser, common_parser, setup_cli_logging
from hades.common.exc import handles_setup_errors
from hades.config import (
    Config,
    load_config,
    Option,
)
from hades.config.options import (
    HADES_CELERY_NODE_QUEUE,
    HADES_CELERY_NOTIFY_EXCHANGE,
    HADES_CELERY_NOTIFY_EXCHANGE_TYPE,
    HADES_CELERY_ROUTING_KEY_MASTERS_ALL,
    HADES_CELERY_ROUTING_KEY_MASTERS_SITE,
    HADES_CELERY_ROUTING_KEY_MASTERS_SITE_AUTH,
    HADES_CELERY_ROUTING_KEY_MASTERS_SITE_ROOT,
    HADES_CELERY_ROUTING_KEY_MASTERS_SITE_UNAUTH,
    HADES_CELERY_RPC_EXCHANGE,
    HADES_CELERY_RPC_EXCHANGE_TYPE,
)

logger = logging.getLogger('hades.bin.vrrp_notify')
INSTANCES: t.Dict[str, t.Type[Option]] = {
    "hades-auth": HADES_CELERY_ROUTING_KEY_MASTERS_SITE_AUTH,
    "hades-root": HADES_CELERY_ROUTING_KEY_MASTERS_SITE_ROOT,
    "hades-unauth": HADES_CELERY_ROUTING_KEY_MASTERS_SITE_UNAUTH,
}


def update_bindings(config: Config, name: str, state: str) -> None:
    app = create_app(config)
    queue_name = config[HADES_CELERY_NODE_QUEUE]
    rpc_exchange = kombu.Exchange(
        config[HADES_CELERY_RPC_EXCHANGE],
        config[HADES_CELERY_RPC_EXCHANGE_TYPE],
    )
    notify_exchange = kombu.Exchange(
        config[HADES_CELERY_NOTIFY_EXCHANGE],
        config[HADES_CELERY_NOTIFY_EXCHANGE_TYPE],
    )
    instance_key = config[INSTANCES[name]]
    bindings = {
        rpc_exchange: {instance_key},
        notify_exchange: {
            config[HADES_CELERY_ROUTING_KEY_MASTERS_ALL],
            config[HADES_CELERY_ROUTING_KEY_MASTERS_SITE],
            instance_key,
        },
    }
    with app.connection(connect_timeout=1) as connection:
        connection.ensure_connection(max_retries=0, timeout=1)
        queue = app.amqp.queues[queue_name]
        bound_queue = queue.bind(connection.default_channel)
        bound_queue.declare()
        if state == 'MASTER':
            for exchange, keys in bindings.items():
                bound_exchange = exchange.bind(connection.default_channel)
                bound_exchange.declare()
                for key in keys:
                    logger.info(
                        "Binding node queue %s to exchange %s "
                        "with routing key %s",
                        queue_name,
                        exchange.name,
                        key,
                    )
                    bound_queue.bind_to(
                        exchange=bound_exchange, routing_key=key
                    )
        else:
            for exchange, keys in bindings.items():
                bound_exchange = exchange.bind(connection.default_channel)
                bound_exchange.declare()
                for key in keys:
                    logger.info(
                        "Unbinding node queue %s from exchange %s "
                        "with routing key %s",
                        queue_name,
                        exchange.name,
                        key,
                    )
                    bound_queue.unbind_from(
                        exchange=rpc_exchange, routing_key=key
                    )


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
        choices=INSTANCES.keys(),
    )
    parser.add_argument('state', choices=['MASTER', 'BACKUP', 'FAULT'],
                        help="The state it's transitioning to")
    parser.add_argument('priority', type=int, help="The priority value")
    return parser



@handles_setup_errors(logger)
def main() -> int:
    parser = create_parser()
    args = parser.parse_args()
    setup_cli_logging(parser.prog, args)
    logger.fatal("Transitioning %s to %s with priority %d", args.name,
                 args.state, args.priority)
    config = load_config(args.config, runtime_checks=True)
    update_bindings(config, args.name, args.state)
    return os.EX_OK


if __name__ == '__main__':
    sys.exit(main())
