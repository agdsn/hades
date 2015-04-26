from distutils.core import setup, Extension

arpreq = Extension('arpreq', sources=['arpreq/arpreq.c'],
                   extra_compile_args=['-std=c11'])

setup(name='arpreq',
      version='0.1',
      description="Resolve an IP address to a MAC address by probing the"
      "Kernel's arp cache.",
      ext_modules=[arpreq])

