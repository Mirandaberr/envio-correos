import os
import sys

import pytest


def _has_display() -> bool:
    # No se crea un Tk() de prueba: crear y destruir un intérprete Tk antes del de la app
    # provoca un segfault con Tk 9 en macOS (verificado al armar este test).
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def pytest_collection_modifyitems(config, items):
    if _has_display():
        return
    skip = pytest.mark.skip(reason="sin pantalla disponible para Tk")
    for item in items:
        if "tests/gui" in str(item.fspath):
            item.add_marker(skip)


# --- Privacidad y trazabilidad de logs en todos los recorridos de GUI (T088) ---

import re  # noqa: E402

from envio_correos import config  # noqa: E402
from envio_correos.devtools.fake_smtp import DEV_PASSWORD  # noqa: E402
from envio_correos.logging_setup import setup_logging, teardown_logging  # noqa: E402

_EMAIL_LIKE = re.compile(r"[\w.%+*-]+@[\w-]+(?:\.[\w-]+)+")
_TRACK_ID = re.compile(r"^\S+ \S+ \w+ \[(S-[0-9A-F]{4}|C-[0-9A-F]{4}(-R\d+)?)\] ")


@pytest.fixture(autouse=True)
def log_privacy(tmp_path):
    handler = setup_logging(tmp_path / "logs-privacidad")
    yield
    handler.flush()
    text = (tmp_path / "logs-privacidad" / config.LOG_FILENAME).read_text(encoding="utf-8")
    teardown_logging()
    unmasked = [e for e in _EMAIL_LIKE.findall(text) if "***@" not in e]
    assert unmasked == [], f"direcciones sin enmascarar en el log: {unmasked[:5]}"
    assert DEV_PASSWORD not in text, "la contraseña apareció en el log"
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith((" ", "\t", "Traceback"))]
    sin_id = [ln for ln in lines if re.match(r"^\d{4}-\d\d-\d\d", ln) and not _TRACK_ID.match(ln)]
    assert sin_id == [], f"líneas sin track_id: {sin_id[:3]}"
