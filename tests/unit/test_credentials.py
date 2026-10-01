import keyring
import pytest
from keyring.backend import KeyringBackend

from envio_correos.core import credentials


class MemoryKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        if (service, username) not in self.store:
            raise keyring.errors.PasswordDeleteError(username)
        del self.store[(service, username)]


@pytest.fixture
def mem():
    previous = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    yield backend
    keyring.set_keyring(previous)


def test_guardar_leer_olvidar(mem):
    credentials.remember("Yo@Empresa.com", "clave")
    assert credentials.recall("yo@empresa.com") == "clave"
    assert credentials.remembered_account() == "yo@empresa.com"
    credentials.forget("yo@empresa.com")
    assert credentials.recall("yo@empresa.com") is None
    assert credentials.remembered_account() is None


def test_olvidar_sin_nada_guardado_no_falla(mem):
    credentials.forget("nadie@empresa.com")


def test_backend_no_disponible_degrada_sin_romper(monkeypatch):
    def boom(*a, **k):
        raise keyring.errors.NoKeyringError("sin backend")

    monkeypatch.setattr(keyring, "get_password", boom)
    monkeypatch.setattr(keyring, "set_password", boom)
    assert credentials.recall("yo@empresa.com") is None
    assert credentials.remember("yo@empresa.com", "x") is False
