.. _components:

**********
Components
**********

Overview
========
Hades consists of quite a number of different components:

- A database (PostgresSQL)
- A RADIUS server (FreeRADIUS)
- A DNS resolver for authorized users (unbound)
- A DHCP server for authorized users (dnsmasq)
- A DNS resolver for unauthorized users (again dnsmasq, but a separate instance)
- A DHCP server for unauthorized users (again dnsmasq, but same instance as unauthorized DNS)
- A privileged daemon, called deputy, that provides a DBus API for local commands
- An agent executing regular tasks and waiting for commands (Celery worker)
- A Flask web application providing a captive portal landing page
- An WSGI application server (uwsgi) hosting the Flask application
- A web server (nginx) forwarding requests to the application server
- Multiple VRRP instances (keepalived) providing automatic fail-over between multiple Hades installations
- Systemd units and timers to orchestrate all the components

All components are intended to be run on the same machine to a serve a set of
users. This group of users constitute a *site* and the machine is called the
*site node*. Multiple instances of Hades can be run for the same site, whereby
one node is primary and other nodes serve as secondary backup nodes.

Database (PostgreSQL)
=====================
`PostgreSQL <https://www.postgresql.org/>`_ was chosen as the backend database,
because it's very mature
database, all other components support it as a backend and its Foreign Data
Wrapper combined with Materialized Views are a very simple and robust way to
implement asynchronous replication.

RADIUS (FreeRADIUS)
===================
`FreeRADIUS <http://freeradius.org/>`_ is the de facto standard RADIUS open
source server implementation.
All other alternatives are less supported on different platforms and don't
offer nearly as much features.

Most modules and features of FreeRADIUS have been disabled to only support
RADIUS MAC Authentication (or MAC Authentication Bypass) via PAP, CHAP and
EAP-MD5. The interoperability has only been verified with HP ProCurve switches,
patches for different lines of hardware are welcome.

Auth DNS (unbound)
==================
DNS for authenticated users is provided by `unbound <https://www.unbound.net/>`_.
The unbound instance has DNSSEC enabled.
In the default configuration unbound runs as a standalone, recursive resolver.

dnsmasq could have been chosen as the resolver for authenticated as well, but it
its not capable of recursively resolving names itself and always needs a set of
upstream DNS servers to forward requests to.

There are actually two separate unbound instances running, the *pristine*
instance and the *alternative* instance. All DNS requests by authenticated users
are normally handled by the *pristine* instance, but requests from IP addresses
can be dispatched to the *alternative* instance using an *ipset*.

See :doc:`alternative-dns` for details.

Auth DHCP (dnsmasq)
===================
Hades currently uses `dnsmasq <http://www.thekelleys.org.uk/dnsmasq/doc.html>`_
as the DHCP server for authenticated users.
The well-known ISC DHCP server has not been chosen, because without patches, it
doesn't support reading static host reservations from a database.
dnsmasq does not support reading from a database either, but can be instructed
to reload its host reservations from disk without restarting.
ISC dhcpd must always be restarted.

dnsmasq's DHCP leases are stored in the local PostgreSQL database through the
``--dhcp-script`` mechanism of dnsmasq. dnsmasq
The `dnsmasq man page <http://www.thekelleys.org.uk/dnsmasq/docs/dnsmasq-man.html>`_
describes the details.

There is a new DHCP server called *kea* also developed by ISC, which would be
the perfect fit for Hades, as it will support reading host reservations from
a relational database.
See https://kea.isc.org/wiki/HostReservationDesign for the details.

Unauth DNS (dnsmasq)
====================
The DNS server for unauthenticated users is a vital part of the captive portal
redirection.
It will respond to any DNS request with the unauth listen IP of the site node.
dnsmasq is very well suited for this unusual configuration.

There is a special entry for dns.msftncsi.com to assist with the Network
Connectivity Status Indicator service used in Microsoft products, such as
Windows.

Unauth DHCP (dnsmasq)
=====================
The same dnsmasq process that provides unauth DNS provides unauth DHCP.
In this network users are given very short leases (two minutes is the default),
so that they will renew their IP address very often and get a regular lease
after transitioning back into the network for authenticated users very quickly.

Site Agent (Celery)
===================
Other applications might want to interact with Hades site nodes to query
information, such as the latest authentication attempts at a particular switch
port for example.

Direct communication in a distributed system, such as Hades with many nodes is
notoriously difficult. There are potentially multiple sites with multiple
site nodes and the nodes may fail or change roles at any time.

To abstract all this complexity away from API users, communication between the
site nodes and other applications is therefore facilitated with the use of a
central RabbitMQ message queue and the distributed task framework Celery.
Although Celery supports different broker backends,
only RabbitMQ is supported by Hades at this point,
because Hades uses advanced AMQP features, which are not available on simpler
brokers, such as Redis.
Please see the `Celery documentation <http://docs.celeryproject.org/>`_ for more
information about Celery.

The central message queue **not** part of Hades, you must provide your own,
if you want to use the API.
If you don't need the API, you can simply disable the ``hades-agent`` systemd
service, it is not required for other functionality.

Deputy (DBus)
=============
Hades makes heavy use of privilege separations and runs daemons as different
users.
For a few operations however root privileges are necessary.
These operations are performed by a small DBus service.
This service is available to the agent.

The name is reference to the
`confused deputy problem <https://en.wikipedia.org/wiki/Confused_deputy_problem>`_.

VRRP (keepalived)
=================
Hades employs the Virtual Router Redundancy Protocol (VRRP) to allow multiple
site node instances for a single sites via `keepalived <http://www.keepalived.org/>`_.

Even if there is only a single site node, keepalived is still required,
because it is used to setup parts of the network configuration.
You may try to run Hades without keepalived, but this is not recommended,
because you would have to take of the proper network setup yourself.
Furthermore you might later decide to deploy more than site node.
