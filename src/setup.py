from setuptools import Extension, find_packages, setup

arpreq = Extension('arpreq', sources=['arpreq/arpreq.c'],
                   extra_compile_args=['-std=c11'])

setup(name='hades',
      version='0.1',
      description="Distributed AG DSN RADIUS MAC authentication. "
                  "Site node agent and captive portal",
      packages=find_packages(exclude=["*.tests"]),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          "Flask",
          "Flask-Babel",
          "SQLAlchemy",
          "psycopg2",
          "celery"
      ],
      ext_modules=[arpreq],
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

