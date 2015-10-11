from datetime import timedelta
import random
import string
import collections

import netaddr

from hades.config import check
from hades.config.check import ConfigError


class OptionMeta(type):
    """Metaclass for options. Classes that derive from options are registered
    in a global dict"""
    options = {}

    def __new__(mcs, what, bases=None, dict=None):
        class_ = super(OptionMeta, mcs).__new__(mcs, what, bases, dict)
        mcs.options[what] = class_
        return class_


class Option(object, metaclass=OptionMeta):
    default = None
    type = None
    runtime_check = None
    static_check = None


def equal_to(other):
    if isinstance(other, type) and issubclass(other, Option):
        other_name = other.__name__
    elif isinstance(other, str):
        other_name = other
    else:
        raise TypeError("Expected Option subclass or str")

    def f(config, name):
        try:
            return config[other_name]
        except KeyError:
            raise ConfigError(name, "Can not set equal to option {}, option is"
                                    " not defined"
                              .format(other_name))
    return f


def deferred_format(fmt_string, *args, **kwargs):
    """
    Evaluate a format string using values from others config options.

    Names of options are given as positional arguments and the corresponding
    values can be referred to using numbers in the format string.
    Keywords arguments can be used as well to bind other option values to
    specific names that are available in the format string.
    :param fmt_string:
    :param args:
    :param kwargs:
    :return:
    """
    def f(config, name):
        try:
            fmt_args = tuple(config[a] for a in args)
            fmt_kwargs = {k: config[v] for k, v in kwargs}
        except KeyError as e:
            raise ConfigError(e.args[0], "Option is missing (required by {})"
                              .format(name)) from e
        return fmt_string.format(*fmt_args, **fmt_kwargs)
    return f


class HADES_SITE_NAME(Option):
    """Name of the site"""
    type = str


# Hades options
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


class HADES_FREERADIUS_USER(Option):
    """User of the freeRADIUS server"""
    default = 'freerad'
    type = str
    runtime_check = check.user_exists


class HADES_FREERADIUS_GROUP(Option):
    """User of the freeRADIUS server"""
    default = 'freerad'
    type = str
    runtime_check = check.group_exists


class HADES_POSTGRESQL_DATABASE(Option):
    """Name of the PostgreSQL database on the site node"""
    default = 'hades'
    type = str


class HADES_POSTGRESQL_SOCKET(Option):
    """Path to the PostgreSQL socket directory"""
    default = '/var/run/postgresql'
    type = str
    runtime_check = check.directory_exists


class HADES_POSTGRESQL_FOREIGN_SERVER_FDW(Option):
    """Name of the foreign data wrapper extensions that should be used"""
    default = 'mysql_fdw'
    type = str


class HADES_POSTGRESQL_FOREIGN_SERVER_OPTIONS(Option):
    """Foreign data wrapper specific server options"""
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_GLOBAL_OPTIONS(Option):
    """
    Foreign data wrapper options that are set on each foreign table.
    The options can be overridden with table specific options.
    """
    default = {
        'dbname': 'hades',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_DHCPHOST_OPTIONS(Option):
    """Foreign data wrapper options for the dhcphost table"""
    default = {
        'table_name': 'dhcphost',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_NAS_OPTIONS(Option):
    """Foreign data wrapper options for the nas table"""
    default = {
        'table_name': 'nas',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADCHECK_OPTIONS(Option):
    """Foreign data wrapper options for the radcheck table"""
    default = {
        'table_name': 'radcheck',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADGROUPCHECK_OPTIONS(Option):
    """Foreign data wrapper options for the radgroupcheck table"""
    default = {
        'table_name': 'radgroupcheck',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADGROUPREPLY_OPTIONS(Option):
    """Foreign data wrapper options for the radgroupreply table"""
    default = {
        'table_name': 'radgroupreply',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADREPLY_OPTIONS(Option):
    """Foreign data wrapper options for the radreply table"""
    default = {
        'table_name': 'radreply',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADUSERGROUP_OPTIONS(Option):
    """Foreign data wrapper options for the radusergroup table"""
    default = {
        'table_name': 'radusergroup',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_USER_MAPPINGS(Option):
    """User mappings from local database users to users on the foreign database
    server"""
    type = collections.Mapping
    static_check = check.user_mapping_for_user_exists('HADES_AGENT_USER')


class HADES_PORTAL_DOMAIN(Option):
    """Fully qualified domain name of the captive portal"""
    default = 'captive-portal.agdsn.de'
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
    default = '/var/lib/hades/portal'
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
    default = '/run/hades/portal/uwsgi.sock'
    type = str
    runtime_check = check.file_creatable


class HADES_PORTAL_UWSGI_WORKERS(Option):
    """Number of uWSGI worker processes"""
    default = 4
    type = int
    static_check = check.greater_than(0)


class HADES_REGULAR_DNSMASQ_USER(Option):
    """User of the regular dnsmasq instance and the SignalProxyDaemon"""
    default = equal_to(HADES_AGENT_USER)
    type = str
    runtime_check = check.user_exists


class HADES_REGULAR_DNSMASQ_GROUP(Option):
    """Group of the regular dnsmasq instance and the SignalProxyDaemon"""
    default = equal_to(HADES_AGENT_GROUP)
    type = str
    runtime_check = check.group_exists


class HADES_REGULAR_DNSMASQ_HOSTS_FILE(Option):
    """Path to the DHCP hosts file of the regular dnsmasq instance."""
    default = "/var/lib/hades/agent/regular-dnsmasq.hosts"
    type = str
    runtime_check = check.file_creatable


class HADES_REGULAR_DNSMASQ_LEASE_FILE(Option):
    """Path to the DHCP lease file of the regular dnsmasq instance."""
    default = "/var/lib/hades/agent/regular-dnsmasq.leases"
    type = str
    runtime_check = check.file_creatable


class HADES_REGULAR_DNSMASQ_SIGNAL_SOCKET(Option):
    """Path to the Unix socket of the SignalProxyDaemon"""
    default = '/run/hades/agent/regular-dnsmasq.sock'
    type = str
    runtime_check = check.file_creatable


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


class HADES_REGULAR_DHCP_DOMAIN(Option):
    """DNS domain returned in the DHCP replies to users in the regular VLANs"""
    default = 'users.agdsn.de'
    type = str


class HADES_REGULAR_DHCP_LEASE_TIME(Option):
    """DHCP Lease time in the the regular VLANs"""
    default = timedelta(hours=24)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_AUTH_LISTEN(Option):
    """IP and network to listen on for requests from authenticated users"""
    default = netaddr.IPNetwork('10.66.67.1/24')
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_AUTH_INTERFACE(Option):
    """Interface where requests from the authenticated users arrive. Interface
    must not be attached directly to the users networks."""
    type = str
    runtime_check = check.interface_exists


class HADES_AUTH_FWMARK(Option):
    """Iptables connmark/mark for connections from authenticated users."""
    type = int
    default = 1
    static_check = check.between(0, 255)


class HADES_AUTH_ALLOWED_TCP_PORTS(Option):
    """Allowed TCP destination ports for unauthenticated users"""
    type = collections.Iterable
    default = (53, 80, 443)


class HADES_AUTH_ALLOWED_UDP_PORTS(Option):
    """Allowed UDP destination ports for unauthenticated users"""
    type = collections.Iterable
    default = (53, 67)


class HADES_AUTH_ROUTING_TABLE(Option):
    """Routing table for connections from unauthenticated users."""
    type = int
    default = 1
    static_check = check.between(0, 255)


class HADES_USER_NETWORKS(Option):
    """
    Public networks of authenticated users.

    Dictionary of networks. Keys are unique identifiers of the network,
    values are netaddr.IPNetworks objects
    """
    type = collections.Mapping
    static_check = check.all(check.not_empty,
                             check.mapping(value_check=check.network_ip))


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


class HADES_UNAUTH_FWMARK(Option):
    """Iptables connmark/mark for connections from unauthenticated users"""
    type = int
    default = 2
    static_check = check.between(0, 255)


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


class HADES_UNAUTH_ROUTING_TABLE(Option):
    """Routing table for connections from unauthenticated users."""
    type = int
    default = 2
    static_check = check.between(0, 255)


class HADES_UNAUTH_DHCP_RANGE(Option):
    """DHCP range for the unauth VLAN. Must be contained within the
    HADES_UNAUTH_LISTEN network."""
    default = netaddr.IPRange('10.66.0.10', '10.66.31.254')
    type = netaddr.IPRange
    static_check = check.ip_range_in_network(HADES_UNAUTH_LISTEN.__name__)


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


# Flask options
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


# Flask-Babel options
class BABEL_DEFAULT_LOCALE(Option):
    """Default locale of the portal application"""
    default = 'de_DE'
    type = str


class BABEL_DEFAULT_TIMEZONE(Option):
    """Default timezone of the portal application"""
    default = 'Europe/Berlin'
    type = str


# Flask-SQLAlchemy options
class SQLALCHEMY_DATABASE_URI(Option):
    default = deferred_format('postgresql:///{}', 'HADES_POSTGRESQL_DATABASE')
    type = str


# Celery options
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
    default = deferred_format("hades-site-{}", 'HADES_SITE_NAME')
    type = str


class CELERY_ACCEPT_CONTENT(Option):
    default = ['json', 'msgpack', 'pickle', 'yaml']
    type = collections.Sequence


class CELERY_TASK_SERIALIZER(Option):
    default = 'pickle'
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
