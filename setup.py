import re
from distutils.core import setup
from setuptools import find_packages

VERSIONFILE="bacula_stats/_version.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))

setup(
    name="bacula_stats",
    version=verstr,
    author="eayin2",
    author_email="eayin2@gmail.com",
    packages=find_packages(),
    url="https://github.com/eayin2/bacula_stats",
    description="CLI tool to display recent or all bacula backups in table blocks.",
    install_requires=["tabulate", "termcolor", "six", "psycopg2", "PyYAML", "voluptuous", "helputils"],
    entry_points={
        'console_scripts': [
            'bacula_stats = bacula_stats.bacula_stats:clidoor',
        ],
    },
)
