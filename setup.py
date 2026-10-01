"""Distro installation paths; project metadata lives in pyproject.toml."""

import os
from pathlib import Path

from setuptools import setup

setup(
    data_files=[
        (str(Path(os.getenv('LIBDIR', '/usr/lib')) / 'systemd/system'), ['lib/systemd/system/netkeeper.service']),
        (str(Path(os.getenv('SYSCONFDIR', '/etc')) / 'netkeeper'), ['etc/netkeeper/config.yml']),
    ],
)
