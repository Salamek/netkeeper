import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from huawei_lte_api.Connection import Connection
from huawei_lte_api.enums.cradle import ConnectionStatusEnum
from huawei_lte_api.enums.device import ControlModeEnum
from typer.testing import CliRunner

from netkeeper.bin import netkeeper as cli
from netkeeper.config import Config
from netkeeper.ext.multiping import MultiPingSocketError


@pytest.mark.parametrize('args', [['--help'], ['-h'], ['run', '--help'], ['status', '--help'], []])
def test_help_does_not_load_configuration(args: list[str]) -> None:
    with patch.object(cli, 'get_config') as get_config:
        result = CliRunner().invoke(cli.cli, args)
    assert result.exit_code == (2 if not args else 0)
    get_config.assert_not_called()
    assert 'Usage:' in result.output


@pytest.mark.parametrize(('config_flag', 'log_flag'), [
    ('--config-prod', '--log-dir'),
    ('--config_prod', '--log_dir'),
    ('--config_prod', '-l'),
])
def test_run_command(config_flag: str, log_flag: str, tmp_path: Path) -> None:
    config = Config()
    with patch.object(cli, 'get_config', return_value=config) as get_config, patch.object(cli, 'run') as run:
        result = CliRunner().invoke(cli.cli, ['run', config_flag, log_flag, str(tmp_path)])
    assert result.exit_code == 0, result.output
    get_config.assert_called_once_with('netkeeper.config.Production')
    run.assert_called_once_with(config, str(tmp_path))


def test_run_defaults() -> None:
    config = Config()
    with patch.object(cli, 'get_config', return_value=config) as get_config, patch.object(cli, 'run') as run:
        result = CliRunner().invoke(cli.cli, ['run'])
    assert result.exit_code == 0, result.output
    get_config.assert_called_once_with('netkeeper.config.Config')
    run.assert_called_once_with(config, None)


def test_status_command() -> None:
    config = Config()
    with patch.object(cli, 'get_config', return_value=config) as get_config, patch.object(cli, 'status') as status:
        result = CliRunner().invoke(cli.cli, ['status'])
    assert result.exit_code == 0, result.output
    get_config.assert_called_once_with('netkeeper.config.Config')
    status.assert_called_once_with(config)


@pytest.mark.parametrize('args', [['unknown'], ['run', '--unknown'], ['status', '--config-prod']])
def test_invalid_arguments(args: list[str]) -> None:
    with patch.object(cli, 'get_config') as get_config:
        result = CliRunner().invoke(cli.cli, args)
    assert result.exit_code == 2
    get_config.assert_not_called()


def test_invalid_log_directory(tmp_path: Path) -> None:
    with patch.object(cli, 'get_config') as get_config:
        result = CliRunner().invoke(cli.cli, ['run', '--log-dir', str(tmp_path / 'missing')])
    assert result.exit_code == 2
    get_config.assert_not_called()


def test_empty_table(capsys: pytest.CaptureFixture[str]) -> None:
    cli.print_table({}, 'Ping Info')
    assert 'Ping Info' in capsys.readouterr().out


@pytest.mark.parametrize(('missing', 'expected'), [(['a'], False), (['a', 'b'], True)])
def test_failure_threshold(missing: list[str], *, expected: bool) -> None:
    with patch.object(cli, 'multi_ping', return_value=({}, missing)):
        assert cli.is_connection_error(['a', 'b'], 50) is expected


def test_dns_failure_is_connection_error() -> None:
    with patch.object(cli, 'multi_ping', side_effect=MultiPingSocketError):
        assert cli.is_connection_error(['example.com'], 50)


def test_systemd_commands() -> None:
    with patch.object(cli, 'call_systemd', return_value=True) as call:
        assert cli.is_service_active('example.service')
        call.assert_called_with('example.service', 'is-active')
        assert cli.is_service_enabled('example.service')
        call.assert_called_with('example.service', 'is-enabled')
        assert cli.restart_service('example.service')
        call.assert_called_with('example.service', 'restart')


def test_reboot_uses_device_control() -> None:
    connection = Mock(spec=Connection)
    with patch.object(cli, 'Client') as client, patch('netkeeper.bin.netkeeper.time.sleep'):
        cli.restart_modem_and_wait_for_alive(connection, logging.getLogger(__name__))
    client.return_value.device.set_control.assert_called_once_with(ControlModeEnum.REBOOT)
    connection.reload.assert_called_once()


@pytest.mark.parametrize(
    ('connection_status', 'first_delay'),
    [
        (ConnectionStatusEnum.CONNECTED, 60),
        (ConnectionStatusEnum.CONNECTING, 120),
    ],
)
def test_modem_waits_before_reboot(connection_status: ConnectionStatusEnum, first_delay: int) -> None:
    state = cli.MonitorState()
    log = logging.getLogger(__name__)
    with patch.object(cli, 'Connection'), patch.object(cli, 'Client') as client, patch.object(cli, 'restart_modem_and_wait_for_alive') as restart:
        client.return_value.device.information.return_value = {'workmode': 'LTE'}
        client.return_value.monitoring.status.return_value = {'ConnectionStatus': connection_status, 'SignalIcon': '1'}
        assert state.check_modem(Config(), log) == first_delay
        restart.assert_not_called()
        assert state.check_modem(Config(), log) == 1
        restart.assert_called_once()
        assert state.after_reboot


def test_restart_limit_and_recovery() -> None:
    state = cli.MonitorState(restart_counter=5, after_reboot=True)
    config = Config(RESTART_SERVICES=['active.service', 'disabled.service'])
    log = logging.getLogger(__name__)
    with patch.object(cli, 'restart_modem_and_wait_for_alive') as reboot:
        assert state.restart(Mock(spec=Connection), log) == 3600
        reboot.assert_not_called()
    assert state.restart_counter == 0
    with (
        patch.object(cli, 'is_service_active', side_effect=[True, False]),
        patch.object(cli, 'is_service_enabled', return_value=False),
        patch.object(cli, 'restart_service') as restart,
    ):
        state.recover(config, log)
        state.recover(config, log)
    restart.assert_called_once_with('active.service')
    assert not state.after_reboot
