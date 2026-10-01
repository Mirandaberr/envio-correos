"""Proveedor v1: SMTP AUTH con contraseña contra Microsoft 365 (research R1).

Garantías del contrato (contracts/send-provider.md): TLS obligatorio con verificación de
certificado (≥ 1.2), `From` siempre la cuenta autenticada, la contraseña nunca sale de esta
clase y el mensaje armado no se retiene después de enviarlo.
"""

from __future__ import annotations

import contextlib
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from envio_correos import config
from envio_correos.config import SmtpEndpoint
from envio_correos.core.providers.base import (
    ConnectionResult,
    Failure,
    FailureKind,
    OutgoingMessage,
    ProviderError,
    ProviderLimits,
    ReasonCode,
    SendOutcome,
)
from envio_correos.core.providers.smtp_errors import Phase, classify

log = logging.getLogger(__name__)

PROVIDER_ID = "m365-smtp-password"
_TLS_FAILURE = Failure(FailureKind.ACCOUNT, ReasonCode.TLS_UNAVAILABLE)


class M365SmtpPasswordProvider:
    provider_id = PROVIDER_ID

    def __init__(
        self,
        sender_email: str,
        password: str,
        *,
        endpoint: SmtpEndpoint | None = None,
        display_name: str = "",
        timeout: float = config.SMTP_TIMEOUT_S,
    ):
        self.sender_email = sender_email
        self.display_name = display_name
        self.__password = password
        self._endpoint = endpoint or config.smtp_endpoint()
        self._timeout = timeout
        self._smtp: smtplib.SMTP | None = None

    def __repr__(self) -> str:
        return (
            f"M365SmtpPasswordProvider(sender={self.sender_email!r}, host={self._endpoint.host!r})"
        )

    @property
    def limits(self) -> ProviderLimits:
        return ProviderLimits(
            min_interval_s=config.min_interval_s(),
            recipients_per_24h=config.RECIPIENTS_PER_24H,
            max_recipients_per_message=config.MAX_RECIPIENTS_PER_MESSAGE,
            max_message_bytes=config.MAX_MESSAGE_BYTES,
            max_attachments_raw_bytes=config.MAX_ATTACHMENTS_RAW_BYTES,
        )

    # --- Sesión ---

    def _ssl_context(self) -> ssl.SSLContext:
        ca = self._endpoint.dev_ca_file
        ctx = ssl.create_default_context(cafile=str(ca) if ca else None)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        return ctx

    def _connect(self) -> smtplib.SMTP:
        ep = self._endpoint
        try:
            smtp = smtplib.SMTP(ep.host, ep.port, timeout=self._timeout)
            smtp.ehlo()
        except (OSError, smtplib.SMTPException) as exc:
            log.warning("No se pudo conectar al servidor de correo: %s", type(exc).__name__)
            raise ProviderError(classify(Phase.CONNECT, None, "")) from None
        try:
            self._secure_and_login(smtp)
        except BaseException:
            _quietly_close(smtp)
            raise
        return smtp

    def _secure_and_login(self, smtp: smtplib.SMTP) -> None:
        if not smtp.has_extn("starttls"):
            log.error("El servidor no ofrece STARTTLS; no se envían credenciales")
            raise ProviderError(_TLS_FAILURE)
        try:
            smtp.starttls(context=self._ssl_context())
            smtp.ehlo()
        except (ssl.SSLError, ssl.CertificateError, smtplib.SMTPException, OSError) as exc:
            log.error("Falló la negociación TLS: %s", type(exc).__name__)
            raise ProviderError(_TLS_FAILURE) from None
        try:
            smtp.login(self.sender_email, self.__password)
        except smtplib.SMTPAuthenticationError as exc:
            failure = classify(Phase.AUTH, exc.smtp_code, exc.smtp_error)
            log.warning("Autenticación rechazada: %s %s", failure.code, failure.smtp_code)
            raise ProviderError(failure) from None
        except smtplib.SMTPException:
            raise ProviderError(Failure(FailureKind.ACCOUNT, ReasonCode.AUTH_UNKNOWN)) from None

    def test_connection(self) -> ConnectionResult:
        try:
            smtp = self._connect()
        except ProviderError as exc:
            return ConnectionResult(False, exc.failure)
        _quietly_close(smtp)
        log.info("Conexión de prueba exitosa")
        return ConnectionResult.success()

    def open(self) -> None:
        if self._smtp is None:
            self._smtp = self._connect()

    def close(self) -> None:
        if self._smtp is not None:
            _quietly_close(self._smtp)
            self._smtp = None

    # --- Envío ---

    def _build(self, message: OutgoingMessage) -> EmailMessage:
        em = EmailMessage()
        em["From"] = formataddr((message.display_name or self.display_name, self.sender_email))
        em["To"] = ", ".join(message.to)
        em["Subject"] = message.subject
        em["Date"] = formatdate(localtime=True)
        em["Message-ID"] = make_msgid(domain=self.sender_email.rpartition("@")[2] or None)
        em.set_content(message.body)
        for att in message.attachments:
            em.add_attachment(
                att.data, maintype=att.maintype, subtype=att.subtype, filename=att.filename
            )
        return em

    def send(self, message: OutgoingMessage) -> SendOutcome:
        self.open()
        assert self._smtp is not None
        recipients = list(message.all_recipients)
        em = self._build(message)  # se descarta al salir de este método (research R7.4)
        try:
            refused = self._smtp.send_message(em, from_addr=self.sender_email, to_addrs=recipients)
        except smtplib.SMTPRecipientsRefused as exc:
            return SendOutcome((), _classify_refused(exc.recipients))
        except smtplib.SMTPSenderRefused as exc:
            raise ProviderError(classify(Phase.MAIL, exc.smtp_code, exc.smtp_error)) from None
        except smtplib.SMTPDataError as exc:
            failure = classify(Phase.DATA, exc.smtp_code, exc.smtp_error)
            return SendOutcome((), dict.fromkeys(recipients, failure))
        except (smtplib.SMTPServerDisconnected, OSError) as exc:
            log.warning("Se perdió la conexión durante el envío: %s", type(exc).__name__)
            self.close()
            raise ProviderError(classify(Phase.CONNECT, None, "")) from None
        rejected = _classify_refused(refused)
        accepted = tuple(r for r in recipients if r not in rejected)
        return SendOutcome(accepted, rejected)


def _classify_refused(refused: dict[str, tuple[int, bytes]]) -> dict[str, Failure]:
    return {addr: classify(Phase.RCPT, code, text) for addr, (code, text) in refused.items()}


def _quietly_close(smtp: smtplib.SMTP) -> None:
    try:
        smtp.quit()
    except (smtplib.SMTPException, OSError):
        with contextlib.suppress(OSError):
            smtp.close()
