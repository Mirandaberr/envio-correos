"""Respuestas SMTP → ReasonCode (contracts/send-provider.md, research R3).

Las variantes de 535 5.7.139 se distinguen por subcadenas observadas en hilos de Microsoft Q&A
(marcadas [NO VERIFICADO] en research R3). Viven en tablas de datos para ajustarlas tras las
pruebas con una cuenta real (quickstart Q1–Q2) sin tocar la lógica.
"""

from __future__ import annotations

import re
from enum import StrEnum

from envio_correos.core.providers.base import Failure
from envio_correos.core.providers.base import FailureKind as K
from envio_correos.core.providers.base import ReasonCode as R


class Phase(StrEnum):
    CONNECT = "connect"
    AUTH = "auth"
    MAIL = "mail"
    RCPT = "rcpt"
    DATA = "data"


# (subcadena en minúsculas, ReasonCode) — se evalúan en orden.
AUTH_535_PATTERNS: tuple[tuple[str, R], ...] = (
    ("smtpclientauthentication is disabled", R.AUTH_SMTP_DISABLED),
    ("security defaults", R.AUTH_SECURITY_DEFAULTS),
    ("credentials were incorrect", R.AUTH_BAD_CREDENTIALS),
)
# 535 con estos códigos extendidos es "credenciales inválidas" genérico.
AUTH_GENERIC_BAD_CREDENTIALS = frozenset({"5.7.8", "5.7.3"})

SEND_AS_DENIED_ENHANCED = "5.7.60"
TOO_MANY_RECIPIENTS_ENHANCED = frozenset({"4.5.3", "5.5.3"})
MESSAGE_TOO_LARGE_ENHANCED = frozenset({"5.3.4"})
MESSAGE_TOO_LARGE_CODES = frozenset({552})
QUOTA_PATTERNS: tuple[str, ...] = ("quotaexceeded", "thread limit exceeded")

_ENHANCED_RE = re.compile(r"\b([245]\.\d{1,3}\.\d{1,3})\b")


def _enhanced(text: str) -> str | None:
    m = _ENHANCED_RE.search(text)
    return m.group(1) if m else None


def _smtp_code(code: int | None, enhanced: str | None) -> str | None:
    if code is None:
        return None
    return f"{code} {enhanced}" if enhanced else str(code)


def classify(phase: Phase, code: int | None, text: str | bytes) -> Failure:
    """Clasifica una respuesta del servidor. Solo conserva código y código extendido:
    el texto completo puede contener direcciones u otros datos y nunca se guarda."""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    enhanced = _enhanced(text)
    sc = _smtp_code(code, enhanced)
    if phase is Phase.CONNECT:
        return Failure(K.TRANSIENT, R.NETWORK, sc)
    if code is None:
        return Failure(K.UNKNOWN, R.UNKNOWN, None)
    low = text.lower()
    reason, kind = _classify_code(phase, code, enhanced, low)
    return Failure(kind, reason, sc)


def _classify_code(phase: Phase, code: int, enhanced: str | None, low: str) -> tuple[R, K]:
    if enhanced == SEND_AS_DENIED_ENHANCED:
        return R.SEND_AS_DENIED, K.ACCOUNT
    if enhanced in TOO_MANY_RECIPIENTS_ENHANCED or (phase is Phase.RCPT and code == 452):
        return R.TOO_MANY_RECIPIENTS, K.TRANSIENT
    if code in MESSAGE_TOO_LARGE_CODES or enhanced in MESSAGE_TOO_LARGE_ENHANCED:
        return R.MESSAGE_TOO_LARGE, K.SIZE
    if any(p in low for p in QUOTA_PATTERNS) or 400 <= code < 500:
        return R.THROTTLED, K.TRANSIENT
    if phase is Phase.AUTH:
        return _classify_auth(code, enhanced, low), K.ACCOUNT
    if phase is Phase.RCPT and 500 <= code < 600:
        return R.RECIPIENT_REJECTED, K.PERMANENT_RECIPIENT
    return R.UNKNOWN, K.UNKNOWN


def _classify_auth(code: int, enhanced: str | None, low: str) -> R:
    if code != 535:
        return R.AUTH_UNKNOWN
    for needle, reason in AUTH_535_PATTERNS:
        if needle in low:
            return reason
    if enhanced in AUTH_GENERIC_BAD_CREDENTIALS:
        return R.AUTH_BAD_CREDENTIALS
    return R.AUTH_UNKNOWN
