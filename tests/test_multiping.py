import errno
import socket
from unittest.mock import Mock, patch

import pytest

from netkeeper.ext.multiping import MultiPing, MultiPingError, multi_ping


def test_wrong_timeout() -> None:
    with pytest.raises(MultiPingError, match='Timeout'):
        multi_ping(['google.com'], 0)


def test_wrong_retry() -> None:
    with pytest.raises(MultiPingError, match='retries'):
        multi_ping(['google.com'], 0.1, retry=10)


@pytest.mark.parametrize('ipv6', [False, True])
def test_ping_round_trip_ignores_malformed_packets(*, ipv6: bool) -> None:
    sock = Mock(spec=socket.socket)
    address = '::1' if ipv6 else '127.0.0.1'
    family = socket.AF_INET6 if ipv6 else socket.AF_INET
    with (
        patch('netkeeper.ext.multiping.socket.getaddrinfo', return_value=[(family, socket.SOCK_RAW, 0, '', (address, 0))]),
        patch('netkeeper.ext.multiping.socket.socket', return_value=sock),
        patch('netkeeper.ext.multiping.time.time', return_value=100.0) as clock,
    ):
        ping = MultiPing([address])
        ping.send()
        request = bytearray(sock.sendto.call_args.args[0])
        assert request[0] == (128 if ipv6 else 8)
        request[0] = 129 if ipv6 else 0
        response = request if ipv6 else bytearray([69] + [0] * 19) + request
        packets = [b'', bytes(response[:-4]), bytes(response)]
        if ipv6:
            # The IPv4 socket is drained before the IPv6 socket.
            packets.insert(0, b'')
        sock.recv.side_effect = [*packets, BlockingIOError(errno.EWOULDBLOCK, 'empty'), BlockingIOError(errno.EWOULDBLOCK, 'empty')]
        clock.return_value = 100.125
        responses, missing = ping.receive(1.0)
    assert responses == {address: 0.125}
    assert missing == []


def test_retry_aggregates_results() -> None:
    with patch('netkeeper.ext.multiping.MultiPing', autospec=True) as ping:
        ping.return_value.receive.side_effect = [({'a': 0.125}, ['b']), ({'b': 0.25}, [])]
        assert multi_ping(['a', 'b'], 2, retry=3) == ({'a': 0.125, 'b': 0.25}, [])
    assert ping.return_value.send.call_count == 2
    ping.return_value.receive.assert_called_with(0.5)
