from setuptools import Extension, find_packages, setup

arpreq = Extension('arpreq', sources=['arpreq/arpreq.c'],
                   extra_compile_args=['-std=c11'])

setup(name='hades',
      version='0.1',
      description="Resolve an IP address to a MAC address by probing the "
                  "Kernel's arp cache.",
      packages=find_packages(exclude=["*.tests"]),
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          "Flask",
          "Flask-Babel",
          "Flask-SQLAlchemy",
          "SQLAlchemy",
          "psycopg2",
          "celery"
      ],
      ext_modules=[arpreq])

