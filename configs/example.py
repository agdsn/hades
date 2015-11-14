from collections import OrderedDict
import netaddr

HADES_SITE_NAME = 'dev'
HADES_SITE_NODE_ID = 'dev-01'
BROKER_URL = 'amqp://hades:hades@172.17.42.1'
HADES_CREATE_DUMMY_INTERFACES = True
HADES_AUTH_INTERFACE = 'auth'
HADES_UNAUTH_INTERFACE = 'unauth'
HADES_VRRP_INTERFACE = 'vrrp'
HADES_VRRP_LISTEN = netaddr.IPNetwork('192.168.32.1/24')
HADES_VRRP_PASSWORD = 'correcthorsebatterystaple'
HADES_RADIUS_LISTEN = netaddr.IPNetwork('10.10.10.240/8')
HADES_RADIUS_INTERFACE = 'radius'
HADES_RADIUS_LOCALHOST_SECRET = 'testing123'
HADES_CONTACT_ADDRESSES = OrderedDict([
    ("Support", "support@example.com"),
])
HADES_POSTGRESQL_FOREIGN_TABLE_DHCPHOST_MAC_STRING = True
HADES_POSTGRESQL_FOREIGN_TABLE_DHCPHOST_IPADDRESS_STRING = True
HADES_POSTGRESQL_FOREIGN_TABLE_RADCHECK_NASIPADDRESS_STRING = True
HADES_POSTGRESQL_FOREIGN_TABLE_RADREPLY_NASIPADDRESS_STRING = True
HADES_POSTGRESQL_FOREIGN_TABLE_RADUSERGROUP_NASIPADDRESS_STRING = True
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
HADES_POSTGRESQL_FOREIGN_SERVER_FDW = 'mysql_fdw'
HADES_POSTGRESQL_FOREIGN_SERVER_OPTIONS = {
    'host': '172.17.0.1',
    'port': '3306',
    'init_command': 'SET lock_wait_timeout = 5;'
}
HADES_POSTGRESQL_FOREIGN_TABLE_GLOBAL_OPTIONS = {
    'dbname': 'radius',
}
HADES_POSTGRESQL_USER_MAPPINGS = {
    'hades-agent': {
        'password': '',
        'username': 'hades-agent',
    },
    'postgres': {
        'password': '',
        'username': 'hades-agent',
    },
}
