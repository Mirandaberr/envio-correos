"""Credenciales en el almacén seguro del sistema (Windows Credential Manager vía keyring).

Solo se guardan si la usuaria elige "Recordar mi cuenta" (FR-013, constitución IV). La cuenta
recordada (sin la clave) se guarda también en keyring bajo una entrada aparte, para no escribir
ni siquiera el correo en archivos de configuración.
"""

from __future__ import annotations

import contextlib
import logging

import keyring
import keyring.errors

from envio_correos import config

log = logging.getLogger(__name__)

_ACCOUNT_ENTRY = "__cuenta_recordada__"


def _norm(email: str) -> str:
    return email.strip().lower()


def remember(email: str, password: str) -> bool:
    try:
        keyring.set_password(config.APP_NAME, _norm(email), password)
        keyring.set_password(config.APP_NAME, _ACCOUNT_ENTRY, _norm(email))
        return True
    except keyring.errors.KeyringError as exc:
        log.warning("No se pudo guardar la cuenta en el almacén seguro: %s", type(exc).__name__)
        return False


def recall(email: str) -> str | None:
    try:
        return keyring.get_password(config.APP_NAME, _norm(email))
    except keyring.errors.KeyringError as exc:
        log.warning("No se pudo leer el almacén seguro: %s", type(exc).__name__)
        return None


def remembered_account() -> str | None:
    try:
        return keyring.get_password(config.APP_NAME, _ACCOUNT_ENTRY)
    except keyring.errors.KeyringError:
        return None


def forget(email: str) -> None:
    for entry in (_norm(email), _ACCOUNT_ENTRY):
        # Si no había nada guardado o el almacén no está disponible, no hay nada que borrar.
        with contextlib.suppress(keyring.errors.KeyringError):
            keyring.delete_password(config.APP_NAME, entry)
