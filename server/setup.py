#! /usr/bin/env python
from setuptools import setup, find_packages
from io import open

setup(
    name='lights-433',
    packages=find_packages(exclude=["tests"]),
    version=0.1,
    description='A small webserver for talking to an Arduino that controls'
                '433Mhz inbound and outbound radios.',
    author='Dillon Dixon',
    author_email='dillondixon@gmail.com',
    url='https://github.com/ownaginatious/lights-433',
    license='MIT',
    zip_safe=True,
    install_requires=[line.strip()
                      for line in open("requirements.txt", "r",
                                       encoding="utf-8").readlines()],
    entry_points = {
        "console_scripts": [
            "lights433 = lights_433.main:main",
        ],
    },
)
