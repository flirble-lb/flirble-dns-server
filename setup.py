#!/usr/bin/env python

try:
    from setuptools import Command, setup
except ImportError:
    from distutils.core import Command, setup

import FlirbleDNSServer
long_description = FlirbleDNSServer.__doc__.rstrip() + "\n"
version = FlirbleDNSServer.version

class GenerateReadme(Command):
    description = "Generates README file from long_description"
    user_options = []
    def initialize_options(self): pass
    def finalize_options(self): pass
    def run(self):
        open("README","w").write(long_description)

setup(name='FlirbleDNSServer',
      version = version,
      description = 'Flirble loadbalancing DNS server',
      long_description = long_description,
      author = 'Chris Luke',
      author_email = 'chrisy@flirble.org',
      url = 'https://git.flirble.org/flirble-lb/flirble-dns-server',
      cmdclass = {'readme': GenerateReadme},
      packages = ['FlirbleDNSServer'],
      package_dir = {'FlirbleDNSServer': 'FlirbleDNSServer'},
      scripts = ['dns-server', 'init-rethinkdb', 'update-server'],
      requires = ['dnslib (>=0.9.2)', 'geoip2 (>=2.2.0)', 'lockfile (>=0.12.2)', 'rethinkdb (>=2.2.0)'],
      license = 'BSD',
      classifiers = [ "Topic :: Internet :: Name Service (DNS)",
                      "Programming Language :: Python :: 2",
                      "Programming Language :: Python :: 3",
                      ],
     )
