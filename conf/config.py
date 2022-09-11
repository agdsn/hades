from collections import OrderedDict
import netaddr

HADES_SITE_NAME = 'dev'
HADES_SITE_NODE_ID = 'dev-01'
BROKER_URL = 'amqp://guest:guest@127.0.0.1/hades'
HADES_CREATE_DUMMY_INTERFACES = True
HADES_BRIDGE_SERVICE_INTERFACES = True
HADES_LOCAL_MASTER_DATABASE = True
HADES_AUTH_INTERFACE = 'auth'
HADES_UNAUTH_INTERFACE = 'unauth'
HADES_VRRP_INTERFACE = 'vrrp'
HADES_VRRP_LISTEN_AUTH = netaddr.IPNetwork('192.168.32.2/24')
HADES_VRRP_LISTEN_ROOT = netaddr.IPNetwork('192.168.32.1/24')
HADES_VRRP_LISTEN_UNAUTH = netaddr.IPNetwork('192.168.32.3/24')
HADES_VRRP_PASSWORD = 'correcthorsebatterystaple'
HADES_RADIUS_LISTEN = (
    netaddr.IPNetwork('10.10.10.240/24'),
)
HADES_RADIUS_INTERFACE = 'radius'
HADES_RADIUS_LOCALHOST_SECRET = 'testing123'
HADES_CONTACT_ADDRESSES = OrderedDict([
    ("Support", "support@example.com"),
])
HADES_USER_NETWORKS = {
    'Wu9': netaddr.IPNetwork('141.30.202.1/24'),
    'Wu3': netaddr.IPNetwork('141.30.223.1/24'),
    'Wu1': netaddr.IPNetwork('141.30.224.1/24'),
    'Wu11': netaddr.IPNetwork('141.30.216.1/24'),
    'Wu7': netaddr.IPNetwork('141.30.222.1/24'),
    'Zw41': netaddr.IPNetwork('141.30.226.1/23'),
    'Wu5': netaddr.IPNetwork('141.30.228.1/24'),
    'UNEP': netaddr.IPNetwork('141.30.242.129/28'),
    'Bor34': netaddr.IPNetwork('141.76.121.1/24'),
    'Ger38': netaddr.IPNetwork('141.76.124.1/24'),
    'Bu22': netaddr.IPNetwork('141.30.204.1/24'),
    'Bu24': netaddr.IPNetwork('141.30.205.1/24'),
    'HSS46a': netaddr.IPNetwork('141.30.217.1/24'),
    'HSS46b': netaddr.IPNetwork('141.30.234.1/25'),
    'HSS48a': netaddr.IPNetwork('141.30.218.1/24'),
    'HSS48b': netaddr.IPNetwork('141.30.215.129/25'),
    'HSS50': netaddr.IPNetwork('141.30.219.1/24'),
    'Zeu1fa': netaddr.IPNetwork('141.30.234.129/26'),
    'Zeu1fb': netaddr.IPNetwork('141.30.234.193/27 '),
}
HADES_POSTGRESQL_USER_MAPPINGS = {
    'hades-agent': {
        'user': 'fdw',
        'password': 'correcthorsebatterystaple',
    },
    'hades-database': {
        'user': 'fdw',
        'password': 'correcthorsebatterystaple',
    },
    'hades-portal': {
        'user': 'fdw',
        'password': 'correcthorsebatterystaple',
    },
    'hades-radius': {
        'user': 'fdw',
        'password': 'correcthorsebatterystaple',
    },
}
HADES_UNAUTH_WHITELIST_DNS = ('agdsn.de',)
HADES_AUTH_DNS_ALTERNATIVE_ZONES = {
    'example.com': {
        'type': 'transparent',
        'records': [
            {
                'name': 'www.example.com',
                'ttl': 60*60,
                'class': 'IN',
                'type': 'A',
                'data': '127.0.0.1'
            },
        ]
    }
}
HADES_CUSTOM_IPTABLES_INPUT_RULES = [
    # Expose PostgreSQL
    "-p tcp -m tcp --dport 5432 -j ACCEPT",
    # Expose RabbitMQ AMQP socket
    "-p tcp -m tcp --dport 5672 -j ACCEPT",
    # Expose RabbitMQ HTTP management interface
    "-p tcp -m tcp --dport 15672 -j ACCEPT",
]
HADES_POSTGRESQL_LISTEN = [netaddr.IPNetwork("0.0.0.0/0")]
