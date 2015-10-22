==========
Components
==========
Hades consists of quite a number of different components:

- A database (PostgresSQL)
- A RADIUS server (freeRADIUS)
- A DNS resolver for authorized users (unbound)
- A DHCP server for authorized users (dnsmasq)
- A DNS resolver for unauthorized users (again dnsmasq, but a separate instance)
- A DHCP server for unauthorized users (again dnsmasq, but same instance as unauthorized DNS)
- An agent executing regular tasks and waiting for commands (Celery worker)
- A Flask web application providing a captive portal landing page
- An WSGI application server (uwsgi) hosting the Flask application
- A web server (nginx) forwarding requests to the application server
- A VRRP server (keepalived) providing automatic fail-over between multiple Hades installations

All components are intended to be run on the same machine to a serve a set of
users. This group of users form the called a site and the machine is called the
site node. Multiple instances of Hades can be run for the same site, whereby
one node is primary and other nodes serve as secondary backup nodes.

Database (PostgreSQL)
---------------------
PostgreSQL was chosen as the backend database, because it's very mature
database, all other components support it as a backend and its Foreign Data
Wrapper combined with Materialized Views are a very simple and robust way to
implement asynchronous replication.

RADIUS (freeRADIUS)
-------------------
freeRADIUS is the de facto standard RADIUS open source server implementation.
All other alternatives are less supported on different platforms and don't
offer nearly as much features.

The generated configuration is for the 2.x line of freeRADIUS as the new 3.x
has not been packaged yet in Debian, which is the target platform of Hades.

Most modules and features of freeRADIUS have been disabled to only support
RADIUS MAC Authentication (or MAC Authentication Bypass) via PAP, CHAP and
EAP-MD5. The interoperability has only been verified with HP ProCurve switches,
patches for different lines of hardware are welcome.

Auth DNS (unbound)
------------------
DNS for authenticated users is provided by unbound.
The unbound instance has DNSSEC-enabled.
In the default configuration unbound runs as a standalone, recursive resolver.

dnsmasq could have been chosen as the resolver for authenticated as well, but it
its not capable of recursively resolving names itself and always needs a set of
upstream DNS servers to forward requests to.

Auth DHCP (dnsmasq)
-------------------
Hades currently uses dnsmasq as the DHCP server for authenticated users.
The well-known ISC DHCP server has not been chosen, because without patches, it
doesn't support reading static host reservations from a database.
dnsmasq does not support reading from a database either, but can be instructed
to reload its host reservations from disk without restarting.
ISC dhcpd must always be restarted.

There is a new DHCP server called kea also developed by ISC, which would be the
perfect fit for Hades, as it will support reading host reservations from
a relational database.
Unfortunately kea is still in development and this particular feature is not
yet fully implemented.
See https://kea.isc.org/wiki/HostReservationDesign for the current state of
affairs.

Unauth DNS (dnsmasq)
--------------------
The DNS server for unauthenticated users is a vital part of the captive portal
redirection.
It will respond to any DNS request with the unauth listen IP of the site node.
dnsmasq is very well suited for this unusual configuration.

There is a special entry for dns.msftncsi.com to assist with the Network
Connectivity Status Indicator service used in Microsoft products, such as
Windows.

Unauth DHCP (dnsmasq)
---------------------
The same dnsmasq process that provides unauth DNS provides unauth DHCP.
In this network users are given very short leases (two minutes is the default
values), so that they will renew their IP address very often and get an regular
after transitioning back into the network for authenticated users very quickly.

Site Agent (Celery)
-------------------
Other internal services and applications might want to contact the site node to
get a list of the latest authentication attempts at a particular switch port for
example.
Direct communication in a distributed system, such as Hades with potentially
many site nodes is therefore facilitated with the use of a central message queue
and the distributed task framework Celery.
The central message queue or broker is **not** part of Hades.
RabbitMQ or Redis is recommended.
Please see the `Celery Broker documentation <https://celery.readthedocs.org/en/latest/getting-started/brokers/index.html>`
