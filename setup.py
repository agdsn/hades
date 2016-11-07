from setuptools import find_packages, setup
from babel.messages import frontend as babel
from distutils.cmd import Command
from distutils.command.build import build
import shutil

class BuildProxy(build):
    user_options = build.user_options + [
        ('disable-bower', None, 'disable bower update during build'),
        ('disable-compile-catalog', None, 'disable babel compilation during build'),
    ]

    boolean_options = build.boolean_options + ['disable-bower', 'disable-compile-catalog']

    def initialize_options(self):
        self.disable_compile_catalog = False
        self.disable_bower = False
        super().initialize_options()

    def finalize_options(self):
        super().finalize_options()

    def run(self):
        if not self.disable_compile_catalog:
            self.run_command('compile_catalog')
        if not self.disable_bower:
            self.run_command('run_bower')
        super().run()

class BowerCommand(Command):
    user_options = []

    def initialize_options(self):
        self.disable_bower = False

    def finalize_options(self):
        pass

    def run(self):
        self.spawn(['npm', 'install', 'bower'])

        # Debian installs node binary as nodejs.
        node_cmd = 'node'
        if not shutil.which(node_cmd):
            node_cmd = 'nodejs'

        # Debian packaging process uses fakeroot.
        self.spawn([node_cmd, 'node_modules/bower/bin/bower', 'install', '--allow-root'])

setup(name='hades',
      version='0.1',
      author='Sebastian Schrader',
      author_email='sebastian.schrader@agdsn.de',
      url='https://github.com/agdsn/hades/',
      license='MIT',
      description="Distributed AG DSN RADIUS MAC authentication. "
                  "Site node agent and captive portal",
      packages=find_packages('src', exclude=["*.tests"]),
      package_dir={'': 'src'},
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          "arpreq",
          "Babel",
          "Celery",
          "Flask",
          "Flask-Babel",
          "Jinja2",
          "netaddr",
          "psycopg2",
          "pyroute2",
          "SQLAlchemy",
      ],
      entry_points={
          'console_scripts': [
              'hades-agent = hades.bin.agent:main',
              'hades-check-database = hades.bin.check_database:main',
              'hades-cleanup = hades.bin.cleanup:main',
              'hades-export-options = hades.bin.export_options:main',
              'hades-generate-template = hades.bin.generate_config:main',
              'hades-refresh = hades.bin.refresh:main',
              'hades-portal = hades.bin.portal:main',
              'hades-su = hades.bin.su:main',
          ],
      },
      scripts=[
          'src/scripts/control-database.sh',
          'src/scripts/control-network.sh',
          'src/scripts/functions.sh',
          'src/scripts/update-trust-anchor.sh',
      ],
      cmdclass={
          'build': BuildProxy,
          'run_bower': BowerCommand,
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
          'Intended Audience :: Telecommunications Industry',
          'Operating System :: POSIX :: Linux',
          'Programming Language :: Python :: 3 :: Only',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: SQL',
          'Programming Language :: Unix Shell',
          'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
          'Topic :: System :: Networking',
      ],
      )

