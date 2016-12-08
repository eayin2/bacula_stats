from distutils.core import setup
from setuptools import find_packages

setup(
    name="bacula_stats",
    version="0.0.2",
    author="eayin2",
    author_email="eayin2@gmail.com",
    packages=find_packages(),
    url="https://github.com/eayin2/bacula_stats",
    description="CLI tool to display recent or all backups in table blocks.",
    install_requires=["tabulate", "termcolor", "six", "psycopg2", "PyYAML", "voluptuous", "helputils"],
    entry_points={
        'console_scripts': [
            'bacula_stats = bacula_stats.bacula_stats:clidoor',
        ],
    },
)
