#!/usr/bin/env python
import os

from setuptools import setup, find_packages

sys_conf_dir = os.getenv("SYSCONFDIR", "/etc")
lib_dir = os.getenv("LIBDIR", "/usr/lib")


def read_readme() -> str:
    with open('README.md', 'r', encoding='utf-8') as f:
        return f.read()


classes = """
    Development Status :: 4 - Beta
    Intended Audience :: Developers
    Programming Language :: Python
    Programming Language :: Python :: 3
    Programming Language :: Python :: 3.7
    Programming Language :: Python :: 3.8
    Programming Language :: Python :: 3.9
    Programming Language :: Python :: 3.10
    Programming Language :: Python :: Implementation :: CPython
    Programming Language :: Python :: Implementation :: PyPy
    Operating System :: OS Independent
"""
classifiers = [s.strip() for s in classes.split('\n') if s]


setup(
    name='netkeeper',
    version='2.0.0',
    description='Netkeeper keeps your huawei router connected',
    long_description=read_readme(),
    long_description_content_type='text/markdown',
    author='Adam Schubert',
    author_email='adam.schubert@sg1-game.net',
    url='https://github.com/Salamek/netkeeper.git',
    license='GPL-3',
    classifiers=classifiers,
    packages=find_packages(exclude=['tests', 'tests.*']),
    install_requires=[
        'pyyaml',
        'docopt',
        'huawei-lte-api'
    ],
    test_suite="tests",
    tests_require=[
        'tox'
    ],
    package_data={'netkeeper': []},
    entry_points={
        'console_scripts': [
            'netkeeper = netkeeper.__main__:main',
        ],
    },
    data_files=[
        (os.path.join(lib_dir, 'systemd', 'system'), [
            'lib/systemd/system/netkeeper.service',
        ]),
        (os.path.join(sys_conf_dir, 'netkeeper'), [
            'etc/netkeeper/config.yml'
        ])
    ]
)
