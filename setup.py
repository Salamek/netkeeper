#!/usr/bin/env python
import os
import re
import sys

from setuptools import setup, find_packages

sys_conf_dir = os.getenv("SYSCONFDIR", "/etc")


def get_requirements(filename):
    return open(os.path.join(filename)).read().splitlines()


classes = """
    Development Status :: 4 - Beta
    Intended Audience :: Developers
    Programming Language :: Python
    Programming Language :: Python :: 2
    Programming Language :: Python :: 2.7
    Programming Language :: Python :: 3
    Programming Language :: Python :: 3.3
    Programming Language :: Python :: 3.4
    Programming Language :: Python :: 3.5
    Programming Language :: Python :: 3.6
    Programming Language :: Python :: Implementation :: CPython
    Programming Language :: Python :: Implementation :: PyPy
    Operating System :: OS Independent
"""
classifiers = [s.strip() for s in classes.split('\n') if s]


install_requires = get_requirements('requirements.txt')
if sys.version_info < (3, 0):
    install_requires.append('futures')


extra_files = []

setup(
    name='granad-gatekeeper',
    version='1.0.1',
    description='BESY GraNad Gatekeeper',
    long_description=open('README.md').read(),
    author='Adam Schubert',
    author_email='adam.schubert@sg1-game.net',
    url='https://gitlab.salamek.cz/sadam/granad-gatekeeper.git',
    license='PROPRIETARY',
    classifiers=classifiers,
    packages=find_packages(exclude=['tests', 'tests.*']),
    install_requires=install_requires,
    test_suite="tests",
    tests_require=install_requires,
    package_data={'granad-gatekeeper': extra_files},
    entry_points={
        'console_scripts': [
            'granad-gatekeeper = granad_gatekeeper.__main__:main',
        ],
    },
    data_files=[
        (os.path.join(sys_conf_dir, 'systemd', 'system'), [
            'etc/systemd/system/granad-gatekeeper.service'
        ]),
        (os.path.join(sys_conf_dir, 'granad-gatekeeper'), [
            'etc/granad-gatekeeper/config.yml'
        ])
    ]
)
