"""Memoria estable durante una campaña con adjunto (SC-011, research R7.4)."""

import gc

import psutil
import pytest

from envio_correos.core import attachments
from envio_correos.core.engine import CampaignRunner, Progress
from envio_correos.core.journal import Journal
from envio_correos.core.message_builder import MessageBuilder, MessageTemplate
from tests.integration.engine_helpers import FakeTime, make_campaign, make_provider

pytestmark = pytest.mark.slow

SENDS = 300
MAX_GROWTH_MB = 30


def test_rss_estable_con_adjunto_de_3mb(smtp_server, tmp_path):
    adj = tmp_path / "adjunto.bin"
    adj.write_bytes(b"\x00\x01" * (3 * 1024**2 // 2))
    ref = attachments.make_ref(adj)
    journal = Journal(tmp_path / "j.db")
    cid, n = make_campaign(journal, [f"u{i}@x.com" for i in range(SENDS)])
    builder = MessageBuilder(
        template=MessageTemplate("Hola", "Cuerpo", (ref,)),
        headers=("Nombre", "Correo"),
        sender_email=smtp_server.username,
        display_name="",
        attachments=attachments.load_for_attempt([ref]),
    )
    proc = psutil.Process()
    samples: list[float] = []

    def sample(event):
        if isinstance(event, Progress):
            samples.append(proc.memory_info().rss / 1e6)

    ft = FakeTime()

    def drop_messages(_fake):
        smtp_server.messages.clear()

    ft.on_wait = drop_messages
    runner = CampaignRunner(
        provider=make_provider(smtp_server),
        journal=journal,
        campaign_id=cid,
        attempt_number=n,
        builder=builder,
        on_event=sample,
        monotonic=ft.monotonic,
        wait=ft.wait,
    )
    runner.run()
    gc.collect()
    journal.close()
    first = max(samples[SENDS // 10 : SENDS // 10 + 10])
    last = max(samples[-10:])
    assert len(samples) == SENDS
    print(f"RSS al 10%: {first:.1f} MB, al final: {last:.1f} MB")  # noqa: T201 - evidencia
    assert last - first < MAX_GROWTH_MB, (first, last)
    assert builder.attachments == ()  # el motor libera los adjuntos al terminar (FR-075)
