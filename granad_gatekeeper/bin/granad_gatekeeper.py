#!/usr/bin/env python3
"""Main entry-point into the 'GraNad RS232' Flask and Celery application.

This is a BESY GraNad RS232

License: PROPRIETARY
Website: https://gitlab.salamek.cz/sadam/granad-gatekeeper.git

Command details:
    run                 Run the application.
    detect_tty          Detect tty ports
    
Usage:
    granad-gatekeeper run [-l DIR] [--config_prod]
    granad-gatekeeper (-h | --help)
    granad-gatekeeper status

Options:
    --config_prod               Load the production configuration instead of
                                development.
    -l DIR --log_dir=DIR        Log all statements to file in this directory
                                instead of stdout.
                                Only ERROR statements will go to stdout. stderr
                                is not used.
"""

import logging
import logging.handlers
import os
import time
import signal
from importlib import import_module
from yaml import load
import sys
from functools import wraps
from docopt import docopt
import granad_gatekeeper as app_root
from granad_gatekeeper.ext.multiping import multi_ping
from huawei_lte_api.AuthorizedConnection import AuthorizedConnection
from huawei_lte_api.Client import Client
from huawei_lte_api.enums.cradle import ConnectionStatusEnum


OPTIONS = docopt(__doc__)
APP_ROOT_FOLDER = os.path.abspath(os.path.dirname(app_root.__file__))


class CustomFormatter(logging.Formatter):
    LEVEL_MAP = {logging.FATAL: 'F', logging.ERROR: 'E', logging.WARN: 'W', logging.INFO: 'I', logging.DEBUG: 'D'}

    def format(self, record):
        record.levelletter = self.LEVEL_MAP[record.levelno]
        return super(CustomFormatter, self).format(record)


def setup_logging(name=None, level=logging.DEBUG):
    """Setup Google-Style logging for the entire application.

    At first I hated this but I had to use it for work, and now I prefer it. Who knew?
    From: https://github.com/twitter/commons/blob/master/src/python/twitter/common/log/formatters/glog.py

    Always logs DEBUG statements somewhere.

    Positional arguments:
    name -- Append this string to the log file filename.
    """

    log_to_disk = False
    if OPTIONS['--log_dir']:
        if not os.path.isdir(OPTIONS['--log_dir']):
            print('ERROR: Directory {} does not exist.'.format(OPTIONS['--log_dir']))
            sys.exit(1)
        if not os.access(OPTIONS['--log_dir'], os.W_OK):
            print('ERROR: No permissions to write to directory {}.'.format(OPTIONS['--log_dir']))
            sys.exit(1)
        log_to_disk = True

    fmt = '%(levelletter)s%(asctime)s.%(msecs).03d %(process)d %(filename)s:%(lineno)d] %(message)s'
    datefmt = '%m%d %H:%M:%S'
    formatter = CustomFormatter(fmt, datefmt)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.ERROR if log_to_disk else logging.DEBUG)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console_handler)

    if log_to_disk:
        file_name = os.path.join(OPTIONS['--log_dir'], 'granad_rs232_{}.log'.format(name))
        file_handler = logging.handlers.TimedRotatingFileHandler(file_name, when='d', backupCount=7)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def get_config(config_class_string, yaml_files=None):
    """Load the Flask config from a class.
    Positional arguments:
    config_class_string -- string representation of a configuration class that will be loaded (e.g.
        'pypi_portal.config.Production').
    yaml_files -- List of YAML files to load. This is for testing, leave None in dev/production.
    Returns:
    A class object to be fed into app.config.from_object().
    """
    config_module, config_class = config_class_string.rsplit('.', 1)
    config_obj = getattr(import_module(config_module), config_class)

    # Expand some options.
    db_fmt = 'granad_gatekeeper.models.{}'
    if getattr(config_obj, 'DB_MODELS_IMPORTS', False):
        config_obj.DB_MODELS_IMPORTS = [db_fmt.format(m) for m in config_obj.DB_MODELS_IMPORTS]

    # Load additional configuration settings.
    yaml_files = yaml_files or [f for f in [
        os.path.join('/', 'etc', 'granad-gatekeeper', 'config.yml'),
        os.path.abspath(os.path.join(APP_ROOT_FOLDER, '..', 'config.yml')),
        os.path.join(APP_ROOT_FOLDER, 'config.yml'),
    ] if os.path.exists(f)]
    additional_dict = dict()
    for y in yaml_files:
        with open(y) as f:
            loaded_data = load(f.read())
            if isinstance(loaded_data, dict):
                additional_dict.update(loaded_data)
            else:
                raise Exception('Failed to parse configuration {}'.format(y))

    # Merge the rest into the Flask app config.
    for key, value in additional_dict.items():
        setattr(config_obj, key, value)

    return config_obj


def parse_options():
    """Parses command line options for Flask.

    Returns:
    Config instance to pass into create_app().
    """
    # Figure out which class will be imported.
    if OPTIONS['--config_prod']:
        config_class_string = 'granad_gatekeeper.config.Production'
    else:
        config_class_string = 'granad_gatekeeper.config.Config'
    config_obj = get_config(config_class_string)

    return config_obj


def command(func):
    """Decorator that registers the chosen command/function.

    If a function is decorated with @command but that function name is not a valid "command" according to the docstring,
    a KeyError will be raised, since that's a bug in this script.

    If a user doesn't specify a valid command in their command line arguments, the above docopt(__doc__) line will print
    a short summary and call sys.exit() and stop up there.

    If a user specifies a valid command, but for some reason the developer did not register it, an AttributeError will
    raise, since it is a bug in this script.

    Finally, if a user specifies a valid command and it is registered with @command below, then that command is "chosen"
    by this decorator function, and set as the attribute `chosen`. It is then executed below in
    `if __name__ == '__main__':`.

    Doing this instead of using Flask-Script.

    Positional arguments:
    func -- the function to decorate
    """
    @wraps(func)
    def wrapped():
        return func()

    # Register chosen function.
    if func.__name__ not in OPTIONS:
        raise KeyError('Cannot register {}, not mentioned in docstring/docopt.'.format(func.__name__))
    if OPTIONS[func.__name__]:
        command.chosen = func

    return wrapped


def print_table(table_rows: dict) -> None:
    max_len_key = max([len(i) for i in list(table_rows.keys())])
    max_len_val = max([len(i) for i in list(table_rows.values())])

    row_format = '| {{:{}s}} | {{:{}s}} |'.format(max_len_key, max_len_val)
    row_format_separator = '| {{:{}s}} + {{:{}s}} |'.format(max_len_key, max_len_val)

    print('+{}+'.format('-' * (max_len_key + max_len_val + 5)))
    print(row_format.format('Item', 'Value'))
    print(row_format_separator.format('-' * max_len_key, '-' * max_len_val))
    for key in table_rows:
        print(row_format.format(key, table_rows[key]))

    print('+{}+'.format('-' * (max_len_key + max_len_val + 5)))


def is_connection_error(targets: list, threshold: int) -> bool:
    esponses, no_responses = multi_ping(targets, timeout=2, retry=3)

    error_rate = (len(no_responses) / len(targets)) * 100
    return error_rate > threshold


@command
def run():
    options = parse_options()
    setup_logging('run', logging.DEBUG if options.DEBUG else logging.WARNING)
    log = logging.getLogger(__name__)
    connected_counter = 0
    connecting_counter = 0
    after_reboot = False
    sleep_time = options.CHECK_INTERVAL

    while True:
        if is_connection_error(options.TARGETS, options.TARGETS_FAIL_THRESHOLD):
            log.warning('Connection error rate reached threshold')
            # Connection seems to be in error state, check router connection
            try:
                connection = AuthorizedConnection(options.MODEM_URL)  # Connect to modem
                client = Client(connection)
                monitoring = client.monitoring.status()

                # We was able to connect to modem
                connection_status = int(monitoring['ConnectionStatus'])
                lte_signal = int(monitoring['SignalIcon'])
                if connection_status == ConnectionStatusEnum.CONNECTED:
                    if connected_counter == 0:
                        log.info('Modem thinks its connected, sleeping for 1 minute...')
                        sleep_time = 60
                        connected_counter += 1
                    else:
                        log.info('Modem thinks its connected, and it is not a first time... check signal')
                        if lte_signal < 2:
                            log.warning('BAD signal ({}) detected, restart'.format(lte_signal))
                            connected_counter = 0
                            client.device.reboot()
                            after_reboot = True
                            log.info('Modem rebooted, sleeping for 2 minutes...')
                            sleep_time = 60 * 2
                        else:
                            log.info('Signal is good and modem reports connected, maybe error on target side ?')
                            sleep_time = options.CHECK_INTERVAL
                elif connection_status == ConnectionStatusEnum.CONNECTING:
                    if connecting_counter == 0:
                        log.info('Modem is in connecting state, sleeping for 2 minutes...')
                        sleep_time = 60 * 2
                        connecting_counter += 1
                    else:
                        log.warning('Modem is in connecting state second time, restart')
                        connecting_counter = 0
                        client.device.reboot()
                        after_reboot = True
                        log.info('Modem rebooted, sleeping for 2 minutes...')
                        sleep_time = 60 * 2

                else:
                    log.warning('Modem is in {}, restarting and sleeping 5 minutes...'.format(connection_status))
                    client.device.reboot()
                    after_reboot = True
                    log.info('Modem rebooted, sleeping for 2 minutes...')
                    sleep_time = 60 * 5

            except Exception as e:
                log.warning('Connection to modem failed, sleeping 10 minutes...')
                sleep_time = 60 * 10
        else:
            connected_counter = 0
            connecting_counter = 0
            sleep_time = options.CHECK_INTERVAL
            log.info('All is OK, sleeping for {}s'.format(sleep_time))
            if after_reboot:
                after_reboot = False
                # @TODO RESTART SERVICES
        time.sleep(sleep_time)


@command
def status():
    options = parse_options()

    connection = AuthorizedConnection(options.MODEM_URL)
    client = Client(connection)
    responses, no_responses = multi_ping(options.TARGETS, timeout=2, retry=3)

    table_rows = {}
    for response in responses:
        table_rows[response] = 'ONLINE'

    for no_response in no_responses:
        table_rows[no_response] = '!!!OFF-LINE!!!'

    print('PING INFO')
    print_table(table_rows)

    information = client.device.information()
    monitoring = client.monitoring.status()

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
        'Device name': information['DeviceName'],
        'Device serial number': information['SerialNumber'],
        'Device IMEI': information['Imei'],
        'Device version': information['HardwareVersion'],
        'Device MAC': information['MacAddress1'],
        'Work mode': information['workmode'],
        'Internet connection status': connection_status_to_text.get(int(monitoring['ConnectionStatus']), 'Unknown'),
        'Signal': '{}/{}'.format(monitoring['SignalIcon'], monitoring['maxsignal']),
        'WAN IP': monitoring['WanIPAddress'],
        'Primary DNS': monitoring['PrimaryDns'],
        'Secondary DNS': monitoring['SecondaryDns'],
    }

    print('MODEM INFO')
    print_table(table_rows)


def main():
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))  # Properly handle Control+C
    getattr(command, 'chosen')()  # Execute the function specified by the user.


if __name__ == '__main__':
    main()

