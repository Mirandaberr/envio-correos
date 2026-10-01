"""Contrato de envío (contracts/send-provider.md, principio VII).

El motor de campañas depende solo de estos tipos; cada proveedor (v1 SMTP con
contraseña, v2 OAuth) los implementa sin que la GUI, el motor o el reporte cambien.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class FailureKind(StrEnum):
    PERMANENT_RECIPIENT = "PERMANENT_RECIPIENT"
    TRANSIENT = "TRANSIENT"
    ACCOUNT = "ACCOUNT"
    SIZE = "SIZE"
    UNKNOWN = "UNKNOWN"


class ReasonCode(StrEnum):
    AUTH_BAD_CREDENTIALS = "AUTH_BAD_CREDENTIALS"
    AUTH_SMTP_DISABLED = "AUTH_SMTP_DISABLED"
    AUTH_SECURITY_DEFAULTS = "AUTH_SECURITY_DEFAULTS"
    AUTH_UNKNOWN = "AUTH_UNKNOWN"
    TLS_UNAVAILABLE = "TLS_UNAVAILABLE"
    NETWORK = "NETWORK"
    SEND_AS_DENIED = "SEND_AS_DENIED"
    RECIPIENT_REJECTED = "RECIPIENT_REJECTED"
    TOO_MANY_RECIPIENTS = "TOO_MANY_RECIPIENTS"
    MESSAGE_TOO_LARGE = "MESSAGE_TOO_LARGE"
    THROTTLED = "THROTTLED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Failure:
    kind: FailureKind
    code: ReasonCode
    smtp_code: str | None = None  # p. ej. "550 5.1.1"; nunca el texto completo del servidor


@dataclass(frozen=True)
class ConnectionResult:
    ok: bool
    failure: Failure | None = None

    @classmethod
    def success(cls) -> ConnectionResult:
        return cls(True, None)


class ProviderError(Exception):
    """Fallo que afecta a la sesión completa (no a un destinatario)."""

    def __init__(self, failure: Failure):
        super().__init__(f"{failure.kind}:{failure.code} {failure.smtp_code or ''}".strip())
        self.failure = failure


@dataclass(frozen=True)
class ProviderLimits:
    min_interval_s: float
    recipients_per_24h: int
    max_recipients_per_message: int
    max_message_bytes: int
    max_attachments_raw_bytes: int


@dataclass(frozen=True)
class Attachment:
    filename: str
    data: bytes = field(repr=False)
    maintype: str = "application"
    subtype: str = "octet-stream"


@dataclass(frozen=True)
class OutgoingMessage:
    to: tuple[str, ...]
    subject: str
    body: str
    bcc: tuple[str, ...] = ()
    attachments: tuple[Attachment, ...] = ()
    display_name: str = ""

    @property
    def all_recipients(self) -> tuple[str, ...]:
        return self.to + self.bcc


@dataclass(frozen=True)
class SendOutcome:
    accepted: tuple[str, ...]
    rejected: Mapping[str, Failure]


@runtime_checkable
class SendProvider(Protocol):
    provider_id: str
    sender_email: str

    @property
    def limits(self) -> ProviderLimits: ...

    def test_connection(self) -> ConnectionResult: ...

    def open(self) -> None: ...

    def close(self) -> None: ...

    def send(self, message: OutgoingMessage) -> SendOutcome: ...
