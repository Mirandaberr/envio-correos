"""Servidor SMTP de pruebas (no se empaqueta en el .exe).

Ofrece STARTTLS con un certificado de una CA de prueba propia y AUTH LOGIN, igual que el
servidor real, para que el cliente nunca necesite relajar TLS (constitución, principio IV).
Su comportamiento es programable para cubrir cada fila de contracts/send-provider.md.

Uso manual (quickstart B):
    ENVIO_CORREOS_DEV_SMTP=127.0.0.1:8025 en la app, y en otra terminal:
    uv run python -m envio_correos.devtools.fake_smtp --port 8025
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import socket
import ssl
import threading
from dataclasses import dataclass, field
from pathlib import Path

import trustme
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword

from envio_correos import config

log = logging.getLogger(__name__)

DEV_USER = "yo@empresa.com"
DEV_PASSWORD = "clave-de-prueba"
# aiosmtpd espera 5 s por defecto a que el servidor responda; en runners de CI lentos (macOS)
# no alcanza. Solo afecta al arranque del servidor de pruebas.
READY_TIMEOUT_S = 30.0

_CA_LOCK = threading.Lock()
_CA: tuple[trustme.CA, trustme.LeafCert] | None = None


def _shared_ca(host: str) -> tuple[trustme.CA, trustme.LeafCert]:
    """Una CA y un certificado de servidor por proceso: generar claves RSA por cada test es
    costoso en CPU y hacía que el arranque superara el timeout en CI."""
    global _CA
    with _CA_LOCK:
        if _CA is None:
            ca = trustme.CA()
            _CA = (ca, ca.issue_cert(host, "localhost"))
        return _CA


@dataclass
class Behavior:
    """Respuestas programables. Las claves de dirección van en minúsculas."""

    rcpt_responses: dict[str, str] = field(default_factory=dict)  # "550 5.1.1 ..." / "451 ..."
    auth_response: str | None = None  # si se define, AUTH falla con este texto
    data_response: str | None = None  # p. ej. "552 5.3.4 Message size exceeds fixed limit"
    max_rcpts_per_message: int | None = None  # excedido → 452 4.5.3
    drop_connection_after_messages: int | None = None  # corta la conexión una vez


@dataclass
class ReceivedMessage:
    mail_from: str
    rcpt_tos: list[str]
    data: bytes


class _Handler:
    def __init__(self, server: FakeSmtpServer):
        self._srv = server

    async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
        b = self._srv.behavior
        if b.max_rcpts_per_message and len(envelope.rcpt_tos) >= b.max_rcpts_per_message:
            return "452 4.5.3 Too many recipients"
        response = b.rcpt_responses.get(address.lower())
        if response:
            return response
        envelope.rcpt_tos.append(address)
        return "250 OK"

    async def handle_DATA(self, server, session, envelope):
        b = self._srv.behavior
        if b.data_response:
            return b.data_response
        with self._srv.lock:
            self._srv.messages.append(
                ReceivedMessage(envelope.mail_from, list(envelope.rcpt_tos), envelope.content)
            )
            count = len(self._srv.messages)
        drop = b.drop_connection_after_messages
        if drop is not None and count == drop:
            b.drop_connection_after_messages = None  # solo una vez
            # Se confirma el mensaje N y recién después se corta: close() de asyncio vacía el
            # buffer de escritura antes de cerrar, así que el cliente recibe el 250.
            asyncio.get_running_loop().call_soon(server.transport.close)
        return "250 OK"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeSmtpServer:
    def __init__(
        self,
        cert_dir: Path,
        *,
        port: int | None = None,
        username: str = DEV_USER,
        password: str = DEV_PASSWORD,
        offer_starttls: bool = True,
        behavior: Behavior | None = None,
    ):
        self.host = "127.0.0.1"
        self.port = port or _free_port()
        self.username = username
        self.password = password
        self.behavior = behavior or Behavior()
        self.messages: list[ReceivedMessage] = []
        self.lock = threading.Lock()
        self.auth_attempts = 0
        cert_dir.mkdir(parents=True, exist_ok=True)
        self.ca_file = cert_dir / "ca.pem"
        tls_context = self._make_tls_context() if offer_starttls else None
        self._controller = Controller(
            _Handler(self),
            hostname=self.host,
            port=self.port,
            tls_context=tls_context,
            require_starttls=offer_starttls,
            authenticator=self._authenticate,
            auth_require_tls=offer_starttls,
            data_size_limit=config.MAX_MESSAGE_BYTES * 2,
            ready_timeout=READY_TIMEOUT_S,
        )

    def _make_tls_context(self) -> ssl.SSLContext:
        ca, server_cert = _shared_ca(self.host)
        ca.cert_pem.write_to_path(str(self.ca_file))
        ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        server_cert.configure_cert(ctx)
        return ctx

    def _authenticate(self, server, session, envelope, mechanism, auth_data) -> AuthResult:
        self.auth_attempts += 1
        if self.behavior.auth_response:
            return AuthResult(success=False, handled=False, message=self.behavior.auth_response)
        if (
            isinstance(auth_data, LoginPassword)
            and auth_data.login.decode() == self.username
            and auth_data.password.decode() == self.password
        ):
            return AuthResult(success=True)
        return AuthResult(
            success=False,
            handled=False,
            message="535 5.7.139 Authentication unsuccessful, the user credentials were incorrect.",
        )

    def start(self) -> FakeSmtpServer:
        self._controller.start()
        return self

    def stop(self) -> None:
        with contextlib.suppress(Exception):
            self._controller.stop()

    def recipients(self) -> list[str]:
        with self.lock:
            return [r for m in self.messages for r in m.rcpt_tos]

    def __enter__(self) -> FakeSmtpServer:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()


def main() -> None:  # pragma: no cover - herramienta manual
    parser = argparse.ArgumentParser(description="Servidor SMTP de pruebas para EnvioCorreos")
    parser.add_argument("--port", type=int, default=8025)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    behavior = Behavior(
        rcpt_responses={
            "rechazar@ejemplo.com": "550 5.1.1 User unknown",
            "lento@ejemplo.com": "451 4.3.2 Temporary failure, try again later",
        }
    )
    srv = FakeSmtpServer(config.dev_cert_dir(), port=args.port, behavior=behavior).start()
    log.info(
        "Servidor de prueba en %s:%s (usuario %s; contraseña: DEV_PASSWORD en este módulo). "
        "CA en %s. Ctrl+C para salir.",
        srv.host,
        srv.port,
        srv.username,
        srv.ca_file,
    )
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.stop()


if __name__ == "__main__":  # pragma: no cover
    main()
