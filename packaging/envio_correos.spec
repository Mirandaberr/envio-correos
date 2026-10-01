# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller: un único ejecutable, sin consola (research R8, FR-080).

Construir (desde la raíz del repo):
    uv run pyinstaller packaging/envio_correos.spec --noconfirm --clean
"""

from PyInstaller.utils.hooks import collect_entry_point, collect_submodules

APP_NAME = "EnvioCorreos"

# keyring descubre sus backends por entry points (research R8); dnspython importa los tipos de
# registro (MX, A, AAAA…) dinámicamente: se incluyen explícitamente para no depender de que un
# hook los detecte.
kr_datas, kr_hidden = collect_entry_point("keyring.backends")
# openpyxl importa defusedxml de forma condicional (protección contra XML malicioso): se fuerza.
hidden = (
    kr_hidden
    + collect_submodules("dns.rdtypes")
    + collect_submodules("defusedxml")
    + ["keyring.backends.Windows"]
)

a = Analysis(
    ["../src/envio_correos/__main__.py"],
    pathex=["../src"],
    datas=kr_datas,
    hiddenimports=hidden,
    excludes=["envio_correos.devtools", "aiosmtpd", "trustme", "pytest", "psutil"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    console=False,
    upx=False,
    icon=None,  # TODO(T082): ícono de la app cuando exista el diseño
)
