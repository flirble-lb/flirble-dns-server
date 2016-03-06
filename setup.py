#!/usr/bin/env python

import os, sys

try:
    from setuptools import Command, setup
except ImportError:
    from distutils.core import Command, setup

# Extract the variables and doc from the module without any
# importing that it does; this is so we can import from it
# without worrying about dependencies and thus extract useful
# metadata. This is most definitely a hack.
builddir = os.path.dirname(os.path.realpath(__file__)) + "/build"
try: os.mkdir(builddir)
except: pass
mpkg = builddir + "/__init__.py"
with open("FlirbleDNSServer/__init__.py", "r") as rfp:
    with open(mpkg, "w") as wfp:
        for line in rfp:
            if line.startswith("import ") or line.startswith("from "):
                continue
            wfp.write(line)
try:
    # Load our freshly minted module
    import build
    # And get the juicy metadata from it
    long_description = build.__doc__.rstrip() + "\n"
    version = build.version
except:
    print("ERROR: Can't retreive version/description information.")
    sys.exit(1)
finally:
    os.remove(mpkg)
    try: os.remove(mpkg+"c")
    except: pass
    try: os.remove(mpkg+"o")
    except: pass
    try: os.rmdir(builddir)
    except: pass


setup(name='FlirbleDNSServer',
      version = version,
      description = 'Flirble loadbalancing DNS server',
      long_description = long_description,
      author = 'Chris Luke',
      author_email = 'chrisy@flirble.org',
      url = 'https://git.flirble.org/flirble-lb/flirble-dns-server',
      packages = ['FlirbleDNSServer'],
      package_dir = {'FlirbleDNSServer': 'FlirbleDNSServer'},
      scripts = ['dns-server', 'init-rethinkdb', 'update-server'],
      requires = ['dnslib (>=0.9.2)', 'geoip2 (>=2.2.0)', 'lockfile (>=0.12.2)', 'rethinkdb (>=2.2.0)'],
      license = 'BSD',
      classifiers = [ "Topic :: Internet :: Name Service (DNS)",
                      "Programming Language :: Python :: 2",
                      ],
     )
