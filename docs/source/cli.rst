*************
CLI Utilities
*************

hades-agent
===========
.. argparse::
   :module: hades.bin.agent
   :func: create_parser
   :prog: hades-agent

hades-check-database
====================
.. argparse::
   :module: hades.bin.check_database
   :func: create_parser
   :prog: hades-check-database

hades-deputy
============
.. argparse::
   :module: hades.bin.deputy
   :func: create_parser
   :prog: hades-deputy

hades-dhcp-script-standalone
============================
.. warning:: Please don't use this script in production,
    as it interferes with the (synced) lease state of the DHCP server.
    In production, this script is not used, but instead the
    :mod:`hades-lease-server <hades.bin.lease_server>`.

.. argparse::
   :module: hades.bin.dhcp_script
   :func: create_parser
   :prog: hades-dhcp-script-standalone

hades-export-options
====================
.. argparse::
   :module: hades.bin.export_options
   :func: create_parser
   :prog: hades-export-options

hades-generate-config
=====================
.. argparse::
   :module: hades.bin.generate_config
   :func: create_parser
   :prog: hades-generate-config

hades-lease-server
==================
.. argparse::
   :module: hades.bin.lease_server
   :func: create_parser
   :prog: hades-lease-server

hades-portal
============
Does not take arguments.

hades-vrrp-notify
=================
.. argparse::
   :module: hades.bin.vrrp_notify
   :func: create_parser
   :prog: hades-vrrp-notify
