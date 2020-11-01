.. _configuration:

*************
Configuration
*************
The configuration of the various :doc:`components` is tightly coupled and must
be kept consistent with regard to each other.
The the Celery worker, the DBus deputy, the FreeRADIUS server, and the Flask app
for example must talk to the PostgreSQL database, the nginx web server must talk
to the uWSGI server etc.

All of these components have their own custom configuration file format.
To relieve the administrators from learning all the different configuration file
formats, all the necessary options of the various components and making sure
that the configuration is consistent, Hades defines its own configuration file
and performs the configuration of the other components automatically for the
administrator and does basic error and consistency checking.
The default location of the central configuration file is
``/etc/hades/config.py``.

Hades can't fully abstract away the components, so some basic knowledge about
the components of Hades, or at least willingness to acquire it if necessary, is
required, especially if errors occur.
Monitoring the systemd journal is usually sufficient for debugging problems.

Syntax
======
The configuration file is a Python file, that should contain a series of
variable assignments for the various options listed below.
Most of the configuration options expect primitive data types as values such as
strings, integers or booleans, while some require more complex types such as
:class:`list` and :class:`dict` or special data types such as
:class:`datetime.timedelta` or :class:`netaddr.IPNetwork`.
You are free to use all the features of the Python programming, but complex
control flow or functions and classes should probably be avoided in a
configuration file.
For detailed information about Python syntax, please see the
:doc:`python:tutorial/index` and :doc:`python:reference/index`.

Importing Python modules other than the special data types from the standard
library or direct dependencies of Hades should also be avoided.
One can however use relative imports to spread options among multiple files.

.. code-block:: python
   :caption: secrets.py

   HADES_VRRP_PASSWORD = 'hunter2'

.. code-block:: python
   :caption: config.py

   from .secrets import HADES_VRRP_PASSWORD

Because you're using Python's built-in import system, you have to adhere to its
rules.
In particular, if you're trying to import files from other directories, those
directories must contain a file named ``__init__.py`` to denote that this
directory is a Python *package*.

.. warning::

   You can't import from parent or sibling directories with respect to your
   root configuration file. Doing :python:`from ..parent import file` from your
   root configuration file won't work as you intended, if it all.

Specifying the Config File
--------------------------
There are various ways to specify the configuration file for Hades.
By default Hades uses the file ``/etc/hades/config.py``.
The Hades command-line tools support the ``-c/--config`` switch to specify a
different file.
In addition, Hades supports the environment variable ``HADES_CONFIG``.
The environment variable is especially useful for the various Hades systemd
services.
All Hades systemd service units source the |EnvironmentFile|_
``/etc/default/hades``.

.. |EnvironmentFile| replace:: ``EnvironmentFile``
.. _EnvironmentFile: https://www.freedesktop.org/software/systemd/man/systemd.exec.html#id-1.16

The command-line switch ``-c/--config`` takes precedence over the environment
variable ``HADES_CONFIG``, which takes precedence over the default value.

Templates
=========
The various third-party components of Hades, like nginx,
are obviously not able to read Python configuration files.
The Hades components, that are written in Python, don't require this template
mechanism.
This covers hades-agent, hades-deputy, hades-unauth-portal, and the various
helper scripts.

The Hades systemd services generate the appropriate configuration for each
third-party component before the actual service daemon is executed.
The configuration files are also regenerated, if the services are restarted.
Reloading a service, if it supports it, does **not** regenerate the
configuration file.
You have to manually regenerate the configuration,
if you don't want to restart service.
For services that support it, the generated configuration is checked before the
service is started or reloaded.
These are the services based on *dnsmasq*, *FreeRADIUS*, and *unbound*.

The generated configuration files are stored in the ``hades`` subdirectory of
the system's runtime directory, ``/run/hades`` by default.

The configuration files are generated from Jinja2 templates.
For information about the syntax of Jinja2 templates,
see the
`Jinja2 documentation <http://jinja.pocoo.org/docs/latest/templates/>`_.

Manual Generation
-----------------
You might be in a situation, where you want to manually generate the third-party
config files. Doing this is very easy:

.. code-block:: console

   hades-generate-config nginx/nginx.conf.j2 /tmp/my-nginx.conf

This will compile the template ``nginx/nginx.conf.j2`` and output its result to
``/tmp/my-nginx.conf``.

The configuration of ``nginx`` however requires more than a file to work.
If the first argument passed to ``hades-generate-config`` refers to a directory,
the command will recursively compile all files ending with ``.j2`` into files
with the same name without the ``.j2`` extension and copy all other files and
directories as-is.

.. code-block:: console

   hades-generic-config nginx /tmp/my-nginx-config

Search Path
-----------
The templates and other files and directories are looked up in a set of
directories on the *template search path*.
By default, the template search path is comprised of the two directories
``/etc/hades/templates`` and ``/usr/share/hades/templates`` in this order.

The directory ``/usr/share/hades/templates`` contains the default templates
shipped with Hades, the directory ``/etc/hades/templates`` is intended for use
by the administrator to override the default templates, if deemed necessary.

The lookup algorithm is analogous to how ``systemd`` looks for its
`unit files <https://www.freedesktop.org/software/systemd/man/systemd.unit.html>`_
or how the shell finds
`executables <http://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html#tag_18_09_01_01>`_
on the ``PATH``.

Deletion Markers
----------------
Instead of overriding the contents of a file, it may be necessary or convenient
to omit files or directories from the generated configuration files.
The mechanism is again analogous to how systemd allows you to mask
with symbolic links to ``/dev/null``.

Options Reference
=================
The following list of available options is automatically generated from the
Python classes that represent the options internally.

.. automodule:: hades.config.options
   :member-order: bysource
   :members:
   :undoc-members:
   :exclude-members: CeleryOption, FlaskOption, Option, OptionMeta
