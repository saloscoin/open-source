import base64
import json
import os
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

import pytest

from core.wallet import Wallet
from rpc.server import RPCHandler, RPCServer


@pytest.mark.parametrize('host,user,password', [
    ('0.0.0.0', None, None), ('127.0.0.1', 'u', None),
    ('127.0.0.1', None, 'p'), ('127.0.0.1', '', 'p'),
    ('127.0.0.1', 'u', ''),
])
def test_rpc_rejects_unsafe_credentials(host, user, password):
    with pytest.raises(ValueError):
        RPCServer(host=host, username=user, password=password)


def test_rpc_authentication_precedes_dispatch():
    rpc = RPCServer(username='üser', password='secret:with:colons')
    calls = []
    rpc.register_method('probe', lambda: calls.append(True) or 'ok')
    server = HTTPServer(('127.0.0.1', 0), RPCHandler)
    server.rpc_server = rpc
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for header in [None, 'Basic !!!', 'Basic ' + base64.b64encode(b'u:wrong').decode()]:
            headers = {} if header is None else {'Authorization': header}
            request = urllib.request.Request(
                f'http://127.0.0.1:{server.server_port}/',
                data=b'{"method":"probe","id":1}', headers=headers)
            with pytest.raises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(request)
            assert error.value.code == 401
            assert calls == []
        token = base64.b64encode('üser:secret:with:colons'.encode()).decode()
        request.add_header('Authorization', 'Basic ' + token)
        with urllib.request.urlopen(request) as response:
            assert json.load(response)['result'] == 'ok'
        assert calls == [True]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(2)


def test_rpc_stops_without_hanging():
    rpc = RPCServer(port=0)
    rpc.start()
    rpc.stop()
    assert not rpc._thread.is_alive()


def test_wallet_encryption_fails_without_mutating_file(tmp_path):
    path = tmp_path / 'wallet.json'
    wallet = Wallet(filepath=str(path))
    wallet.create_address()
    original = path.read_bytes()
    with pytest.raises(NotImplementedError):
        wallet.encrypt('password')
    assert path.read_bytes() == original
    assert not wallet.encrypted


def test_legacy_flag_does_not_accept_password_or_overwrite(tmp_path):
    path = tmp_path / 'legacy.json'
    wallet = Wallet(filepath=str(path))
    wallet.create_address()
    data = json.loads(path.read_text())
    data['encrypted'] = True
    path.write_text(json.dumps(data))
    original = path.read_bytes()
    loaded = Wallet(filepath=str(path))
    with pytest.raises(NotImplementedError):
        loaded.unlock('anything')
    assert loaded.locked
    with pytest.raises(ValueError):
        loaded.save()
    assert path.read_bytes() == original


def test_private_keys_survive_atomic_save_and_restart(tmp_path):
    path = tmp_path / 'wallet.json'
    wallet = Wallet(filepath=str(path))
    address = wallet.create_address()
    loaded = Wallet(filepath=str(path))
    assert loaded.addresses[0].private_key == address.private_key
    if os.name == 'posix':
        assert path.stat().st_mode & 0o777 == 0o600
    assert not list(tmp_path.glob('.wallet-*'))


def test_hd_passphrase_rejected_before_state_changes():
    wallet = Wallet()
    with pytest.raises(NotImplementedError):
        wallet.create_hd_wallet(passphrase='secret')
    assert wallet.mnemonic == ''
    assert wallet.addresses == []


def test_exchange_requires_credentials_before_initialization(monkeypatch):
    from exchange_node import ExchangeNode
    with pytest.raises(ValueError):
        ExchangeNode()
    captured = {}
    monkeypatch.setattr(ExchangeNode, '_init_blockchain', lambda self: None)
    monkeypatch.setattr(ExchangeNode, '_init_p2p', lambda self: None)
    monkeypatch.setattr(ExchangeNode, '_init_rpc', lambda self: captured.update(user=self.rpc_user))
    ExchangeNode(rpc_user='custom', rpc_password='secret')
    assert captured['user'] == 'custom'
