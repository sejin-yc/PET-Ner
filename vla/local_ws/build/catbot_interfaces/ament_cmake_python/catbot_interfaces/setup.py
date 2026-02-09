from setuptools import find_packages
from setuptools import setup

setup(
    name='catbot_interfaces',
    version='0.0.0',
    packages=find_packages(
        include=('catbot_interfaces', 'catbot_interfaces.*')),
)
