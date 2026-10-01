"""Logging con trazabilidad (principio VI) y sin datos sensibles (principio IV).

- Toda línea lleva un `track_id`: el de sesión (`S-xxxx`, desde que abre la app) o, dentro de
  `campaign_context`, el del intento de campaña (`C-xxxx-Rn`).
- Las direcciones de correo se enmascaran (`ju***@empresa.com`) en mensaje y argumentos.
- Archivo rotativo acotado (LOG_MAX_BYTES × (LOG_BACKUP_COUNT + 1)).
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import logging.handlers
import re
import secrets
from collections.abc import Iterator
from pathlib import Path

from envio_correos import config

_EMAIL_RE = re.compile(r"([A-Za-z0-9._%+\-]+)@([A-Za-z0-9.\-]+\.[A-Za-z]{2,})")
_FORMAT = "%(asctime)s %(levelname)s [%(track_id)s] %(name)s: %(message)s"

_campaign_track_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "campaign_track_id", default=None
)
_session_track_id = f"S-{secrets.token_hex(2).upper()}"
_handler: logging.Handler | None = None
_EXC_FORMATTER = logging.Formatter()


def session_track_id() -> str:
    return _session_track_id


def current_track_id() -> str:
    return _campaign_track_id.get() or _session_track_id


def mask_email(address: str) -> str:
    return _EMAIL_RE.sub(lambda m: f"{m.group(1)[:2]}***@{m.group(2)}", address)


class TrackIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.track_id = current_track_id()
        return True


class EmailMaskFilter(logging.Filter):
    """Formatea el mensaje una vez y lo enmascara; así ningún argumento con PII llega al
    archivo. Se reemplazan `msg`/`args` del registro (el formateo ya no se repite)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_email(record.getMessage())
        record.args = None
        # El traceback también puede traer direcciones (p. ej. en el texto de una excepción
        # de smtplib): se formatea acá y se enmascara antes de que lo escriba el Formatter.
        if record.exc_info:
            record.exc_text = mask_email(_EXC_FORMATTER.formatException(record.exc_info))
            record.exc_info = None
        if record.stack_info:
            record.stack_info = mask_email(record.stack_info)
        return True


@contextlib.contextmanager
def campaign_context(track_id: str) -> Iterator[None]:
    token = _campaign_track_id.set(track_id)
    try:
        yield
    finally:
        _campaign_track_id.reset(token)


def setup_logging(directory: Path | None = None, level: int = logging.INFO) -> logging.Handler:
    """Configura el logger raíz. Idempotente: reconfigurar reemplaza el handler anterior."""
    global _handler
    teardown_logging()
    directory = directory or config.log_dir()
    directory.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        directory / config.LOG_FILENAME,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.addFilter(TrackIdFilter())
    handler.addFilter(EmailMaskFilter())
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)
    _handler = handler
    return handler


def teardown_logging() -> None:
    global _handler
    if _handler is not None:
        logging.getLogger().removeHandler(_handler)
        _handler.close()
        _handler = None
