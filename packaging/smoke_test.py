"""Smoke test del ejecutable empaquetado (quickstart P1, T083).

Uso: python packaging/smoke_test.py dist/EnvioCorreos[.exe]
Ejecuta `--smoke`, exige exit 0 en menos de SMOKE_TIMEOUT_S y reporta el tiempo de arranque.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SMOKE_TIMEOUT_S = 60  # holgado: la primera ejecución onefile descomprime el bundle
STARTUP_TARGET_S = 10  # SC-006


def main() -> int:
    exe = Path(sys.argv[1])
    env = dict(os.environ, ENVIO_CORREOS_DATA_DIR=tempfile.mkdtemp())
    start = time.perf_counter()
    proc = subprocess.run([str(exe), "--smoke"], env=env, timeout=SMOKE_TIMEOUT_S)
    elapsed = time.perf_counter() - start
    log = Path(env["ENVIO_CORREOS_DATA_DIR"]) / "logs" / "envio-correos.log"
    if log.exists():
        sys.stdout.write(log.read_text(encoding="utf-8"))
    sys.stdout.write(
        f"\nexit={proc.returncode} tiempo={elapsed:.1f}s tamaño={exe.stat().st_size / 1e6:.1f}MB\n"
    )
    if elapsed > STARTUP_TARGET_S:
        sys.stdout.write(f"AVISO: el arranque superó {STARTUP_TARGET_S}s (SC-006)\n")
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
