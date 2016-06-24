from setuptools import Extension, find_packages, setup
from babel.messages import frontend as babel

setup(name='hades',
      version='0.1',
      description="Distributed AG DSN RADIUS MAC authentication. "
                  "Site node agent and captive portal",
      packages=find_packages('src', exclude=["*.tests"]),
      package_dir={'': 'src'},
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          "Flask",
          "Flask-Babel",
          "SQLAlchemy",
          "arpreq",
          "celery",
          "netaddr",
          "psycopg2",
          "pyroute2",
      ],
      scripts=[
          'src/scripts/hades',
      ],
      cmdclass={
          'compile_catalog': babel.compile_catalog,
          'extract_messages': babel.extract_messages,
          'init_catalog': babel.init_catalog,
          'update_catalog': babel.update_catalog,
      },
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'License :: OSI Approved :: MIT License',
          'Environment :: No Input/Output (Daemon)',
          'Environment :: Web Environment',
          'Intended Audience :: System Administrators',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 3 :: Only',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: Implementation :: CPython',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
          'Topic :: System :: Networking',
      ],
      )

