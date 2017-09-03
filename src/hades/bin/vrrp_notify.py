import logging
import sys
import textwrap
from contextlib import closing

import kombu

from hades.agent import app
from hades.common.cli import ArgumentParser, parser as common_parser
from hades.config.loader import load_config, get_config
from hades.config.options import CeleryOption

logger = logging.getLogger('hades.bin.vrrp_notify')


# noinspection PyUnusedLocal
def notify_auth(state, priority) -> int:
    return 0


# noinspection PyUnusedLocal
def notify_radius(state, priority) -> int:
    config = get_config(runtime_checks=True)
    queue_name = config.HADES_CELERY_NODE_QUEUE
    exchange_name = config.HADES_CELERY_RPC_EXCHANGE
    exchange_type = config.HADES_CELERY_RPC_EXCHANGE_TYPE
    routing_key = config.HADES_CELERY_SITE_ROUTING_KEY
    exchange = kombu.Exchange(exchange_name, exchange_type)
    with closing(app.connection(connect_timeout=1)) as connection:
        queue = app.amqp.queues[queue_name]
        bound_queue = queue.bind(connection.default_channel)
        if state == 'MASTER':
            logger.info("Binding site node queue %s to RPC exchange %s "
                        "with site routing key %s",
                        queue_name, exchange_name, routing_key)
            bound_queue.bind_to(exchange=exchange, routing_key=routing_key)
        else:
            logger.info("Unbinding site node queue %s from RPC exchange %s "
                        "with site routing key %s",
                        queue_name, exchange_name, routing_key)
            bound_queue.unbind_from(exchange=exchange, routing_key=routing_key)
    return 0


# noinspection PyUnusedLocal
def notify_unauth(state, priority) -> int:
    return 0


def main() -> int:
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
    parser.add_argument('name', help="The name of the group or instance")
    parser.add_argument('state', choices=['MASTER', 'BACKUP', 'FAULT'],
                        help="The state it's transitioning to")
    parser.add_argument('priority', type=int, help="The priority value")
    args = parser.parse_args()
    logger.fatal("Transitioning %s to %s with priority %d", args.name,
                 args.state, args.priority)
    app.config_from_object(
        load_config(args.config, runtime_checks=True, option_cls=CeleryOption))
    if args.name == 'hades-auth':
        return notify_auth(args.state, args.priority)
    elif args.name == 'hades-radius':
        return notify_radius(args.state, args.priority)
    elif args.name == 'hades-unauth':
        return notify_unauth(args.state, args.priority)


if __name__ == '__main__':
    sys.exit(main())
