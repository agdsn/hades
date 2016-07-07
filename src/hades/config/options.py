import collections
import random
import string
from datetime import timedelta

import netaddr

from hades.config import check, compute
from hades.config.base import Option


###################
# General options #
###################


class HADES_SITE_NAME(Option):
    """Name of the site"""
    type = str


class HADES_SITE_NODE_ID(Option):
    """Unique name of the site node instance"""
    type = str


class HADES_REAUTHENTICATION_INTERVAL(Option):
    """RADIUS periodic reauthentication interval"""
    default = timedelta(seconds=300)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_RETENTION_INTERVAL(Option):
    """RADIUS postauth and accounting data retention interval"""
    default = timedelta(days=1)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_CONTACT_ADDRESSES(Option):
    """Contact addresses displayed on the captive portal page"""
    type = collections.Mapping


class HADES_USER_NETWORKS(Option):
    """
    Public networks of authenticated users.

    Dictionary of networks. Keys are unique identifiers of the network,
    values are netaddr.IPNetworks objects
    """
    type = collections.Mapping
    static_check = check.all(check.not_empty,
                             check.mapping(value_check=check.network_ip))


#############################
# Network namespace options #
#############################


class HADES_NETNS_MAIN_AUTH_LISTEN(Option):
    default = netaddr.IPNetwork('172.18.0.0/31')
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_NETNS_AUTH_LISTEN(Option):
    default = netaddr.IPNetwork('172.18.0.1/31')
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_NETNS_MAIN_UNAUTH_LISTEN(Option):
    default = netaddr.IPNetwork('172.18.0.2/31')
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_NETNS_UNAUTH_LISTEN(Option):
    default = netaddr.IPNetwork('172.18.0.3/31')
    static_check = check.network_ip
    runtime_check = check.address_exists


#######################
# Hades Agent options #
#######################


class HADES_AGENT_USER(Option):
    """User of the site node agent"""
    default = 'hades-agent'
    type = str
    runtime_check = check.user_exists


class HADES_AGENT_GROUP(Option):
    """Group of the site node agent"""
    default = 'hades-agent'
    type = str
    runtime_check = check.group_exists


class HADES_AGENT_HOME(Option):
    """Working directory of the site node agent"""
    default = '/var/lib/hades/agent'
    type = str
    runtime_check = check.directory_exists


######################
# PostgreSQL options #
######################


class HADES_POSTGRESQL_USER(Option):
    """User the PostgreSQL database is running as"""
    type = str
    default = 'postgres'


class HADES_POSTGRESQL_GROUP(Option):
    """Group the PostgreSQL database is running as"""
    type = str
    default = 'postgres'


class HADES_POSTGRESQL_DATABASE(Option):
    """Name of the PostgreSQL database on the site node"""
    default = 'hades'
    type = str


class HADES_POSTGRESQL_SOCKET_DIRECTORY(Option):
    """Path to the PostgreSQL socket directory"""
    default = '/run/hades/database'
    type = str
    runtime_check = check.directory_exists


class HADES_POSTGRESQL_PORT(Option):
    """Port and socket name of the PostgresSQL database"""
    default = 5432
    type = int
    static_check = check.between(1, 65535)


class HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE(Option):
    """
    If set to a string, create and use a local “foreign” database with that
    name.
    """
    type = str


class HADES_POSTGRESQL_FOREIGN_SERVER_FDW(Option):
    """
    Name of the foreign data wrapper extensions that should be used.

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    default = 'postgres_fdw'
    type = str


class HADES_POSTGRESQL_FOREIGN_SERVER_OPTIONS(Option):
    """
    Foreign data wrapper specific server options

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_SERVER_TYPE(Option):
    """
    Foreign data wrapper specific server type

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    type = str


class HADES_POSTGRESQL_FOREIGN_SERVER_VERSION(Option):
    """
    Foreign data wrapper specific server version

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    type = str


class HADES_POSTGRESQL_FOREIGN_TABLE_GLOBAL_OPTIONS(Option):
    """
    Foreign data wrapper options that are set on each foreign table.
    The options can be overridden with table specific options.

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    default = {
        'dbname': 'hades',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_DHCPHOST_IPADDRESS_STRING(Option):
    """
    Whether the ipaddress column of the foreign dhcphost table has a string type
    """
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_DHCPHOST_MAC_STRING(Option):
    """Whether the mac column of the foreign dhcphost table has a string type"""
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_DHCPHOST_OPTIONS(Option):
    """
    Foreign data wrapper options for the dhcphost table

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'dhcphost',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_NAS_OPTIONS(Option):
    """
    Foreign data wrapper options for the nas table

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'nas',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADCHECK_NASIPADDRESS_STRING(Option):
    """
    Whether the nasipaddress column of the foreign radcheck table has a string
    type
    """
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_RADCHECK_OPTIONS(Option):
    """
    Foreign data wrapper options for the radcheck table

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'radcheck',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADGROUPCHECK_OPTIONS(Option):
    """
    Foreign data wrapper options for the radgroupcheck table

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'radgroupcheck',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADGROUPREPLY_OPTIONS(Option):
    """
    Foreign data wrapper options for the radgroupreply table

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'radgroupreply',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADREPLY_NASIPADDRESS_STRING(Option):
    """
    Whether the nasipaddress column of the foreign radgroupcheck table has a
    string type
    """
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_RADREPLY_OPTIONS(Option):
    """
    Foreign data wrapper options for the radreply table

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'radreply',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADUSERGROUP_NASIPADDRESS_STRING(Option):
    """
    Whether the nasipaddress column of the foreign radgroupcheck table has a
    string type
    """
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_RADUSERGROUP_OPTIONS(Option):
    """
    Foreign data wrapper options for the radusergroup table

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'radusergroup',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_USER_MAPPINGS(Option):
    """
    User mappings from local database users to users on the foreign database
    server

    If HADES_POSTGRESQL_LOCAL_FOREIGN_DATABASE is set, this option is ignored.
    """
    type = collections.Mapping
    static_check = check.all(
        check.user_mapping_for_user_exists('HADES_POSTGRESQL_USER'),
        check.user_mapping_for_user_exists('HADES_AGENT_USER'),
    )


########################
# Hades Portal options #
########################


class HADES_PORTAL_DOMAIN(Option):
    """Fully qualified domain name of the captive portal"""
    default = 'captive-portal.agdsn.de'
    type = str


class HADES_PORTAL_URL(Option):
    """URL of the landing page of the captive portal"""
    default = compute.deferred_format("http://{}/", HADES_PORTAL_DOMAIN)
    type = str


class HADES_PORTAL_USER(Option):
    """User of the web server and captive portal application"""
    default = 'hades-portal'
    runtime_check = check.user_exists


class HADES_PORTAL_GROUP(Option):
    """Group of the web server and captive portal application"""
    default = 'hades-portal'
    runtime_check = check.group_exists


class HADES_PORTAL_HOME(Option):
    """Working directory of the captive portal application"""
    default = '/var/lib/hades/unauth-portal'
    runtime_check = check.directory_exists


class HADES_PORTAL_NGINX_WORKERS(Option):
    """Number of nginx worker processes"""
    default = 4
    type = int
    static_check = check.greater_than(0)


class HADES_PORTAL_SSL_CERTIFICATE(Option):
    """Path to the SSL certificate of the captive portal"""
    default = '/etc/ssl/certs/ssl-cert-snakeoil.pem'
    runtime_check = check.file_exists


class HADES_PORTAL_SSL_CERTIFICATE_KEY(Option):
    """Path to the SSL certificate key of the captive portal"""
    default = '/etc/ssl/private/ssl-cert-snakeoil.key'
    runtime_check = check.file_exists


class HADES_PORTAL_UWSGI_SOCKET(Option):
    """Path to uWSGI socket of the captive portal"""
    default = '/run/hades/unauth-portal/uwsgi.sock'
    type = str
    runtime_check = check.file_creatable


class HADES_PORTAL_UWSGI_WORKERS(Option):
    """Number of uWSGI worker processes"""
    default = 4
    type = int
    static_check = check.greater_than(0)


###############################
# Authenticated users options #
###############################


class HADES_AUTH_DNSMASQ_USER(Option):
    """
    User of the dnsmasq instance for authenticated users and the
    SignalProxyDaemon
    """
    default = compute.equal_to(HADES_AGENT_USER)
    type = str
    runtime_check = check.user_exists


class HADES_AUTH_DNSMASQ_GROUP(Option):
    """
    Group of the dnsmasq instance for authenticated users and the SignalProxyDaemon
    """
    default = compute.equal_to(HADES_AGENT_GROUP)
    type = str
    runtime_check = check.group_exists


class HADES_AUTH_DNSMASQ_PID_FILE(Option):
    """
    Path of the PID file of the dnsmasq instance for authenticated users.
    """
    default = "/run/hades/auth-dhcp/dnsmasq.pid"
    type = str
    runtime_check = check.file_creatable


class HADES_AUTH_DNSMASQ_HOSTS_FILE(Option):
    """
    Path to the DHCP hosts file of the dnsmasq instance for authenticated users.
    """
    default = "/var/lib/hades/auth-dhcp/dnsmasq.hosts"
    type = str
    runtime_check = check.file_creatable


class HADES_AUTH_DNSMASQ_LEASE_FILE(Option):
    """
    Path to the DHCP lease file of the dnsmasq instance for authenticated users.
    """
    default = "/var/lib/hades/auth-dhcp/dnsmasq.leases"
    type = str
    runtime_check = check.file_creatable


class HADES_AUTH_DHCP_DOMAIN(Option):
    """DNS domain of authenticated users"""
    default = 'users.agdsn.de'
    type = str


class HADES_AUTH_DHCP_LEASE_TIME(Option):
    """DHCP Lease time for authenticated users"""
    default = timedelta(hours=24)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_UNBOUND_USER(Option):
    """User of the unbound daemon"""
    default = 'hades-auth-dns'
    type = str
    runtime_check = check.user_exists


class HADES_UNBOUND_GROUP(Option):
    """User of the unbound daemon"""
    default = 'hades-auth-dns'
    type = str
    runtime_check = check.group_exists


class HADES_AUTH_LISTEN(Option):
    """IP and network to listen on for requests from authenticated users"""
    default = netaddr.IPNetwork('10.66.67.10/24')
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_AUTH_INTERFACE(Option):
    """Interface where requests from the authenticated users arrive. Interface
    must not be attached directly to the users networks."""
    type = str
    runtime_check = check.interface_exists


class HADES_AUTH_ALLOWED_TCP_PORTS(Option):
    """Allowed TCP destination ports for unauthenticated users"""
    type = collections.Iterable
    default = (53, 80, 443)


class HADES_AUTH_ALLOWED_UDP_PORTS(Option):
    """Allowed UDP destination ports for unauthenticated users"""
    type = collections.Iterable
    default = (53, 67)


#################################
# Unauthenticated users options #
#################################


class HADES_UNAUTH_DNSMASQ_USER(Option):
    """
    User of the dnsmasq instance for unauthenticated users
    """
    default = "dnsmasq"
    type = str
    runtime_check = check.user_exists


class HADES_UNAUTH_DNSMASQ_GROUP(Option):
    """
    Group of the dnsmasq instance for unauthenticated users
    """
    default = "nogroup"
    type = str
    runtime_check = check.group_exists


class HADES_UNAUTH_DNSMASQ_PID_FILE(Option):
    """
    Path of the PID file of the dnsmasq instance for unauthenticated users.
    """
    default = "/run/hades/unauth-dns/dnsmasq.pid"
    type = str
    runtime_check = check.file_creatable


class HADES_UNAUTH_DHCP_LEASE_TIME(Option):
    """DHCP lease time in the unauth VLAN"""
    default = timedelta(minutes=2)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_UNAUTH_INTERFACE(Option):
    """Interface attached to the unauth VLAN"""
    type = str
    runtime_check = check.interface_exists


class HADES_UNAUTH_LISTEN(Option):
    """IP and network to listen for unauthenticated users"""
    default = netaddr.IPNetwork('10.66.0.1/19')
    type = netaddr.IPNetwork
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_UNAUTH_ALLOWED_TCP_PORTS(Option):
    """Allowed TCP destination ports for unauthenticated users"""
    type = collections.Iterable
    default = (53, 80, 443)


class HADES_UNAUTH_ALLOWED_UDP_PORTS(Option):
    """Allowed UDP destination ports for unauthenticated users"""
    type = collections.Iterable
    default = (53, 67)


class HADES_UNAUTH_CAPTURED_TCP_PORTS(Option):
    """
    All traffic destined to these TCP ports is transparently redirected
    (captured) to the unauth listen address of the site node
    """
    type = collections.Iterable
    default = (53, 80, 443)


class HADES_UNAUTH_CAPTURED_UDP_PORTS(Option):
    """
    All traffic destined to these UDP ports is transparently redirected
    (captured) to the unauth listen address of the site node
    """
    type = collections.Iterable
    default = (53,)


class HADES_UNAUTH_DHCP_RANGE(Option):
    """DHCP range for the unauth VLAN. Must be contained within the
    HADES_UNAUTH_LISTEN network."""
    default = netaddr.IPRange('10.66.0.10', '10.66.31.254')
    type = netaddr.IPRange
    static_check = check.ip_range_in_network(HADES_UNAUTH_LISTEN.__name__)


class HADES_UNAUTH_WHITELIST_DNS(Option):
    """List of DNS names which are whitelisted for unauthenticated users.
    """
    default = ()
    type = collections.Iterable


class HADES_UNAUTH_WHITELIST_IPSET(Option):
    """Name of ipset for whitelisted IPs.
    """
    default = "unauth_whitelist"
    type = str


##################
# RADIUS options #
##################


class HADES_RADIUS_USER(Option):
    """User of the freeRADIUS server"""
    default = 'freerad'
    type = str
    runtime_check = check.user_exists


class HADES_RADIUS_GROUP(Option):
    """Group of the freeRADIUS server"""
    default = 'freerad'
    type = str
    runtime_check = check.group_exists


class HADES_RADIUS_LISTEN(Option):
    """IP and network the RADIUS server is listening on"""
    type = netaddr.IPNetwork
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_RADIUS_INTERFACE(Option):
    """Interface the RADIUS server is listening on"""
    type = str
    runtime_check = check.interface_exists


class HADES_RADIUS_AUTHENTICATION_PORT(Option):
    """RADIUS authentication port"""
    type = int
    default = 1812


class HADES_RADIUS_ACCOUNTING_PORT(Option):
    """RADIUS accounting port"""
    type = int
    default = 1813


class HADES_RADIUS_LOCALHOST_SECRET(Option):
    """Shared secret for the localhost RADIUS client"""
    type = str


class HADES_RADIUS_DATABASE_FAIL_ACCEPT(Option):
    """Send Access-Accept packets if the sql module fails"""
    type = bool
    default = True


class HADES_RADIUS_DATABASE_FAIL_REPLY_ATTRIBUTES(Option):
    """
    Reply attributes that will be set in Access-Accept packets if the sql
    module fails.

    The attribute value must be specified in proper freeRADIUS syntax. That
    means that string replies should be enclosed in single quotes.
    """
    type = collections.Mapping
    default = {
        'Reply-Message': "'database_down'",
    }


##########################
# Gratuitous ARP options #
##########################


class HADES_GRATUITOUS_ARP_INTERVAL(Option):
    """
    Period in which gratuitous ARP requests are broadcasted to notify
    a) clients of the MAC address of current master site node instance
    b) clients switching from the auth to the unauth VLAN of the new gateway MAC
    """
    type = timedelta
    default = timedelta(seconds=1)


################
# VRRP options #
################


class HADES_PRIORITY(Option):
    """
    Priority of the site node instance.
    The available instance with the highest priority becomes master.
    """
    type = int
    default = 100
    static_check = check.between(1, 254)


class HADES_INITIAL_MASTER(Option):
    """Flag that indicates if site node instance starts in master state"""
    type = bool
    default = False


class HADES_VRRP_INTERFACE(Option):
    """Interface for VRRP communication"""
    type = str
    runtime_check = check.interface_exists


class HADES_VRRP_BRIDGE(Option):
    """Interface name for VRRP bridge (created if necessary)"""
    type = str
    default = 'br-vrrp'
    static_check = check.not_empty


class HADES_VRRP_LISTEN_AUTH(Option):
    """IP and network for VRRP communication (auth instance)"""
    type = netaddr.IPNetwork
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_VRRP_LISTEN_RADIUS(Option):
    """IP and network for VRRP communication (radius instance)"""
    type = netaddr.IPNetwork
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_VRRP_LISTEN_UNAUTH(Option):
    """IP and network for VRRP communication (unauth instance)"""
    type = netaddr.IPNetwork
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_VRRP_PASSWORD(Option):
    """
    Shared secret to authenticate VRRP messages between site node instances.
    """
    type = str


class HADES_VRRP_VIRTUAL_ROUTER_ID_AUTH(Option):
    """Virtual router ID used by Hades (auth instance)"""
    type = int
    default = 66
    static_check = check.between(0, 255)


class HADES_VRRP_VIRTUAL_ROUTER_ID_RADIUS(Option):
    """Virtual router ID used by Hades (radius instance)"""
    type = int
    default = 67
    static_check = check.between(0, 255)


class HADES_VRRP_VIRTUAL_ROUTER_ID_UNAUTH(Option):
    """Virtual router ID used by Hades (unauth instance)"""
    type = int
    default = 68
    static_check = check.between(0, 255)


class HADES_VRRP_ADVERTISEMENT_INTERVAL(Option):
    """Interval between VRRP advertisements"""
    type = timedelta
    default = timedelta(seconds=5)
    static_check = check.greater_than(timedelta(0))


class HADES_VRRP_PREEMPTION_DELAY(Option):
    """
    Delay before a MASTER transitions to BACKUP when a node with a higher
    priority comes online
    """
    type = timedelta
    default = timedelta(seconds=30)
    static_check = check.between(timedelta(seconds=0), timedelta(seconds=1000))


################
# Test options #
################


class HADES_CREATE_DUMMY_INTERFACES(Option):
    """Create dummy interfaces if interfaces do not exist"""
    type = bool
    default = False


#################
# Flask options #
#################


class SECRET_KEY(Option):
    """
    Flask secret key
    The current portal application does not any feature of Flask that would
    require a persistent secret key, therefore a random key is generated by
    default
    """
    default = ''.join(random.choice(string.ascii_letters + string.digits)
                      for i in range(64))
    type = str


class DEBUG(Option):
    """Flask debug mode flag"""
    defaults = False
    type = bool


#######################
# Flask-Babel options #
#######################


class BABEL_DEFAULT_LOCALE(Option):
    """Default locale of the portal application"""
    default = 'de_DE'
    type = str


class BABEL_DEFAULT_TIMEZONE(Option):
    """Default timezone of the portal application"""
    default = 'Europe/Berlin'
    type = str


############################
# Flask-SQLAlchemy options #
############################


class SQLALCHEMY_DATABASE_URI(Option):
    default = compute.deferred_format('postgresql:///{}?host={}&port={}',
                                      HADES_POSTGRESQL_DATABASE,
                                      HADES_POSTGRESQL_SOCKET_DIRECTORY,
                                      HADES_POSTGRESQL_PORT)
    type = str


##################
# Celery options #
##################


class BROKER_URL(Option):
    type = str


class BROKER_CONNECTION_MAX_RETRIES(Option):
    """
    Maximum number of retries before giving up re-establishing the
    connection to the broker.

    Set to zero to retry forever in case of longer partitions between sites
    and the main database.
    """
    default = 0
    type = int


class CELERY_ENABLE_UTC(Option):
    default = True
    type = bool


class CELERY_TIMEZONE(Option):
    default = 'UTC'
    type = str


class CELERY_DEFAULT_QUEUE(Option):
    default = compute.deferred_format("hades-site-{}", HADES_SITE_NAME)
    type = str


class CELERY_ACCEPT_CONTENT(Option):
    default = ['json', 'msgpack', 'pickle', 'yaml']
    type = collections.Sequence


class CELERY_TASK_SERIALIZER(Option):
    default = 'pickle'
    type = str


class CELERY_RESULT_BACKEND(Option):
    default = 'rpc://'
    type = str


class CELERYBEAT_SCHEDULE(Option):
    default = {
        'refresh': {
            'task': 'hades.agent.refresh',
            'schedule': timedelta(minutes=5),
        },
        'delete-old': {
            'task': 'hades.agent.delete_old',
            'schedule': timedelta(hours=1),
        },
    }


class CELERYBEAT_SCHEDULE_FILENAME(Option):
    default = '/var/lib/hades/agent/celerybeat-schedule'
