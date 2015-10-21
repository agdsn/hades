Networking
==========
Hades was designed with the AG DSN network topology in mind.
In principal four different types of IP subnets were assumed/are supported:

- internal subnets: Subnet for internal services that should not be exposed
  to users, e.g. RADIUS, VRRP
- an unauth subnet: A private subnet for all unauthorized users of a site.
  DNS, DHCP and a captive portal are offered on this network
- an auth subnet: The subnet where the site node listens to offer services to
  authorized users, e.g. DNS and DHCP
- the user subnets: The actual subnets of authorized users

A Hades site note is expected to be directly attached to the first three types
of subnets (internal, unauth, auth).
A site node must not be attached directly to the user subnets.
Authenticated users must therefore be routed to the site node.
This is due to VLAN transitions.

VLAN Transitions
----------------
The authorization status of users may change, previously authorized users may
become unauthorized and subsequently switch from the auth network to the unauth
network. Users or rather the network stack of their devices won't notice this
switch and retain their previously assigned IP address. This could be handled
with short DHCP lease times, short lease times are however not recommended.
RFC 2131 recommends a minimum lease time of one hour for production systems.

In Hades we handle this problem differently, by allowing the user to retain
their original user network IP in the unauth network. This is accomplished by
adding the IP addresses of the default gateways of the user networks to the
unauth interface. In addition gratuitous ARP requests are broadcasted
periodically to notify the users that the MAC address of the default gateway
has changed.

This approach works, but has a big problem. Authenticated users also make
requests (DNS and DHCP) to the site node. The Kernel would either discard these
requests if strict reverse path forwarding/filtering is enabled, because the
requests are arriving on the wrong interface according to the Kernel's routing
table (because the Kernel thinks requests from the user networks should arrive
on the unauth interface), or replies to the requests would be sent out on the
unauth interface.

How can we handle this? We would have to route replies for connections from IP
addresses in the user networks depending on which interface a connection (not a
packet) originated from. This is exactly what we do using policy routing. Hades
sets up two different routing tables, one for connections originating from the
unauth interface (default table id 2) and one for any other connection (default
table id 1). The main routing table of the Kernel is only used as a template to
setup the other tables.

Fail-Over (VRRP)
----------------
Hades employs the Virtual Router Redundancy Protocol (VRRP) to allow multiple
site node instances for a single sites.
It uses keepalived

Even if there is only a single site node instance per site, keepalived is still
started to setup most of the network configuration.
