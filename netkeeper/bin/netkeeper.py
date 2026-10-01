#!/usr/bin/env python3
"""Netkeeper command line dispatcher and monitoring commands."""

import logging
import logging.handlers
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Annotated, ClassVar

import typer
from huawei_lte_api.Client import Client
from huawei_lte_api.Connection import Connection
from huawei_lte_api.enums.cradle import ConnectionStatusEnum
from huawei_lte_api.enums.device import ControlModeEnum
from huawei_lte_api.exceptions import ResponseErrorException
from yaml import safe_load

import netkeeper as app_root
from netkeeper.config import Config
from netkeeper.ext.multiping import MultiPingSocketError, multi_ping

APP_ROOT_FOLDER = Path(app_root.__file__).resolve().parent


class CustomFormatter(logging.Formatter):
    LEVEL_MAP: ClassVar[dict[int, str]] = {logging.FATAL: 'F', logging.ERROR: 'E', logging.WARNING: 'W', logging.INFO: 'I', logging.DEBUG: 'D'}

    def format(self, record: logging.LogRecord) -> str:
        record.levelletter = self.LEVEL_MAP[record.levelno]
        return super().format(record)


def setup_logging(name: str | None = None, level: int = logging.DEBUG, log_dir: str | None = None) -> None:
    """Setup Google-Style logging for the entire application.

    At first I hated this but I had to use it for work, and now I prefer it. Who knew?
    From: https://github.com/twitter/commons/blob/master/src/python/twitter/common/log/formatters/glog.py

    Always logs DEBUG statements somewhere.

    Positional arguments:
    name -- Append this string to the log file filename.
    """
    log_to_disk = False
    if log_dir:
        if not Path(log_dir).is_dir():
            print(f'ERROR: Directory {log_dir} does not exist.')
            sys.exit(1)
        if not os.access(log_dir, os.W_OK):
            print(f'ERROR: No permissions to write to directory {log_dir}.')
            sys.exit(1)
        log_to_disk = True

    fmt = '%(levelletter)s%(asctime)s.%(msecs).03d %(process)d %(filename)s:%(lineno)d] %(message)s'
    datefmt = '%m%d %H:%M:%S'
    formatter = CustomFormatter(fmt, datefmt)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console_handler)

    if log_to_disk:
        file_name = Path(log_dir or '.') / f'netkeeper_{name}.log'
        file_handler = logging.handlers.TimedRotatingFileHandler(file_name, when='d', backupCount=7)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def get_config(config_class_string: str, yaml_files: list[str] | None = None) -> Config:
    """Create an independent config instance, then apply YAML files in order."""
    config_module, config_class = config_class_string.rsplit('.', 1)
    config_type = getattr(import_module(config_module), config_class)
    if not isinstance(config_type, type) or not issubclass(config_type, Config):
        message = f'{config_class_string} is not a Config subclass'
        raise TypeError(message)
    config = config_type()
    if yaml_files is None:
        yaml_files = [
            str(path)
            for path in (
                Path('/etc/netkeeper/config.yml'),
                APP_ROOT_FOLDER.parent / 'config.yml',
                APP_ROOT_FOLDER / 'config.yml',
            )
            if path.exists()
        ]

    for filename in yaml_files:
        print(f'Loading config from {filename}')
        with Path(filename).open(encoding='utf-8') as config_file:
            loaded: object = safe_load(config_file)
        if not isinstance(loaded, dict) or not all(isinstance(key, str) for key in loaded):
            message = f'Failed to parse configuration {filename}'
            raise ValueError(message)
        for key, value in loaded.items():
            if key not in config.__dataclass_fields__:
                message = f'Unknown configuration setting: {key}'
                raise ValueError(message)
            setattr(config, key, value)
    config.validate()
    return config


def print_table(table_rows: Mapping[str, str], header: str | None = None) -> None:
    max_len_key = max(len('Item'), len(header or '') - 10, *(len(key) for key in table_rows))
    max_len_val = max([len('Value'), *(len(value) for value in table_rows.values())])

    header_format = f'| {{:{max_len_key + max_len_val + 3}s}} |'
    row_format = f'| {{:{max_len_key}s}} | {{:{max_len_val}s}} |'
    row_format_separator = f'| {{:{max_len_key}s}} + {{:{max_len_val}s}} |'

    print('+{}+'.format('-' * (max_len_key + max_len_val + 5)))

    if header:
        print(header_format.format(header))
        print(row_format_separator.format('-' * max_len_key, '-' * max_len_val))

    print(row_format.format('Item', 'Value'))
    print(row_format_separator.format('-' * max_len_key, '-' * max_len_val))
    for key in table_rows:
        print(row_format.format(key, table_rows[key]))

    print('+{}+'.format('-' * (max_len_key + max_len_val + 5)))


def is_connection_error(targets: list[str], threshold: int) -> bool:
    try:
        _, no_responses = multi_ping(targets, timeout=2, retry=3)
    except MultiPingSocketError:
        return True
    else:
        error_rate = (len(no_responses) / len(targets)) * 100
        return error_rate > threshold


def restart_modem_and_wait_for_alive(connection: Connection, log: logging.Logger) -> None:
    client = Client(connection)
    log.warning('Restarting modem!')
    client.device.set_control(ControlModeEnum.REBOOT)
    log.warning('Waiting for modem to restart')
    time.sleep(20)
    log.warning('Waiting for modem to become live')
    while True:
        try:
            connection.reload()
            client.monitoring.status()
        except ResponseErrorException as e:
            log.warning('Modem not available', exc_info=e)
            time.sleep(20)
        else:
            log.warning('Modem booted')
            return


def call_systemd(service_name: str, argument: str) -> bool:
    found_systemctl = shutil.which('systemctl')
    if not found_systemctl:
        message = 'systemctl binary was not found'
        raise ValueError(message)

    with subprocess.Popen([found_systemctl, argument, '--quiet', service_name]) as p:  # noqa: S603 - systemctl is resolved locally; arguments are passed without a shell.
        p.wait()
        return p.returncode == 0


def is_service_active(service_name: str) -> bool:
    return call_systemd(service_name, 'is-active')


def is_service_enabled(service_name: str) -> bool:
    return call_systemd(service_name, 'is-enabled')


def restart_service(service_name: str) -> bool:
    return call_systemd(service_name, 'restart')


@dataclass
class MonitorState:
    connected_counter: int = 0
    connecting_counter: int = 0
    restart_counter: int = 0
    after_reboot: bool = False

    def restart(self, connection: Connection, log: logging.Logger) -> int:
        if self.restart_counter >= 5:
            self.restart_counter = 0
            return 60 * 60
        restart_modem_and_wait_for_alive(connection, log)
        self.restart_counter += 1
        self.after_reboot = True
        return 1

    def check_modem(self, options: Config, log: logging.Logger) -> int:
        connection = Connection(options.MODEM_URL)
        client = Client(connection)
        information = client.device.information()
        monitoring = client.monitoring.status()
        connection_status = int(monitoring['ConnectionStatus'])
        if information['workmode'] == 'LTE':
            signal_strength = int(monitoring['SignalIcon'])
        elif information['workmode'] == 'NR-5GC':
            signal_strength = int(monitoring['SignalIconNr'])
        else:
            signal_strength = 0

        if connection_status == ConnectionStatusEnum.CONNECTED:
            if self.connected_counter == 0:
                log.warning('Modem thinks its connected, sleeping for 1 minute...')
                self.connected_counter += 1
                return 60
            if signal_strength >= 2:
                log.warning('Signal is good and modem reports connected, maybe error on target side ?')
                return options.CHECK_INTERVAL
            log.warning('BAD signal (%s) detected, restart', signal_strength)
            self.connected_counter = 0
        elif connection_status == ConnectionStatusEnum.CONNECTING:
            if self.connecting_counter == 0:
                log.warning('Modem is in connecting state, sleeping for 2 minutes...')
                self.connecting_counter += 1
                return 60 * 2
            log.warning('Modem is in connecting state second time, restart')
            self.connecting_counter = 0
        else:
            log.warning('Modem is in connection state: %s, restarting...', connection_status)
        return self.restart(connection, log)

    def recover(self, options: Config, log: logging.Logger) -> None:
        self.connected_counter = 0
        self.connecting_counter = 0
        self.restart_counter = 0
        if self.after_reboot:
            self.after_reboot = False
            for service in options.RESTART_SERVICES:
                if is_service_active(service) or is_service_enabled(service):
                    log.warning('Restarting service %s', service)
                    restart_service(service)


def run(options: Config, log_dir: str | None = None) -> None:
    setup_logging('run', logging.DEBUG if options.DEBUG else logging.WARNING, log_dir)
    log = logging.getLogger(__name__)
    state = MonitorState()
    while True:
        if is_connection_error(options.TARGETS, options.TARGETS_FAIL_THRESHOLD):
            log.warning('Connection error rate reached threshold')
            try:
                sleep_time = state.check_modem(options, log)
            except ResponseErrorException as e:
                log.warning('Connection to modem failed, sleeping 10 minutes...', exc_info=e)
                sleep_time = 60 * 10
        else:
            state.recover(options, log)
            sleep_time = options.CHECK_INTERVAL
            log.info('All is OK, sleeping for %ss', sleep_time)
        time.sleep(sleep_time)


def status(options: Config) -> None:

    connection = Connection(options.MODEM_URL)
    client = Client(connection)

    table_rows = {}

    try:
        responses, no_responses = multi_ping(options.TARGETS, timeout=2, retry=3)
    except MultiPingSocketError as e:
        responses = {}
        no_responses = []
        table_rows[str(e)] = 'ERROR'

    for address, ping in responses.items():
        table_rows[address] = f'ONLINE: {ping:.4f}s'

    for no_response in no_responses:
        table_rows[no_response] = '!!!OFF-LINE!!!'

    print_table(table_rows, 'Ping Info')

    information = client.device.information()
    monitoring = client.monitoring.status()
    if information['workmode'] == 'LTE':
        signal_strength = monitoring.get('SignalIcon')
    elif information['workmode'] == 'NR-5GC':
        signal_strength = monitoring.get('SignalIconNr')
    else:
        signal_strength = 0

    connection_status_to_text = {
        ConnectionStatusEnum.CONNECTED: 'Connected',
        ConnectionStatusEnum.CONNECTING: 'Connecting',
        ConnectionStatusEnum.DISCONNECTED: 'Disconnected',
        ConnectionStatusEnum.DISCONNECTING: 'Disconnecting',
        ConnectionStatusEnum.CONNECT_FAILED: 'Connect FAILED',
        ConnectionStatusEnum.CONNECT_STATUS_ERROR: 'Connect ERROR',
        ConnectionStatusEnum.CONNECT_STATUS_NULL: 'Connect NULL',
    }

    table_rows = {
        'Device name': information.get('DeviceName', '???'),
        'Device serial number': information.get('SerialNumber', '???'),
        'Device IMEI': information.get('Imei', '???'),
        'Device version': information.get('HardwareVersion', '???'),
        'Device MAC': information.get('MacAddress1', '???'),
        'Work mode': information.get('workmode', '???'),
        'Internet connection status': connection_status_to_text.get(ConnectionStatusEnum(int(monitoring.get('ConnectionStatus', 906))), 'Unknown'),
        'Signal': '{}/{}'.format(signal_strength, monitoring.get('maxsignal')),
        'WAN IP': str(monitoring.get('WanIPAddress', information.get('WanIPAddress', '???'))),
        'Primary DNS': monitoring.get('PrimaryDns', '???'),
        'Secondary DNS': monitoring.get('SecondaryDns', '???'),
    }

    print_table(table_rows, 'Modem Info')


cli = typer.Typer(no_args_is_help=True, help='Keep your Huawei router connected.', context_settings={'help_option_names': ['-h', '--help']})


@cli.callback()
def root_callback() -> None:
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))


@cli.command('run')
def run_command(
    *,
    config_prod: Annotated[
        bool,
        typer.Option('--config-prod', '--config_prod', help='Load production configuration instead of development.'),
    ] = False,
    log_dir: Annotated[
        Path | None,
        typer.Option('--log-dir', '--log_dir', '-l', exists=True, file_okay=False, writable=True, help='Also write logs to this directory.'),
    ] = None,
) -> None:
    """Monitor connectivity and restart the router when needed."""
    config = get_config('netkeeper.config.Production' if config_prod else 'netkeeper.config.Config')
    run(config, str(log_dir) if log_dir is not None else None)


@cli.command('status')
def status_command() -> None:
    """Show router status and ping results."""
    status(get_config('netkeeper.config.Config'))


def main(argv: list[str] | None = None) -> int:
    cli(args=list(argv) if argv is not None else None, standalone_mode=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
