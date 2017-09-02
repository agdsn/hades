import collections
import re
import urllib.parse
from datetime import timedelta

import kombu
import kombu.common
import netaddr

from hades import constants
from hades.config import check, compute
from hades.config.base import Option, OptionCheckError


###################
# General options #
###################


class HADES_SITE_NAME(Option):
    """Name of the site"""
    type = str
    required = True

    # noinspection PyUnusedLocal
    @classmethod
    def static_check(cls, config, value):
        if not re.match(r'\A[a-z][a-z0-9-]*\Z', value, re.ASCII):
            raise OptionCheckError("not a valid site name", option=cls)


class HADES_SITE_NODE_ID(Option):
    """ID of the site node"""
    type = str
    required = True

    # noinspection PyUnusedLocal
    @classmethod
    def static_check(cls, config, value):
        if not re.match(r'\A[a-z][a-z0-9-]*\Z', value, re.ASCII):
            raise OptionCheckError("not a valid node ID", option=cls)


class HADES_MAIL_DESTINATION_ADDRESSES(Option):
    """Automatic notification mails will be send to this address."""
    type = collections.Sequence
    default = []


class HADES_MAIL_SENDER_ADDRESS(Option):
    """Automatic notification mails will use this address as sender."""
    type = str
    default = ''


class HADES_MAIL_SMTP_SERVER(Option):
    """Name or IP address of SMTP relay server."""
    type = str
    default = ''


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
    required = True


class HADES_USER_NETWORKS(Option):
    """
    Public networks of authenticated users.

    Dictionary of networks. Keys are unique identifiers of the network,
    values are netaddr.IPNetworks objects
    """
    type = collections.Mapping
    required = True
    static_check = check.satisfy_all(
        check.not_empty,
        check.mapping(value_check=check.network_ip)
    )


class HADES_CUSTOM_IPTABLES_INPUT_RULES(Option):
    """
    Additional iptables rules for INPUT chain.

    A list of valid iptables-restore rules with leading -A INPUT.
    """
    type = collections.Iterable
    required = False
    default = []


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


######################
# PostgreSQL options #
######################


class HADES_POSTGRESQL_PORT(Option):
    """Port and socket name of the PostgresSQL database"""
    default = 5432
    type = int
    static_check = check.between(1, 65535)


class HADES_POSTGRESQL_LISTEN(Option):
    """
    A list of addresses PostgreSQL should listen on.
    """
    default = (
        netaddr.IPNetwork('127.0.0.1/8'),
    )
    type = collections.Sequence
    static_check = check.sequence(check.network_ip)
    runtime_check = check.sequence(check.address_exists)


class HADES_POSTGRESQL_FOREIGN_SERVER_FDW(Option):
    """
    Name of the foreign data wrapper extensions that should be used.

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    default = 'postgres_fdw'
    type = str


class HADES_POSTGRESQL_FOREIGN_SERVER_OPTIONS(Option):
    """
    Foreign data wrapper specific server options

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    type = collections.Mapping
    default = {}


class HADES_POSTGRESQL_FOREIGN_SERVER_TYPE(Option):
    """
    Foreign data wrapper specific server type

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    type = (str, type(None))
    default = None


class HADES_POSTGRESQL_FOREIGN_SERVER_VERSION(Option):
    """
    Foreign data wrapper specific server version

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    type = (str, type(None))
    default = None


class HADES_POSTGRESQL_FOREIGN_TABLE_GLOBAL_OPTIONS(Option):
    """
    Foreign data wrapper options that are set on each foreign table.
    The options can be overridden with table specific options.

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    default = {
        'dbname': 'hades',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_ALTERNATIVE_DNS_IPADDRESS_STRING(Option):
    """
    Whether the ipaddress column of the foreign alternative_dns table has a string type
    """
    type = bool
    default = False


class HADES_POSTGRESQL_FOREIGN_TABLE_ALTERNATIVE_DNS_OPTIONS(Option):
    """
    Foreign data wrapper options for the alternative_dns table

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'alternative_dns',
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

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'dhcphost',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_NAS_OPTIONS(Option):
    """
    Foreign data wrapper options for the nas table

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
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

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'radcheck',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADGROUPCHECK_OPTIONS(Option):
    """
    Foreign data wrapper options for the radgroupcheck table

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'radgroupcheck',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_FOREIGN_TABLE_RADGROUPREPLY_OPTIONS(Option):
    """
    Foreign data wrapper options for the radgroupreply table

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
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

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
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

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    default = {
        'table_name': 'radusergroup',
    }
    type = collections.Mapping


class HADES_POSTGRESQL_USER_MAPPINGS(Option):
    """
    User mappings from local database users to users on the foreign database
    server

    If HADES_LOCAL_MASTER_DATABASE is set, this option is ignored.
    """
    type = collections.Mapping
    static_check = check.user_mapping_for_user_exists(constants.DATABASE_USER)


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


class HADES_PORTAL_UWSGI_WORKERS(Option):
    """Number of uWSGI worker processes"""
    default = 4
    type = int
    static_check = check.greater_than(0)


###############################
# Authenticated users options #
###############################


class HADES_AUTH_DHCP_DOMAIN(Option):
    """DNS domain of authenticated users"""
    default = 'users.agdsn.de'
    type = str


class HADES_AUTH_DHCP_LEASE_LIFETIME(Option):
    """DHCP lease lifetime for authenticated users"""
    default = timedelta(hours=24)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_AUTH_DHCP_LEASE_RENEW_TIMER(Option):
    """DHCP lease renew timer for authenticated users"""
    type = timedelta
    static_check = check.greater_than(timedelta(0))

    @staticmethod
    def default(config):
        return 0.5 * config.HADES_AUTH_DHCP_LEASE_LIFETIME


class HADES_AUTH_DHCP_LEASE_REBIND_TIMER(Option):
    """DHCP lease rebind timer for authenticated users"""
    type = timedelta
    static_check = check.greater_than(timedelta(0))

    @staticmethod
    def default(config):
        return 0.875 * config.HADES_AUTH_DHCP_LEASE_LIFETIME


class HADES_AUTH_LISTEN(Option):
    """
    Sequence of IPs and networks to listen on for requests from authenticated
    users.

    The first IP in the sequence will be the main IP, e.g. it will be advertised
    as IP of DNS server in DHCP responses.
    """
    default = (
        netaddr.IPNetwork('10.66.67.10/24'),
    )
    type = collections.Sequence
    static_check = check.satisfy_all(
        check.not_empty,
        check.sequence(check.network_ip),
    )
    runtime_check = check.sequence(check.address_exists)


class HADES_AUTH_INTERFACE(Option):
    """
    Interface where requests of authenticated users arrive.

    This interface will be moved into the auth namespace and IP addresses on
    this interface are managed by the keepalived hades-auth VRRP instance.

    This interface should therefore be managed completely by Hades. Aside from
    its creation other tools, e.g. ifupdown, systemd-network, should not
    interfere. No other daemons should listen on or bind to this interface.
    """
    type = str
    required = True
    runtime_check = check.interface_exists


class HADES_AUTH_NEXT_HOP(Option):
    """
    The next hop, where packets to user networks (e.g. DHCP replies, DNS
    replies) should be forwarded to.
    """
    type = netaddr.IPNetwork
    default = netaddr.IPNetwork('10.66.67.1/24')
    static_check = check.network_ip


class HADES_AUTH_ALLOWED_TCP_PORTS(Option):
    """Allowed TCP destination ports for unauthenticated users"""
    type = collections.Iterable
    default = (53, 80, 443, 9053)


class HADES_AUTH_ALLOWED_UDP_PORTS(Option):
    """Allowed UDP destination ports for unauthenticated users"""
    type = collections.Iterable
    default = (53, 67, 9053)


class HADES_AUTH_DNS_ALTERNATIVE_IPSET(Option):
    """Name of ipset for alternative DNS resolving."""
    type = str
    default = "hades_alternative_dns"


class HADES_AUTH_DNS_ALTERNATIVE_ZONES(Option):
    """DNS zones that are transparently spoofed if alternative DNS is
    enabled."""
    type = collections.Mapping
    default = {}


#################################
# Unauthenticated users options #
#################################


class HADES_UNAUTH_DHCP_LEASE_TIME(Option):
    """
    DHCP lease time for unauth users

    This lease time should be set rather short, so that unauthenticated will
    quickly obtain a new address if they become authenticated.
    """
    default = timedelta(minutes=2)
    type = timedelta
    static_check = check.greater_than(timedelta(0))


class HADES_UNAUTH_INTERFACE(Option):
    """Interface attached to the unauth VLAN"""
    type = str
    required = True
    runtime_check = check.interface_exists


class HADES_UNAUTH_LISTEN(Option):
    """
    Sequence of IPs and networks to listen for unauthenticated users.

    The first IP in the sequence will be the main IP, e.g. it will be advertised
    as IP of DNS server in DHCP responses.
    """
    default = (
        netaddr.IPNetwork('10.66.0.1/19'),
    )
    type = collections.Sequence
    static_check = check.satisfy_all(
        check.not_empty,
        check.sequence(check.network_ip)
    )
    runtime_check = check.sequence(check.address_exists)


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
    static_check = check.ip_range_in_networks(HADES_UNAUTH_LISTEN)


class HADES_UNAUTH_WHITELIST_DNS(Option):
    """List of DNS names which are whitelisted for unauthenticated users.
    """
    default = ()
    type = collections.Iterable


class HADES_UNAUTH_WHITELIST_IPSET(Option):
    """Name of ipset for whitelisted IPs.
    """
    default = "hades_unauth_whitelist"
    type = str


##################
# RADIUS options #
##################


class HADES_RADIUS_LISTEN(Option):
    """
    Sequence of IPs and networks the RADIUS server is listening on.
    """
    default = (
        netaddr.IPNetwork('10.66.68.10/24'),
    )
    type = collections.Sequence
    static_check = check.satisfy_all(
        check.not_empty,
        check.sequence(check.network_ip)
    )
    runtime_check = check.sequence(check.address_exists)


class HADES_RADIUS_INTERFACE(Option):
    """Interface the RADIUS server is listening on"""
    type = str
    required = True
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


class HADES_RADIUS_UNKNOWN_USER(Option):
    type = str
    default = "unknown"


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
    static_check = check.greater_than(timedelta(seconds=0))


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
    required = True
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


class HADES_LOCAL_MASTER_DATABASE(Option):
    """
    Create and use a local “foreign” database.
    """
    type = bool
    default = False


class HADES_BRIDGE_SERVICE_INTERFACES(Option):
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
    @staticmethod
    def default(config):
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


class HADES_CELERY_WORKER_HOSTNAME(Option):
    """
    Hostname of the hades-agent Celery worker.
    """
    default = compute.deferred_format('{}.{}', HADES_SITE_NAME,
                                      HADES_SITE_NODE_ID)
    type = str


class HADES_CELERY_RPC_EXCHANGE(Option):
    default = 'hades.agent.rpc'
    type = str


class HADES_CELERY_RPC_EXCHANGE_TYPE(Option):
    default = 'topic'
    type = str


class HADES_CELERY_NOTIFY_EXCHANGE(Option):
    default = 'hades.agent.notify'
    type = str


class HADES_CELERY_NOTIFY_EXCHANGE_TYPE(Option):
    default = 'topic'
    type = str


class HADES_CELERY_NODE_QUEUE(Option):
    default = compute.deferred_format('hades.{}.{}', HADES_SITE_NAME,
                                      HADES_SITE_NODE_ID)
    type = str


class HADES_CELERY_SITE_ROUTING_KEY(Option):
    default = compute.equal_to(HADES_SITE_NAME)
    type = str


class HADES_CELERY_NODE_ROUTING_KEY(Option):
    default = compute.deferred_format('{}.{}', HADES_SITE_NAME,
                                      HADES_SITE_NODE_ID)
    type = str


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
        routing key. The agent on a site node, which has become the RADIUS VRRP
        MASTER, will also bind its queue to the RPC exchange with the
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
            config.HADES_CELERY_RPC_EXCHANGE_TYPE
        )
        notify_exchange = kombu.Exchange(
            config.HADES_CELERY_NOTIFY_EXCHANGE,
            config.HADES_CELERY_NOTIFY_EXCHANGE_TYPE
        )
        node_key = config.HADES_CELERY_NODE_ROUTING_KEY
        site_key = config.HADES_CELERY_SITE_ROUTING_KEY
        return (
            kombu.Queue(config.HADES_CELERY_NODE_QUEUE, (
                    kombu.binding(rpc_exchange, routing_key=node_key),
                    kombu.binding(notify_exchange, routing_key=node_key),
                    kombu.binding(notify_exchange, routing_key=site_key),
                    kombu.binding(notify_exchange, routing_key=''),
                ),
                auto_delete=True, durable=False),
        )
    type = collections.Sequence


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
    type = collections.Sequence


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
    default = (
        'hades.agent.tasks',
    )
    type = collections.Sequence


class CELERY_TASK_RESULT_EXPIRES(CeleryOption):
    default = timedelta(minutes=5)
    type = timedelta
