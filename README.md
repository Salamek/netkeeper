# Netkeeper

Keeps internet connection open if possible (Restarts network LTE modem), this project uses https://github.com/Salamek/huawei-lte-api, see [supported devices list](https://github.com/Salamek/huawei-lte-api/blob/master/README.md)

![Screenshot](doc/info.jpg)

[![Tox tests](https://github.com/Salamek/netkeeper/actions/workflows/python-test.yml/badge.svg)](https://github.com/Salamek/netkeeper/actions/workflows/python-test.yml)

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
TARGETS: ['google.com', '8.8.8.8', 'youtube.com']  # Targets to test
TARGETS_FAIL_THRESHOLD: 50  # <= 50% must fail to restart modem
MODEM_URL: 'http://admin:admin@192.168.8.1/'
RESTART_SERVICES: []  # List of systemd services to restart after modem has successfully regained connection 
CHECK_INTERVAL: 60  # seconds
```


## Usage

Package installs systemd service named `netkeeper.service` that monitors your router, to check that it is running run:

```bash
systemctl status netkeeper
```


```bash
Command details:
    run                 Run the application.
    status              Show status of router.
Usage:
    netkeeper run [-l DIR] [--config_prod]
    netkeeper (-h | --help)
    netkeeper status

Options:
    --config_prod               Load the production configuration instead of
                                development.
    -l DIR --log_dir=DIR        Log all statements to file in this directory
                                instead of stdout.
                                Only ERROR statements will go to stdout. stderr
                                is not used.
```


