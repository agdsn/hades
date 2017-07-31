from collections import OrderedDict
import netaddr

HADES_SITE_NAME = 'dev'
BROKER_URL = 'amqp://hades:hades@172.17.42.1'
HADES_SITE_NODE_ID = 'dev-01'
HADES_CREATE_DUMMY_INTERFACES = True
HADES_BRIDGE_SERVICE_INTERFACES = True
HADES_LOCAL_MASTER_DATABASE = True
HADES_AUTH_INTERFACE = 'auth'
HADES_UNAUTH_INTERFACE = 'unauth'
HADES_VRRP_INTERFACE = 'vrrp'
HADES_VRRP_LISTEN_RADIUS = netaddr.IPNetwork('192.168.32.1/24')
HADES_VRRP_LISTEN_AUTH = netaddr.IPNetwork('192.168.32.2/24')
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
    'news.com': {
        'type': 'transparent',
        'records': [
            {
                'name': 'fake.news.com',
                'ttl': 60*60,
                'class': 'IN',
                'type': 'A',
                'data': '127.0.0.1'
            },
        ]
    }
}
