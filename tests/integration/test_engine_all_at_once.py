"""Motor en modo "Todos a la vez" (US4, FR-041, FR-042)."""

from email import message_from_bytes
from email.policy import default as default_policy

import pytest

from envio_correos.core.engine import CampaignRunner
from envio_correos.core.journal import Journal
from envio_correos.core.journal import RecipientState as S
from envio_correos.core.message_builder import MessageBuilder, MessageTemplate, SendMode
from tests.integration.engine_helpers import FakeTime, make_campaign, make_provider


@pytest.fixture
def journal(tmp_path):
    j = Journal(tmp_path / "j.db")
    yield j
    j.close()


def addrs(n):
    return [f"u{i}@x.com" for i in range(n)]


def run(journal, srv, cid, n, mode=SendMode.ALL_AT_ONCE_BCC, **limits):
    builder = MessageBuilder(
        template=MessageTemplate("Aviso", "Hola a todos"),
        headers=("Nombre", "Correo"),
        sender_email=srv.username,
        display_name="",
        mode=mode,
    )
    CampaignRunner(
        provider=make_provider(srv, **limits),
        journal=journal,
        campaign_id=cid,
        attempt_number=n,
        builder=builder,
        monotonic=FakeTime().monotonic,
        wait=FakeTime().wait,
    ).run()


def test_250_destinatarios_en_3_lotes_con_copia_oculta(smtp_server, journal):
    cid, n = make_campaign(journal, addrs(250))
    run(journal, smtp_server, cid, n)
    assert len(smtp_server.messages) == 3
    assert [len(m.rcpt_tos) for m in smtp_server.messages] == [101, 101, 51]  # +1: remitente
    parsed = message_from_bytes(smtp_server.messages[0].data, policy=default_policy)
    assert parsed["To"] == smtp_server.username and parsed["Bcc"] is None
    assert journal.counts(cid, n) == {S.SENT: 250}


def test_destinatarios_visibles(smtp_server, journal):
    cid, n = make_campaign(journal, addrs(3))
    run(journal, smtp_server, cid, n, mode=SendMode.ALL_AT_ONCE_VISIBLE)
    parsed = message_from_bytes(smtp_server.messages[0].data, policy=default_policy)
    assert [a.addr_spec for a in parsed["To"].addresses] == addrs(3)


def test_rechazo_parcial_solo_marca_esas_direcciones(smtp_server, journal):
    smtp_server.behavior.rcpt_responses.update(
        {"u3@x.com": "550 5.1.1 No", "u7@x.com": "550 5.1.1 No"}
    )
    cid, n = make_campaign(journal, addrs(10))
    run(journal, smtp_server, cid, n)
    st = [r.state for r in journal.recipients(cid, n)]
    assert st[3] is S.FAILED and st[7] is S.FAILED and st.count(S.SENT) == 8


def test_demasiados_destinatarios_divide_el_lote(smtp_server, journal):
    smtp_server.behavior.max_rcpts_per_message = 30  # el servidor acepta 30 por mensaje
    cid, n = make_campaign(journal, addrs(100))
    run(journal, smtp_server, cid, n)
    assert journal.counts(cid, n) == {S.SENT: 100}
    assert all(len(m.rcpt_tos) <= 30 for m in smtp_server.messages)
    assert sorted(a for a in smtp_server.recipients() if a != smtp_server.username) == sorted(
        addrs(100)
    )


def test_cupo_diario_cuenta_destinatarios_no_mensajes(smtp_server, journal):
    cid, n = make_campaign(journal, addrs(150))
    run(journal, smtp_server, cid, n, recipients_per_24h=120)
    c = journal.counts(cid, n)
    assert c[S.SENT] == 100 and c[S.PENDING] == 50
