import collections
import collections.abc
import re
import urllib.parse
from datetime import timedelta

import kombu
import kombu.common
import netaddr

from hades import constants

from . import check, compute
from .base import Compute, Option


class HadesOption(Option, abstract=True):
    pass


###################
# General options #
###################


class HADES_SITE_NAME(HadesOption):
    """Name of the site"""
    type = str
    required = True
    static_check = check.match(r'\A[a-z][a-z0-9-]*\Z', re.ASCII)


class HADES_SITE_NODE_ID(HadesOption):
    """ID of the site node"""
    type = str
    required = True
    static_check = check.match(r'\A[a-z][a-z0-9-]*\Z', re.ASCII)


class HADES_MAIL_DESTINATION_ADDRESSES(HadesOption):
    """Automatic notification mails will be send to this address."""
    type = collections.abc.Sequence
    static_check = check.satisfy_all(
        check.not_empty,
        check.sequence(check.type_is(str))
    )


class HADES_MAIL_SENDER_ADDRESS(HadesOption):
    """Automatic notification mails will use this address as sender."""
    type = str


class HADES_MAIL_SMTP_SERVER(HadesOption):
    """Name or IP address of SMTP relay server."""
    type = str


class HADES_REAUTHENTICATION_INTERVAL(HadesOption):
    """RADIUS periodic reauthentication interval"""
    default = timedelta(seconds=300)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_RETENTION_INTERVAL(HadesOption):
    """RADIUS postauth and accounting data retention interval"""
    default = timedelta(days=1)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_CONTACT_ADDRESSES(HadesOption):
    """Contact addresses displayed on the captive portal page"""
    type = collections.abc.Mapping
    required = True


class HADES_USER_NETWORKS(HadesOption):
    """
    Public networks of authenticated users.

    Dictionary of networks. Keys are unique identifiers of the network,
    values are :class:`netaddr.IPNetwork` objects
    """
    type = collections.abc.Mapping
    required = True
    static_check = check.satisfy_all(
        check.not_empty,
        check.mapping(value_check=check.network_ip)
    )


class HADES_CUSTOM_IPTABLES_INPUT_RULES(HadesOption):
    """Additional iptables rules for ``INPUT`` chain.

    A list of valid ``iptables-restore`` rule lines with leading ``-A INPUT``.
    """
    type = collections.abc.Sequence
    default: collections.abc.Sequence = []


#############################
# Network namespace options #
#############################


class HADES_NETNS_MAIN_AUTH_LISTEN(HadesOption):
    default = netaddr.IPNetwork('172.18.0.0/31')
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_NETNS_AUTH_LISTEN(HadesOption):
    default = netaddr.IPNetwork('172.18.0.1/31')
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_NETNS_MAIN_UNAUTH_LISTEN(HadesOption):
    default = netaddr.IPNetwork('172.18.0.2/31')
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_NETNS_UNAUTH_LISTEN(HadesOption):
    default = netaddr.IPNetwork('172.18.0.3/31')
    static_check = check.network_ip
    runtime_check = check.address_exists


######################
# PostgreSQL options #
######################


class HADES_POSTGRESQL_PORT(HadesOption):
    """Port and socket name of the PostgresSQL database"""
    default = 5432
    type = int
    static_check = check.between(1, 65535)


class HADES_POSTGRESQL_LISTEN(HadesOption):
    """
    A list of addresses PostgreSQL should listen on.
    """
    default = (
        netaddr.IPNetwork('127.0.0.1/8'),
    )
    type = collections.abc.Sequence
    static_check = check.sequence(check.network_ip)
    runtime_check = check.sequence(check.address_exists)


class HADES_POSTGRESQL_FOREIGN_SERVER_FDW(HadesOption):
    """
    Name of the foreign data wrapper extensions that should be used.

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    default = 'postgres_fdw'
    type = str


class HADES_POSTGRESQL_FOREIGN_SERVER_OPTIONS(HadesOption):
    """
    Foreign data wrapper specific server options

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    type = collections.abc.Mapping
    default: collections.abc.Mapping = {}


class HADES_POSTGRESQL_FOREIGN_SERVER_TYPE(HadesOption):
    """
    Foreign data wrapper specific server type

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    type = str


class HADES_POSTGRESQL_FOREIGN_SERVER_VERSION(HadesOption):
    """
    Foreign data wrapper specific server version

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    type = str


class HADES_POSTGRESQL_FOREIGN_TABLE_GLOBAL_OPTIONS(HadesOption):
    """
    Foreign data wrapper options that are set on each foreign table.
    The options can be overridden with table specific options.

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    default: collections.abc.Mapping = {}
    type = collections.abc.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_ALTERNATIVE_DNS_IPADDRESS_STRING(HadesOption):
    """Whether the ``IPAddress`` column of the foreign ``alternative_dns`` table
    has a string type"""
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_ALTERNATIVE_DNS_OPTIONS(HadesOption):
    """Foreign data wrapper options for the ``alternative_dns`` table

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    default = {
        'table_name': 'alternative_dns',
    }
    type = collections.abc.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_AUTH_DHCP_HOST_IPADDRESS_STRING(HadesOption):
    """Whether the ``IPAddress`` column of the foreign ``auth_dhcp_host`` table
    has a string type"""
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_AUTH_DHCP_HOST_MAC_STRING(HadesOption):
    """Whether the ``MAC`` column of the foreign ``auth_dhcp_host`` table has a
    string type"""
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_AUTH_DHCP_HOST_OPTIONS(HadesOption):
    """Foreign data wrapper options for the ``auth_dhcp_host`` table

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    default = {
        "table_name": "auth_dhcp_host",
    }
    type = collections.abc.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_NAS_OPTIONS(HadesOption):
    """Foreign data wrapper options for the ``nas`` table

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    default = {
        'table_name': 'nas',
    }
    type = collections.abc.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADCHECK_NASIPADDRESS_STRING(HadesOption):
    """Whether the ``NASIPAddress`` column of the foreign ``radcheck`` table has
    a string type."""
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_RADCHECK_OPTIONS(HadesOption):
    """Foreign data wrapper options for the ``radcheck`` table

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    default = {
        'table_name': 'radcheck',
    }
    type = collections.abc.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADGROUPCHECK_OPTIONS(HadesOption):
    """Foreign data wrapper options for the ``radgroupcheck`` table

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    default = {
        'table_name': 'radgroupcheck',
    }
    type = collections.abc.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADGROUPREPLY_OPTIONS(HadesOption):
    """Foreign data wrapper options for the ``radgroupreply`` table

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    default = {
        'table_name': 'radgroupreply',
    }
    type = collections.abc.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADREPLY_NASIPADDRESS_STRING(HadesOption):
    """Whether the ``NASIPAddress`` column of the foreign ``radgroupcheck``
    table has a string type"""
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_RADREPLY_OPTIONS(HadesOption):
    """Foreign data wrapper options for the ``radreply`` table

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    default = {
        'table_name': 'radreply',
    }
    type = collections.abc.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADUSERGROUP_NASIPADDRESS_STRING(HadesOption):
    """Whether the ``NASIPAddress`` column of the foreign ``radgroupcheck``
    table has a string type"""
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_RADUSERGROUP_OPTIONS(HadesOption):
    """Foreign data wrapper options for the ``radusergroup`` table

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    default = {
        'table_name': 'radusergroup',
    }
    type = collections.abc.Mapping


class HADES_POSTGRESQL_USER_MAPPINGS(HadesOption):
    """
    User mappings from local database users to users on the foreign database
    server

    If :hades:option:`HADES_LOCAL_MASTER_DATABASE` is set, this option is
    ignored.
    """
    type = collections.abc.Mapping
    static_check = check.user_mapping_for_user_exists(constants.DATABASE_USER)


########################
# Hades Portal options #
########################


class HADES_PORTAL_DOMAIN(HadesOption):
    """Fully qualified domain name of the captive portal"""
    default = 'captive-portal.agdsn.de'
    type = str


class HADES_PORTAL_URL(HadesOption):
    """URL of the landing page of the captive portal"""
    default = compute.deferred_format("http://{}/", HADES_PORTAL_DOMAIN)
    type = str


class HADES_PORTAL_NGINX_WORKERS(HadesOption):
    """Number of nginx worker processes"""
    default = 4
    type = int
    static_check = check.greater_than(0)


class HADES_PORTAL_SSL_CERTIFICATE(HadesOption):
    """Path to the SSL certificate of the captive portal"""
    default = '/etc/ssl/certs/ssl-cert-snakeoil.pem'
    runtime_check = check.file_exists


class HADES_PORTAL_SSL_CERTIFICATE_KEY(HadesOption):
    """Path to the SSL certificate key of the captive portal"""
    default = '/etc/ssl/private/ssl-cert-snakeoil.key'
    runtime_check = check.file_exists


class HADES_PORTAL_UWSGI_WORKERS(HadesOption):
    """Number of uWSGI worker processes"""
    default = 4
    type = int
    static_check = check.greater_than(0)


###############################
# Authenticated users options #
###############################


class HADES_AUTH_DHCP_DOMAIN(HadesOption):
    """DNS domain of authenticated users"""
    default = 'users.agdsn.de'
    type = str


class HADES_AUTH_DHCP_LEASE_LIFETIME(HadesOption):
    """DHCP lease lifetime for authenticated users"""
    default = timedelta(hours=24)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_AUTH_DHCP_LEASE_RENEW_TIMER(HadesOption):
    """DHCP lease renew timer for authenticated users"""
    type = timedelta
    static_check = check.greater_than(timedelta(0))

    # noinspection PyNestedDecorators
    @Compute.decorate
    @staticmethod
    def default(config):
        """Half of :hades:option:`HADES_AUTH_DHCP_LEASE_LIFETIME`"""
        return 0.5 * config.HADES_AUTH_DHCP_LEASE_LIFETIME


class HADES_AUTH_DHCP_LEASE_REBIND_TIMER(HadesOption):
    """DHCP lease rebind timer for authenticated users"""
    type = timedelta
    static_check = check.greater_than(timedelta(0))

    # noinspection PyNestedDecorators
    @Compute.decorate
    @staticmethod
    def default(config):
        """0.875 of :hades:option:`HADES_AUTH_DHCP_LEASE_LIFETIME`"""
        return 0.875 * config.HADES_AUTH_DHCP_LEASE_LIFETIME


class HADES_AUTH_LISTEN(HadesOption):
    """
    Sequence of IPs and networks to listen on for requests from authenticated
    users.

    The first IP in the sequence will be the main IP, e.g. it will be advertised
    as IP of DNS server in DHCP responses.
    """
    default = (
        netaddr.IPNetwork('10.66.67.10/24'),
    )
    type = collections.abc.Sequence
    static_check = check.satisfy_all(
        check.not_empty,
        check.sequence(check.network_ip),
    )
    runtime_check = check.sequence(check.address_exists)


class HADES_AUTH_INTERFACE(HadesOption):
    """
    Interface where requests of authenticated users arrive.

    This interface will be moved into the auth namespace and IP addresses on
    this interface are managed by the keepalived hades-auth VRRP instance.

    This interface should therefore be managed completely by Hades. Aside from
    its creation other tools, e.g. ``ifupdown``, ``systemd-networkd``, should
    not interfere. No other daemons should listen on or bind to this interface.
    """
    type = str
    required = True
    runtime_check = check.interface_exists


class HADES_AUTH_BRIDGE(HadesOption):
    """Name of the auth bridge interface"""
    type = str
    default = "br-auth"
    static_check = check.match(r"\A[A-Za-z0-9_-]{1,15}\Z", re.ASCII)


class HADES_AUTH_NEXT_HOP(HadesOption):
    """
    The next hop, where packets to user networks (e.g. DHCP replies, DNS
    replies) should be forwarded to.
    """
    type = netaddr.IPNetwork
    default = netaddr.IPNetwork('10.66.67.1/24')
    static_check = check.network_ip


class HADES_AUTH_ALLOWED_TCP_PORTS(HadesOption):
    """Allowed TCP destination ports for unauthenticated users"""
    type = collections.abc.Sequence
    default = (53, 80, 443, 9053)


class HADES_AUTH_ALLOWED_UDP_PORTS(HadesOption):
    """Allowed UDP destination ports for unauthenticated users"""
    type = collections.abc.Sequence
    default = (53, 67, 9053)


class HADES_AUTH_DNS_ALTERNATIVE_IPSET(HadesOption):
    """Name of ipset for alternative DNS resolving."""
    type = str
    default = "hades_alternative_dns"


class HADES_AUTH_DNS_ALTERNATIVE_ZONES(HadesOption):
    """DNS zones that are transparently spoofed if alternative DNS is
    enabled."""
    type = collections.abc.Mapping
    default: collections.abc.Mapping = {}


#################################
# Unauthenticated users options #
#################################


class HADES_UNAUTH_DHCP_LEASE_TIME(HadesOption):
    """
    DHCP lease time for unauth users

    This lease time should be set rather short, so that unauthenticated will
    quickly obtain a new address if they become authenticated.
    """
    default = timedelta(minutes=2)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_UNAUTH_INTERFACE(HadesOption):
    """Interface attached to the unauth VLAN"""
    type = str
    required = True
    runtime_check = check.interface_exists


class HADES_UNAUTH_BRIDGE(HadesOption):
    """Name of the unauth bridge interface"""
    type = str
    default = "br-unauth"
    static_check = check.match(r"\A[A-Za-z0-9_-]{1,15}\Z", re.ASCII)


class HADES_UNAUTH_LISTEN(HadesOption):
    """
    Sequence of IPs and networks to listen for unauthenticated users.

    The first IP in the sequence will be the main IP, e.g. it will be advertised
    as IP of DNS server in DHCP responses.
    """
    default = (
        netaddr.IPNetwork('10.66.0.1/19'),
    )
    type = collections.abc.Sequence
    static_check = check.satisfy_all(
        check.not_empty,
        check.sequence(check.network_ip)
    )
    runtime_check = check.sequence(check.address_exists)


class HADES_UNAUTH_ALLOWED_TCP_PORTS(HadesOption):
    """Allowed TCP destination ports for unauthenticated users"""
    type = collections.abc.Sequence
    default = (53, 80, 443)


class HADES_UNAUTH_ALLOWED_UDP_PORTS(HadesOption):
    """Allowed UDP destination ports for unauthenticated users"""
    type = collections.abc.Sequence
    default = (53, 67)


class HADES_UNAUTH_CAPTURED_TCP_PORTS(HadesOption):
    """
    All traffic destined to these TCP ports is transparently redirected
    (captured) to the unauth listen address of the site node
    """
    type = collections.abc.Sequence
    default = (53, 80, 443)


class HADES_UNAUTH_CAPTURED_UDP_PORTS(HadesOption):
    """
    All traffic destined to these UDP ports is transparently redirected
    (captured) to the unauth listen address of the site node
    """
    type = collections.abc.Sequence
    default = (53,)


class HADES_UNAUTH_DHCP_RANGE(HadesOption):
    """DHCP range for the unauth VLAN. Must be contained within the
    :hades:option:`HADES_UNAUTH_LISTEN` network."""
    default = netaddr.IPRange('10.66.0.10', '10.66.31.254')
    type = netaddr.IPRange
    static_check = check.ip_range_in_networks(HADES_UNAUTH_LISTEN)


class HADES_UNAUTH_WHITELIST_DNS(HadesOption):
    """List of DNS names which are whitelisted for unauthenticated users.
    """
    default = ()
    type = collections.abc.Sequence


class HADES_UNAUTH_WHITELIST_IPSET(HadesOption):
    """Name of ipset for whitelisted IPs.
    """
    default = "hades_unauth_whitelist"
    type = str


##################
# RADIUS options #
##################


class HADES_RADIUS_LISTEN(HadesOption):
    """
    Sequence of IPs and networks the RADIUS server is listening on.
    """
    default = (
        netaddr.IPNetwork('10.66.68.10/24'),
    )
    type = collections.abc.Sequence
    static_check = check.satisfy_all(
        check.not_empty,
        check.sequence(check.network_ip)
    )
    runtime_check = check.sequence(check.address_exists)


class HADES_RADIUS_INTERFACE(HadesOption):
    """Interface the RADIUS server is listening on"""
    type = str
    required = True
    runtime_check = check.interface_exists


class HADES_RADIUS_AUTHENTICATION_PORT(HadesOption):
    """RADIUS authentication port"""
    type = int
    default = 1812


class HADES_RADIUS_ACCOUNTING_PORT(HadesOption):
    """RADIUS accounting port"""
    type = int
    default = 1813


class HADES_RADIUS_LOCALHOST_SECRET(HadesOption):
    """Shared secret for the localhost RADIUS client"""
    type = str


class HADES_RADIUS_DATABASE_FAIL_ACCEPT(HadesOption):
    """Send ``Access-Accept`` packets if the RADIUS ``sql`` module fails"""
    type = bool
    default = True


class HADES_RADIUS_DATABASE_FAIL_REPLY_ATTRIBUTES(HadesOption):
    """
    Reply attributes that will be set in ``Access-Accept`` packets if the RADIUS
    ``sql`` module fails.

    The attribute value must be specified in proper FreeRADIUS syntax. That
    means that string replies should be enclosed in single quotes.
    """
    type = collections.abc.Mapping
    default = {
        'Reply-Message': "'database_down'",
    }


class HADES_RADIUS_UNKNOWN_USER(HadesOption):
    """The ``User-Name``, that is used as fallback if the MAC address was not
    found in the database."""
    type = str
    default = "unknown"


##########################
# Gratuitous ARP options #
##########################


class HADES_GRATUITOUS_ARP_INTERVAL(HadesOption):
    """
    Period in which gratuitous ARP requests are broadcasted to notify

    #. clients of the MAC address of current master site node instance
    #. clients switching from the auth to the unauth VLAN of the new gateway MAC
    """
    type = timedelta
    default = timedelta(seconds=1)
    static_check = check.greater_than(timedelta(seconds=0))


################
# VRRP options #
################


class HADES_PRIORITY(HadesOption):
    """
    Priority of the site node instance.

    The available instance with the highest priority becomes master.
    """
    type = int
    default = 100
    static_check = check.between(1, 254)


class HADES_INITIAL_MASTER(HadesOption):
    """Flag that indicates if the site node instance starts in master state"""
    type = bool
    default = False


class HADES_VRRP_INTERFACE(HadesOption):
    """Interface for VRRP communication"""
    type = str
    runtime_check = check.interface_exists


class HADES_VRRP_BRIDGE(HadesOption):
    """Interface name for VRRP bridge (created if necessary)"""
    type = str
    default = 'br-vrrp'
    static_check = check.not_empty


class HADES_VRRP_LISTEN_AUTH(HadesOption):
    """IP and network for VRRP communication (auth instance)"""
    type = netaddr.IPNetwork
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_VRRP_LISTEN_ROOT(HadesOption):
    """IP and network for VRRP communication (root instance)"""
    type = netaddr.IPNetwork
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_VRRP_LISTEN_UNAUTH(HadesOption):
    """IP and network for VRRP communication (unauth instance)"""
    type = netaddr.IPNetwork
    static_check = check.network_ip
    runtime_check = check.address_exists


class HADES_VRRP_PASSWORD(HadesOption):
    """
    Shared secret to authenticate VRRP messages between site node instances.
    """
    required = True
    type = str


class HADES_VRRP_VIRTUAL_ROUTER_ID_AUTH(HadesOption):
    """Virtual router ID used by Hades (auth instance)"""
    type = int
    default = 66
    static_check = check.between(0, 255)


class HADES_VRRP_VIRTUAL_ROUTER_ID_ROOT(HadesOption):
    """Virtual router ID used by Hades (root instance)"""
    type = int
    default = 67
    static_check = check.between(0, 255)


class HADES_VRRP_VIRTUAL_ROUTER_ID_UNAUTH(HadesOption):
    """Virtual router ID used by Hades (unauth instance)"""
    type = int
    default = 68
    static_check = check.between(0, 255)


class HADES_VRRP_ADVERTISEMENT_INTERVAL(HadesOption):
    """Interval between VRRP advertisements"""
    type = timedelta
    default = timedelta(seconds=5)
    static_check = check.greater_than(timedelta(0))


class HADES_VRRP_PREEMPTION_DELAY(HadesOption):
    """
    Delay before a *MASTER* transitions to *BACKUP* when a node with a higher
    priority comes online
    """
    type = timedelta
    default = timedelta(seconds=30)
    static_check = check.between(timedelta(seconds=0), timedelta(seconds=1000))


################
# Test options #
################


class HADES_CREATE_DUMMY_INTERFACES(HadesOption):
    """Create dummy interfaces if interfaces do not exist"""
    type = bool
    default = False


class HADES_LOCAL_MASTER_DATABASE(HadesOption):
    """
    Create and use a local “foreign” database.
    """
    type = bool
    default = False


class HADES_BRIDGE_SERVICE_INTERFACES(HadesOption):
    """
    Link the service interface of the auth and unauth network namespaces through
    bridges and veth interfaces rather than moving the interface directly into
    the network namespace.

    This allows to attach other interfaces to the bridge to e.g. test DHCP.
    """
    type = bool
    default = False


#################
# Flask options #
#################

class FlaskOption(Option, abstract=True):
    pass


class DEBUG(FlaskOption):
    """Flask debug mode flag"""
    defaults = False
    type = bool


#######################
# Flask-Babel options #
#######################


class BABEL_DEFAULT_LOCALE(FlaskOption):
    """Default locale of the portal application"""
    default = 'de_DE'
    type = str


class BABEL_DEFAULT_TIMEZONE(FlaskOption):
    """Default timezone of the portal application"""
    default = 'Europe/Berlin'
    type = str


############################
# Flask-SQLAlchemy options #
############################


class SQLALCHEMY_DATABASE_URI(FlaskOption):
    # noinspection PyNestedDecorators
    @Compute.decorate
    @staticmethod
    def default(config):
        """A URI targeting the default postgresql socket in the pkgrunstatedir.

        The port is set to :hades:option:`HADES_POSTGRESQL_PORT`
        and the user is the default database user.
        """
        if 'postgresql' not in urllib.parse.uses_netloc:
            urllib.parse.uses_netloc.append('postgresql')
        if 'postgresql' not in urllib.parse.uses_query:
            urllib.parse.uses_query.append('postgresql')
        query = urllib.parse.urlencode({
            'host': constants.pkgrunstatedir + '/database',
            'port': config.HADES_POSTGRESQL_PORT,
            'requirepeer': constants.DATABASE_USER,
            'client_encoding': 'utf-8',
            'connect_timeout': 5,
        })
        return urllib.parse.urlunsplit(('postgresql', '',
                                        constants.DATABASE_NAME,
                                        query, ''))
    type = str


##################
# Celery options #
##################


class HADES_CELERY_WORKER_HOSTNAME(HadesOption):
    """
    Hostname of the hades-agent Celery worker.
    """
    default = compute.deferred_format('{}.{}', HADES_SITE_NAME,
                                      HADES_SITE_NODE_ID)
    type = str


class HADES_CELERY_RPC_EXCHANGE(HadesOption):
    default = 'hades.agent.rpc'
    type = str


class HADES_CELERY_RPC_EXCHANGE_TYPE(HadesOption):
    default = 'topic'
    type = str


class HADES_CELERY_NOTIFY_EXCHANGE(HadesOption):
    default = 'hades.agent.notify'
    type = str


class HADES_CELERY_NOTIFY_EXCHANGE_TYPE(HadesOption):
    default = 'topic'
    type = str


class HADES_CELERY_NODE_QUEUE(HadesOption):
    default = compute.deferred_format('hades.{}.{}', HADES_SITE_NAME,
                                      HADES_SITE_NODE_ID)
    type = str


class HADES_CELERY_NODE_QUEUE_TTL(HadesOption):
    """TTL of the node's queue in seconds"""
    default = 5.0
    type = float


class HADES_CELERY_NODE_QUEUE_MAX_LENGTH(HadesOption):
    """Maximum length (in messages) of the node's queue"""
    default = 1000
    type = int


class HADES_CELERY_SITE_ROUTING_KEY(HadesOption):
    default = compute.equal_to(HADES_SITE_NAME)
    type = str


class HADES_CELERY_NODE_ROUTING_KEY(HadesOption):
    default = compute.deferred_format('{}.{}', HADES_SITE_NAME,
                                      HADES_SITE_NODE_ID)
    type = str


class HADES_CELERY_STATE_DB(HadesOption):
    """Path of Celery node state database"""
    type = str
    default = "{}/agent/state.db".format(constants.pkgrunstatedir)


class CeleryOption(Option, abstract=True):
    pass


class BROKER_URL(CeleryOption):
    type = str


class BROKER_CONNECTION_MAX_RETRIES(CeleryOption):
    """
    Maximum number of retries before giving up re-establishing the
    connection to the broker.

    Set to zero to retry forever in case of longer partitions between sites
    and the main database.
    """
    default = 0
    type = int


class CELERY_ENABLE_UTC(CeleryOption):
    default = True
    type = bool


class CELERY_DEFAULT_DELIVERY_MODE(CeleryOption):
    default = 'transient'
    type = str


class CELERY_QUEUES(CeleryOption):
    # noinspection PyNestedDecorators
    @Compute.decorate
    @staticmethod
    def default(config):
        """
        Declare two exchanges, one for RPCs and one for notifications.

        RPCs return results and should therefore only be answered by a single
        agent. Notifications have no results and are processed by potentially
        multiple agents.

        Each agent/site node has a single queue specific to this node. This
        queue is bound to the RPC exchange with a node-specific routing key and
        to the notify exchange with the site-specific, node-specific, and empty
        routing key. The agent on a site node, where the root VRRP instance has
        become MASTER, will also bind its queue to the RPC exchange with the
        site-specific routing key and remove this binding as soon as the sites
        leaves the MASTER state.

        This setup ensures that RPC messages can be sent to a specific
        agent/node, by using the node-specific routing key and to the agent on
        the master by using the site-specific routing key.
        Notifications can be sent to all agents/nodes by using the empty routing
        key, to all agents/nodes of a site by using the site-specific routing
        key, and to a specific node by using the node-specific routing key.
        """
        rpc_exchange = kombu.Exchange(
            config.HADES_CELERY_RPC_EXCHANGE,
            config.HADES_CELERY_RPC_EXCHANGE_TYPE,
            auto_delete=False,
            delivery_mode=kombu.Exchange.TRANSIENT_DELIVERY_MODE,
            durable=True,
        )
        notify_exchange = kombu.Exchange(
            config.HADES_CELERY_NOTIFY_EXCHANGE,
            config.HADES_CELERY_NOTIFY_EXCHANGE_TYPE,
            auto_delete=False,
            delivery_mode=kombu.Exchange.TRANSIENT_DELIVERY_MODE,
            durable=True,
        )
        node_key = config.HADES_CELERY_NODE_ROUTING_KEY
        site_key = config.HADES_CELERY_SITE_ROUTING_KEY
        return (
            kombu.Queue(
                config.HADES_CELERY_NODE_QUEUE,
                (
                    kombu.binding(rpc_exchange, routing_key=node_key),
                    kombu.binding(notify_exchange, routing_key=node_key),
                    kombu.binding(notify_exchange, routing_key=site_key),
                    kombu.binding(notify_exchange, routing_key=""),
                ),
                auto_delete=True,
                durable=False,
                max_length=config.HADES_CELERY_NODE_QUEUE_MAX_LENGTH,
                message_ttl=int(config.HADES_CELERY_NODE_QUEUE_TTL * 1000),
            ),
        )

    type = collections.abc.Sequence


class CELERYD_PREFETCH_MULTIPLIER(CeleryOption):
    type = int
    default = 1


class CELERY_TIMEZONE(CeleryOption):
    default = 'UTC'
    type = str


class CELERY_DEFAULT_QUEUE(CeleryOption):
    default = compute.equal_to(HADES_CELERY_NODE_QUEUE)
    type = str


class CELERY_DEFAULT_ROUTING_KEY(CeleryOption):
    default = compute.equal_to(HADES_CELERY_SITE_ROUTING_KEY)
    type = str


class CELERY_DEFAULT_EXCHANGE(CeleryOption):
    default = compute.equal_to(HADES_CELERY_RPC_EXCHANGE)
    type = str


class CELERY_ACCEPT_CONTENT(CeleryOption):
    default = ['json']
    type = collections.abc.Sequence


class CELERY_EVENT_SERIALIZER(CeleryOption):
    default = 'json'
    type = str


class CELERY_RESULT_SERIALIZER(CeleryOption):
    default = 'json'
    type = str


class CELERY_TASK_SERIALIZER(CeleryOption):
    default = 'json'
    type = str


class CELERY_RESULT_BACKEND(CeleryOption):
    default = 'rpc://'
    type = str


class CELERY_RESULT_EXCHANGE(CeleryOption):
    default = 'hades.result'
    type = str


class CELERY_IMPORTS(CeleryOption):
    default = ()
    type = collections.abc.Sequence


class CELERY_TASK_RESULT_EXPIRES(CeleryOption):
    default = timedelta(minutes=5)
    type = timedelta
