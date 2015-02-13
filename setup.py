import os
import sys
import re

from setuptools import setup, find_packages

NAME = 'pyramid-asyncio'

py_version = sys.version_info[:2]
if py_version < (3, 3):
    raise Exception("{name} requires Python >= 3.3.".format(name=NAME))

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.rst')) as readme:
    README = readme.read()
with open(os.path.join(here, 'CHANGES.rst')) as changes:
    CHANGES = changes.read()

with open(os.path.join(here, NAME.replace('-', '_'),
                       '__init__.py')) as version:
    VERSION = re.compile(r".*__version__ = '(.*?)'",
                         re.S).match(version.read()).group(1)


requires = [
    'pyramid',
    'gunicorn >= 19.0',
    'aiohttp',
    ]

extras_require = {
    'session': ['pyramid-kvs >= 0.2',  # XXX unreleased
                'asyncio-redis',
                'simplejson'
                ]
}

if py_version < (3, 4):
    requires.append('asyncio')


setup(name=NAME,
      version=VERSION,
      description='Pyramid Asyncio Glue',
      # long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Framework :: Pyramid",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
        "Intended Audience :: Developers",
        "License :: Repoze Public License",
        ],
      author='Guillaume Gauvrit',
      author_email='guillaume@gauvr.it',
      url='https://github.com/mardiros/pyramid_asyncio',
      keywords='pyramid asyncio',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      test_suite='{name}.tests'.format(name=NAME),
      install_requires=requires,
      license="BSD-derived (http://www.repoze.org/LICENSE.txt)",
      extras_require=extras_require,
      entry_points = """\
      [pyramid.scaffold]
      aio_jinja2=pyramid_asyncio.scaffolds:AioJinja2Template
      """
      )
