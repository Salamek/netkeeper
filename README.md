# Netkeeper

Keeps internet connection open if possible (Restarts network LTE modem), this project uses https://github.com/Salamek/huawei-lte-api, see [supported devices list](https://github.com/Salamek/huawei-lte-api/blob/master/README.md)

![Screenshot](doc/info.jpg)

[![Code checks](https://github.com/Salamek/netkeeper/actions/workflows/python-test.yml/badge.svg)](https://github.com/Salamek/netkeeper/actions/workflows/python-test.yml)

> Please consider sponsoring if you're using this package commercially, my time is not free :) You can sponsor me by clicking on "Sponsor" button in top button row. Thank You.


## Installation

### Repository
You can also use these repositories maintained by me
#### Debian and derivatives

Add repository by running these commands

```
$ wget -O- https://repository.salamek.cz/deb/salamek.gpg | sudo tee /usr/share/keyrings/salamek-archive-keyring.gpg
$ echo "deb     [signed-by=/usr/share/keyrings/salamek-archive-keyring.gpg] https://repository.salamek.cz/deb/pub all main" | sudo tee /etc/apt/sources.list.d/salamek.cz.list
```

And then you can install a package netkeeper

```
$ apt update && apt install netkeeper
```

#### Archlinux

Add repository by adding this at end of file /etc/pacman.conf

```
[salamek]
Server = https://repository.salamek.cz/arch/pub/any
SigLevel = Optional
```

and then install by running

```
$ pacman -Sy netkeeper
```


## Configuration

Configuration is stored in `/etc/netkeeper/config.yml`:

```yml
TARGETS: ['google.com', '8.8.8.8', 'cloudflare.com']  # Targets to test
TARGETS_FAIL_THRESHOLD: 50  # More than 50% must fail to restart modem
MODEM_URL: 'http://admin:admin@192.168.8.1/'
RESTART_SERVICES: []  # List of systemd services to restart after modem has successfully regained connection 
CHECK_INTERVAL: 60  # seconds
```


## Usage

Package installs systemd service named `netkeeper.service` that monitors your router, to check that it is running run:

```bash
systemctl status netkeeper
```


The CLI uses Typer, with help available for each command:

```bash
netkeeper --help
netkeeper run --help
netkeeper run --config-prod --log-dir /var/log
netkeeper status
```

`run` accepts `--config-prod` for production configuration and `--log-dir DIR`
(or `-l DIR`) to also write logs to an existing, writable directory. The original
`--config_prod` and `--log_dir` spellings remain supported for existing service
files and scripts. Running `netkeeper` without arguments displays help.




## Development

Python 3.13 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev,test]'
./code-check.sh
```

The check script runs Ruff, strict Mypy, and pytest. Tests use mocked sockets and
router clients; they do not require root or a modem. Build release artifacts with
`python -m build`. Project metadata and tool settings live in `pyproject.toml`.
The small `setup.py` preserves systemd/config installation paths for distro builds
and supports the existing `LIBDIR` and `SYSCONFDIR` environment overrides.
