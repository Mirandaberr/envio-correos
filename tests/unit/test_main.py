import os
import sys
import tempfile
import time
from pathlib import Path

from envio_correos import __main__ as entry
from envio_correos import config


def test_no_limpia_si_no_esta_empaquetada(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert entry.cleanup_orphan_mei_dirs() == 0


def test_limpia_solo_mei_viejas_y_no_la_actual(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
    vieja, reciente, actual = (tmp_path / n for n in ("_MEI111", "_MEI222", "_MEI333"))
    for d in (vieja, reciente, actual):
        d.mkdir()
    old = time.time() - config.MEI_ORPHAN_MAX_AGE_S - 60
    os.utime(vieja, (old, old))
    os.utime(actual, (old, old))
    monkeypatch.setattr(sys, "_MEIPASS", str(actual), raising=False)
    assert entry.cleanup_orphan_mei_dirs() == 1
    assert not vieja.exists() and reciente.exists() and actual.exists()
    assert Path(tmp_path / "_MEI333").exists()


def test_smoke_check_en_desarrollo(isolated_app_dirs, monkeypatch):
    import customtkinter

    class FakeCTk:
        def after(self, ms, fn):
            pass

        def mainloop(self):
            pass

        def destroy(self):
            pass

    monkeypatch.setattr(customtkinter, "CTk", FakeCTk)
    assert entry.smoke_check() == 0
