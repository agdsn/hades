from datetime import timedelta
import random
import string
import collections

import netaddr

from hades.config import check


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
    default = 'hades'
    type = str


class HADES_POSTGRESQL_SOCKET(Option):
    default = '/var/run/postgresql'
    type = str
    runtime_check = check.directory_exists


class HADES_POSTGRESQL_FOREIGN_SERVER_FDW(Option):
    default = 'mysql_fdw'
    type = str


class HADES_POSTGRESQL_FOREIGN_SERVER_OPTIONS(Option):
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_GLOBAL_OPTIONS(Option):
    default = {
        'dbname': 'hades',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_DHCPHOST_OPTIONS(Option):
    default = {
        'table_name': 'dhcphost',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_NAS_OPTIONS(Option):
    default = {
        'table_name': 'nas',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADCHECK_OPTIONS(Option):
    default = {
        'table_name': 'radcheck',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADGROUPCHECK_OPTIONS(Option):
    default = {
        'table_name': 'radgroupcheck',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADGROUPREPLY_OPTIONS(Option):
    default = {
        'table_name': 'radgroupreply',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADREPLY_OPTIONS(Option):
    default = {
        'table_name': 'radreply',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADUSERGROUP_OPTIONS(Option):
    default = {
        'table_name': 'radusergroup',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_USER_MAPPINGS(Option):
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
    default = '/var/lib/hades-portal'
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
    default = '/run/hades/portal.sock'
    type = str
    runtime_check = check.file_creatable


class HADES_PORTAL_UWSGI_WORKERS(Option):
    """Number of uWSGI worker processes"""
    default = 4
    type = int
    static_check = check.greater_than(0)


class HADES_REGULAR_DNSMASQ_DHCP_HOSTS_FILE(Option):
    """Path to the DHCP hosts file of the regular dnsmasq instance."""
    default = "/var/lib/hades/agent/dnsmasq-regular.hosts"
    type = str
    runtime_check = check.file_creatable


class HADES_REGULAR_DNSMASQ_DHCP_LEASE_FILE(Option):
    """Path to the DHCP lease file of the regular dnsmasq instance."""
    default = "/var/lib/hades/agent/dnsmasq-regular.leases"
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


class HADES_REGULAR_LISTEN(Option):
    """IP and network to listen on for requests from the regular VLANs"""
    default = netaddr.IPNetwork('10.66.67.1/24')
    static_check = check.address_exists


class HADES_REGULAR_INTERFACE(Option):
    """Interface where requests from the regular VLANs arrive. Interface must
    not be attached directly to an regular VLAN."""
    type = str
    runtime_check = check.interface_exists


class HADES_REGULAR_NETWORKS(Option):
    """Dictionary of networks. Keys are unique identifiers of the network,
    values are netaddr.IPNetworks objects"""
    type = collections.Mapping
    static_check = check.gateway_network_dict


class HADES_UNAUTH_DHCP_LEASE_TIME(Option):
    """DHCP lease time in the unauth VLAN"""
    default = timedelta(minutes=2)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_UNAUTH_INTERFACE(Option):
    """Interface of attached to the unauth VLAN"""
    type = str
    runtime_check = check.interface_exists


class HADES_UNAUTH_LISTEN(Option):
    """IP and network """
    default = netaddr.IPNetwork('10.66.0.1/19')
    type = netaddr.IPNetwork


class HADES_UNAUTH_DHCP_RANGE(Option):
    """DHCP range for the unauth VLAN. Must be contained within the
    HADES_UNAUTH_LISTEN network."""
    default = netaddr.IPRange('10.66.0.10', '10.66.31.254')
    type = netaddr.IPRange
    static_check = check.ip_range_in_network('HADES_UNAUTH_LISTEN')


class HADES_MANAGEMENT_LISTEN(Option):
    """
    IP and network for services with restricted access.
    The RADIUS server listens on this IP.
    """
    type = str
    runtime_check = check.address_exists


class HADES_MANAGEMENT_INTERFACE(Option):
    """Interface for services with restricted access."""
    type = str
    runtime_check = check.interface_exists


# Flask options
class SECRET_KEY(Option):
    default = ''.join(random.choice(string.ascii_letters + string.digits)
                      for i in range(64))
    type = str


class DEBUG(Option):
    defaults = True
    type = bool


# Flask-Babel options
class BABEL_DEFAULT_LOCALE(Option):
    default = 'de_DE'
    type = str


class BABEL_DEFAULT_TIMEZONE(Option):
    default = 'Europe/Berlin'
    type = str


# Flask-SQLAlchemy options
class SQLALCHEMY_DATABASE_URI(Option):
    default = 'postgresql:///hades'
    type = str


# Celery options
class BROKER_URL(Option):
    type = str


class CELERY_ENABLE_UTC(Option):
    default = True
    type = bool


class CELERY_DEFAULT_QUEUE(Option):
    default = "hades-agent-test"
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
