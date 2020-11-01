********
Overview
********

Hades is the authentication and authorization system of the AG DSN residential
network/student network.
It is a distributed system that provides RADIUS MAC authentication (also called
MAC Authentication Bypass on Cisco devices) to authenticate users via switches
that support it and offers the most essential networking services, DHCP and DNS,
for authenticated users.
Hades includes a basic captive portal that explains to unauthenticated users why
their authentication attempt failed.

External services may be integrated into the captive portal to e.g. allow user
to login with user account into a user management interface, a web mail
interface, or sign up via a web interface.

Table of Contents
=================
.. toctree::
   :maxdepth: 2

   self
   components
   networking
   replication
   configuration
   alternative-dns
   cli
   development
   api/hades
   genindex

Goals
=====
- Authenticate users without requiring any special software on the user side
- Provide DNS and DHCP for authenticated users
- Show an error page to unauthenticated users
- Support a whitelist of domains, that unauthenticated users can access
- Fault-Tolerance
- Isolate unauthenticated users properly from the rest of the network

Requirements
============

Debian
------
Hades was developed specifically for deployment on Debian.
In principle, Hades can run on any other Linux distribution,
but there was no need and more importantly no time to test this.
On the other hand, Hades provides native Debian packages that integrate nicely.

Hades provides a configure script, that determines all platform-specific paths,
so porting it to a different distribution.

For details, see :ref:`development`.

systemd
-------
Hades makes use of systemd.
Obviously systemd is used to start, stop, reload the various services of Hades
and ensure start-up order and dependencies.
Every decent init system does that.

Hades however uses some more advanced features,
which other init systems might not provide:

- Systemd, among other things, is used by keepalived to check the health status of
  other hades services.
- Network namespaces are created through systemd and ``ip netns``.
- Periodic tasks are implemented through systemd timers.

Again, in principle all of this could be made to work without systemd, but there
was neither the need, nor the time to do that.

Python
------
At least Python 3.5 is currently required to run Hades.

Building
========
The easiest way to build Hades is using `Docker <https://www.docker.com/>`_:

 .. code-block:: console

   $ docker-compose build --build-arg=UID=$(id -u) --build-arg=GID=$(id -g)
   $ docker-compose run --user builder --rm build.sh

The first command will build an image for development purposes.
The UID and GID build arguments ensure that the user, that is created within the
container has the same UID and GID as your current user.

The second command will start an ephemeral container, that mounts the project
directory and the build subdirectory into the container and builds the Debian
packages.

Afterwards you can find the Debian packages under ``./build``:

 .. code-block:: console

   $ ls -1 ./build
   arpreq_0.3.3-1_all.deb
   arpreq_0.3.3-1_amd64.buildinfo
   arpreq_0.3.3-1_amd64.changes
   hades
   hades_0.4.0_amd64.buildinfo
   hades_0.4.0_amd64.changes
   hades_0.4.0_amd64.deb
   python3-arpreq_0.3.3-1_all.deb
   python-arpreq
   python-arpreq_0.3.3-1_all.deb

If something fails or you just want to explore the build environment, you can
start a container in detached state and launch a shell in it afterwards:

 .. code-block:: console

   $ docker-compose up -d
   $ docker-compose exec --user builder bash

This way, systemd will start in the docker container, so that you can install
and test Hades inside the container:

 .. code-block:: console

   builder@0123456789ab:/$ cd /build
   builder@0123456789ab:~$ sudo dpkg -i python3-arpreq_0.3.3-1_all.deb
   builder@0123456789ab:~$ sudo dpkg -i hades_0.4.0_amd64.deb
   builder@0123456789ab:~$ cd /build/hades
   builder@0123456789ab:~/hades$ sudo cp tests/config.py /etc/hades
   builder@0123456789ab:~/hades$ sudo systemctl enable hades.service
   builder@0123456789ab:~/hades$ sudo systemctl start hades.service

Congratulations, you've successfully started a test instance of Hades!

Concepts
========

Site Node
---------

Asynchronous Replication
------------------------


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

