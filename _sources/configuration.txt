=============
Configuration
=============
Hades consists of multiple components.
The configuration of these components is tightly coupled.
The freeRADIUS server, the Celery worker and the Flask app for example must talk
to the PostgreSQL database, the nginx web server must talk to the uWSGI server,
etc.

To make the configuration as easy as possible, all components are configured
with a single configuration file.
The configuration file is a simple Python file with a series of assignments.
Most of the configuration options expect primitive data types as values such as
string, integers or booleans, while some require more complex types such as
:py:class:`list`s and :py:class:`dict`s or special data types such as
:py:class:`datetime.timedelta` or :py:class:`netaddr.IPNetwork`.

The various components, like nginx, are obviously not able to read this special
Python file.
The Hades startup script generates the appropriate configuration
for each service before the actual service daemon, nginx for example, is
executed.
The configuration is generated from Jinja2 templates, which can be found in the
:py:mod:`hades.config.templates` package of Hades.

Using Docker
============
If you use Docker to run Hades in containers you can specify the path to this
configuration file with `HADES_CONFIG` environment variable, e.g.::

   docker run -e HADES_CONFIG=/etc/hades/site.conf hades agent

The configuration file must be present inside Docker container, not the Docker
host! You can make the file available inside the Docker container by creating
your own Dockerfile which inherits from the hades Docker image and use `COPY`
or `ADD` or you use the Docker volume feature to bind mount the file, e.g.::

   docker run -v ~/site.conf:/etc/hades/site.conf -e HADES_CONFIG=/etc/hades/site.conf hades agent

Options Reference
=================
The following list of available options is automatically generated from the
Python classes that represent the options internally.
To use these options, put them into your configuration file without the
``hades.config.options`` prefix, e.g.::

   HADES_SITE_NAME = 'my_site'

.. automodule:: hades.config.options
   :member-order: bysource
   :members:
   :undoc-members:
   :exclude-members: OptionMeta, Option, equal_to, deferred_format
