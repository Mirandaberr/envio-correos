"""Utilidades para probar el motor sin dormir de verdad."""

from __future__ import annotations

import dataclasses
import threading

from envio_correos.core.journal import CampaignSpec, Journal, RecipientRow
from envio_correos.core.message_builder import MessageBuilder, MessageTemplate
from envio_correos.core.providers.m365_smtp import M365SmtpPasswordProvider
from tests.smtp_fixtures import endpoint_for


class FakeTime:
    """Reloj monotónico falso: solo avanza cuando el motor espera."""

    def __init__(self):
        self.t = 1000.0
        self.waits: list[float] = []
        self.stop = threading.Event()
        self.on_wait = None  # gancho opcional: se llama antes de cada espera

    def monotonic(self) -> float:
        return self.t

    def wait(self, seconds: float) -> bool:
        if self.on_wait:
            self.on_wait(self)
        self.waits.append(round(seconds, 3))
        self.t += seconds
        return self.stop.is_set()


class LimitedProvider:
    """Envuelve un proveedor real y permite cambiar sus límites."""

    def __init__(self, inner, **limit_overrides):
        self._inner = inner
        self._limits = dataclasses.replace(inner.limits, **limit_overrides)
        self.provider_id = inner.provider_id
        self.sender_email = inner.sender_email
        self.before_send = None

    @property
    def limits(self):
        return self._limits

    def test_connection(self):
        return self._inner.test_connection()

    def open(self):
        self._inner.open()

    def close(self):
        self._inner.close()

    def send(self, message):
        if self.before_send:
            self.before_send(message)
        return self._inner.send(message)


def make_provider(srv, **limit_overrides):
    inner = M365SmtpPasswordProvider(srv.username, srv.password, endpoint=endpoint_for(srv))
    return LimitedProvider(inner, **limit_overrides)


def make_campaign(journal: Journal, addresses: list[str], account="yo@empresa.com"):
    spec = CampaignSpec(
        account_email=account,
        source_path=str(journal.path.parent / "lista.xlsx"),  # nunca relativa al repo
        sheet_name="Hoja",
        headers=("Nombre", "Correo"),
        email_col=1,
        subject="Hola",
        body="Cuerpo",
        attachments=(),
        mode="ONE_BY_ONE",
    )
    cid = journal.create_campaign(spec)
    rows = [RecipientRow(i + 2, a, (f"N{i}", a)) for i, a in enumerate(addresses)]
    n = journal.start_attempt(cid, rows)
    return cid, n


def make_builder(sender="yo@empresa.com"):
    return MessageBuilder(
        template=MessageTemplate("Hola", "Cuerpo"),
        headers=("Nombre", "Correo"),
        sender_email=sender,
        display_name="",
    )
