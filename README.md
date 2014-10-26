Hades
=====
Hades is the AG DSN catchall VLAN Project

Goals
-----
* All devices that should not have access to the network are placed into a single VLAN (or
  multiple?). This applies to
  - devices with unknown MAC address
  - known devices of users that should be denied access to the network (e.g.
    abuse, overdue payment, traffic limit exceeded)
* Restrict traffic heavily in this VLAN
* Provide information (a website) to the users telling them why they are placed
  in the Hades

Components
----------
* Catchall DNS-Server (dnsmasq) resolving all names, except a few, to a single IP address
* Website using Flask to display information to the user
* Python C extension that probes the kernel ARP cache for MAC addresses of
  given IP addresses to allow identification of the devices
* iptables rules that forward to some whitelisted destination

