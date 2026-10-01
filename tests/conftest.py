from __future__ import annotations

from pathlib import Path

import pytest

from tests.fixtures.make_fixtures import make_all


@pytest.fixture(scope="session")
def fixtures_dir(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    return make_all(tmp_path_factory.mktemp("fixtures"))


@pytest.fixture(autouse=True)
def isolated_app_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Ningún test escribe en el perfil real del usuario."""
    data = tmp_path / "appdata"
    monkeypatch.setenv("ENVIO_CORREOS_DATA_DIR", str(data))
    # Cualquier ruta relativa que use un test termina en un temporal, nunca en el repo.
    monkeypatch.chdir(tmp_path)
    return data


@pytest.fixture(autouse=True)
def no_reverse_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """socket.getfqdn() hace DNS inverso, que en algunas redes se cuelga (pasó en el runner de
    macOS de GitHub). Ni la app ni el servidor de prueba deben depender de él."""
    import socket

    def forbidden(*_a, **_k):
        raise AssertionError("se llamó a socket.getfqdn() (DNS inverso)")

    monkeypatch.setattr(socket, "getfqdn", forbidden)
