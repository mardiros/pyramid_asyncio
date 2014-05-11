import os
import sys
from setuptools import setup, find_packages


py_version = sys.version_info[:2]
if py_version < (3, 3):
    raise Exception("websockets requires Python >= 3.3.")

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, 'README.rst')) as readme:
    README = readme.read()
with open(os.path.join(here, 'CHANGES.rst')) as changes:
    CHANGES = changes.read()


requires = [
    'pyramid',
    'gunicorn',
    'aiohttp'
    ]

if py_version < (3, 4):
    requires.append('asyncio')


setup(name='pyramid-asyncio',
      version='0.0',
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
      test_suite='pyramid_asyncio',
      install_requires=requires,
      license="BSD-derived (http://www.repoze.org/LICENSE.txt)",
      entry_points = """\
      [pyramid.scaffold]
      aio_jinja2=pyramid_asyncio.scaffolds:AioJinja2Template
      """
      )
