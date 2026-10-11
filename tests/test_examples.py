import socket

from examples.offline_walkthrough import run_demo


def test_walkthrough_works_without_network_or_persistent_wallets(monkeypatch, tmp_path):
    def unexpected_network(*args, **kwargs):
        raise AssertionError('Offline example attempted network access')

    monkeypatch.setattr(socket, 'socket', unexpected_network)
    monkeypatch.setattr(socket, 'getaddrinfo', unexpected_network)
    monkeypatch.chdir(tmp_path)
    assert run_demo() == {
        'signature_verified': True,
        'changed_message_rejected': True,
        'wallet_reload_verified': True,
        'block_template_height': 1,
        'block_header_bytes': 80,
        'template_mined_or_broadcast': False,
    }
    assert list(tmp_path.iterdir()) == []
