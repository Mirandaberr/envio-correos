"""Abrir archivos o carpetas con la aplicación predeterminada del sistema."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def open_path(path: Path) -> bool:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]  # solo existe en Windows
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
        return True
    except (OSError, subprocess.CalledProcessError) as exc:
        log.warning("No se pudo abrir el archivo con la app predeterminada: %s", type(exc).__name__)
        return False
