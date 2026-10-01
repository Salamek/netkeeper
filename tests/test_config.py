from pathlib import Path

import pytest

from netkeeper.bin.netkeeper import get_config
from netkeeper.config import Config


def test_yaml_overrides_are_ordered_and_isolated(tmp_path: Path) -> None:
    first = tmp_path / 'first.yml'
    second = tmp_path / 'second.yml'
    first.write_text('TARGETS: [example.com]\nCHECK_INTERVAL: 10\n', encoding='utf-8')
    second.write_text('CHECK_INTERVAL: 20\n', encoding='utf-8')
    config = get_config('netkeeper.config.Config', [str(first), str(second)])
    assert config.TARGETS == ['example.com']
    assert config.CHECK_INTERVAL == 20
    defaults = get_config('netkeeper.config.Config', [])
    assert defaults.CHECK_INTERVAL == 60
    assert defaults.TARGETS == Config().TARGETS
    config.RESTART_SERVICES.append('example.service')
    assert 'example.service' not in defaults.RESTART_SERVICES


@pytest.mark.parametrize(
    'content',
    [
        '[]',
        'null',
        '1: value',
        'UNKNOWN: value',
        'TARGETS: []',
        'TARGETS: example.com',
        'TARGETS: [123]',
        'MODEM_URL: null',
        'CHECK_INTERVAL: 0',
        'CHECK_INTERVAL: true',
        'TARGETS_FAIL_THRESHOLD: 101',
    ],
)
def test_invalid_configuration(tmp_path: Path, content: str) -> None:
    filename = tmp_path / 'config.yml'
    filename.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError, match=r'configuration|setting|TARGETS|MODEM_URL|CHECK_INTERVAL'):
        get_config('netkeeper.config.Config', [str(filename)])


def test_production_requires_configuration() -> None:
    with pytest.raises(ValueError, match='TARGETS'):
        get_config('netkeeper.config.Production', [])


def test_production_configuration(tmp_path: Path) -> None:
    filename = tmp_path / 'config.yml'
    filename.write_text('TARGETS: [example.com]\nMODEM_URL: http://192.168.8.1/\n', encoding='utf-8')
    config = get_config('netkeeper.config.Production', [str(filename)])
    assert config.DEBUG is False
    assert config.TARGETS == ['example.com']
    assert config.MODEM_URL == 'http://192.168.8.1/'
