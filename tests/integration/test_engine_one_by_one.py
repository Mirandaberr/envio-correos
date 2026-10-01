"""Motor de campañas, modo uno por uno, contra el servidor SMTP local (US1, FR-053..056)."""

import pytest

from envio_correos import config
from envio_correos.core.engine import CampaignRunner, Finished, Paused, Progress
from envio_correos.core.journal import AttemptState, Journal
from envio_correos.core.journal import RecipientState as S
from envio_correos.logging_setup import setup_logging, teardown_logging
from envio_correos.texts import es
from tests.integration.engine_helpers import FakeTime, make_builder, make_campaign, make_provider

INTERVAL = round(config.min_interval_s(), 3)


@pytest.fixture
def journal(tmp_path):
    j = Journal(tmp_path / "j.db")
    yield j
    j.close()


def addrs(n):
    return [f"u{i}@x.com" for i in range(n)]


def runner(journal, provider, cid, n, ft, events):
    return CampaignRunner(
        provider=provider,
        journal=journal,
        campaign_id=cid,
        attempt_number=n,
        builder=make_builder(),
        on_event=events.append,
        monotonic=ft.monotonic,
        wait=ft.wait,
    )


def states(journal, cid, n):
    return [r.state for r in journal.recipients(cid, n)]


def test_rechazo_no_detiene_y_cada_correo_tiene_un_destinatario(smtp_server, journal):
    smtp_server.behavior.rcpt_responses["u2@x.com"] = "550 5.1.1 User unknown"
    cid, n = make_campaign(journal, addrs(20))
    ft, events = FakeTime(), []
    runner(journal, make_provider(smtp_server), cid, n, ft, events).run()

    st = states(journal, cid, n)
    assert st.count(S.SENT) == 19 and st[2] is S.FAILED
    failed = journal.recipients(cid, n)[2]
    assert failed.reason_code == "RECIPIENT_REJECTED" and failed.smtp_code == "550 5.1.1"
    assert failed.reason_text == es.reason_text("RECIPIENT_REJECTED")
    assert all(len(m.rcpt_tos) == 1 for m in smtp_server.messages)
    assert len(smtp_server.messages) == 19
    assert journal.attempt_state(cid, n) is AttemptState.DONE
    assert isinstance(events[-1], Finished) and events[-1].state is AttemptState.DONE
    assert sum(isinstance(e, Progress) for e in events) == 20


def test_respeta_el_ritmo_entre_envios(smtp_server, journal):
    cid, n = make_campaign(journal, addrs(5))
    ft = FakeTime()
    runner(journal, make_provider(smtp_server), cid, n, ft, []).run()
    assert ft.waits == [INTERVAL] * 4


def test_sending_se_confirma_antes_de_enviar(smtp_server, journal):
    cid, n = make_campaign(journal, addrs(3))
    provider = make_provider(smtp_server)
    seen = []

    def check(message):
        row = next(r for r in journal.recipients(cid, n) if r.address == message.to[0])
        seen.append(row.state)

    provider.before_send = check
    runner(journal, provider, cid, n, FakeTime(), []).run()
    assert seen == [S.SENDING] * 3


def test_detener_marca_restantes_como_omitidos(smtp_server, journal):
    cid, n = make_campaign(journal, addrs(10))
    ft, events = FakeTime(), []
    r = runner(journal, make_provider(smtp_server), cid, n, ft, events)

    def stop_after_five(fake):
        if len(smtp_server.messages) >= 5:
            r.stop()
            fake.stop.set()

    ft.on_wait = stop_after_five
    r.run()
    st = states(journal, cid, n)
    assert st.count(S.SENT) == 5 and st.count(S.SKIPPED) == 5
    skipped = journal.recipients(cid, n, {S.SKIPPED})[0]
    assert skipped.reason_text == es.SKIP_STOPPED_BY_USER
    assert journal.attempt_state(cid, n) is AttemptState.STOPPED
    assert events[-1].state is AttemptState.STOPPED


def test_transitorio_persistente_reintenta_y_pausa(smtp_server, journal):
    smtp_server.behavior.rcpt_responses["u1@x.com"] = "451 4.3.2 Try again later"
    cid, n = make_campaign(journal, addrs(4))
    ft, events = FakeTime(), []
    runner(journal, make_provider(smtp_server), cid, n, ft, events).run()
    assert list(config.TRANSIENT_RETRY_DELAYS_S) == [w for w in ft.waits if w != INTERVAL]
    assert states(journal, cid, n) == [S.SENT, S.PENDING, S.PENDING, S.PENDING]
    assert journal.attempt_state(cid, n) is AttemptState.PAUSED
    assert isinstance(events[-1], Paused) and events[-1].reason == "THROTTLED"


def test_transitorio_que_se_resuelve_en_el_reintento(smtp_server, journal):
    smtp_server.behavior.rcpt_responses["u1@x.com"] = "451 4.3.2 Try again later"
    cid, n = make_campaign(journal, addrs(3))
    ft = FakeTime()

    def heal(fake):
        if 30.0 in fake.waits:
            smtp_server.behavior.rcpt_responses.clear()

    ft.on_wait = heal
    runner(journal, make_provider(smtp_server), cid, n, ft, []).run()
    assert states(journal, cid, n) == [S.SENT] * 3


def test_error_de_cuenta_pausa_sin_enviar(smtp_server, journal):
    smtp_server.behavior.auth_response = (
        "535 5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled for the "
        "Mailbox."
    )
    cid, n = make_campaign(journal, addrs(3))
    events = []
    runner(journal, make_provider(smtp_server), cid, n, FakeTime(), events).run()
    assert states(journal, cid, n) == [S.PENDING] * 3
    assert journal.attempt_state(cid, n) is AttemptState.PAUSED
    assert events[-1].reason == "AUTH_SMTP_DISABLED"


def test_limite_diario_pausa_y_deja_pendientes(smtp_server, journal):
    cid, n = make_campaign(journal, addrs(8))
    events = []
    provider = make_provider(smtp_server, recipients_per_24h=5)
    runner(journal, provider, cid, n, FakeTime(), events).run()
    st = states(journal, cid, n)
    assert st.count(S.SENT) == 5 and st.count(S.PENDING) == 3
    assert journal.attempt_state(cid, n) is AttemptState.PAUSED
    assert events[-1].reason == "DAILY_LIMIT"


def test_limite_diario_cuenta_lo_ya_enviado_en_24h(smtp_server, journal):
    prev_cid, prev_n = make_campaign(journal, addrs(3))
    for seq in range(3):
        journal.mark_result(prev_cid, prev_n, seq, S.SENT)
    cid, n = make_campaign(journal, [f"v{i}@x.com" for i in range(4)])
    provider = make_provider(smtp_server, recipients_per_24h=5)
    runner(journal, provider, cid, n, FakeTime(), []).run()
    assert states(journal, cid, n).count(S.SENT) == 2


def test_reconecta_si_el_servidor_corta_sin_perder_ni_duplicar(smtp_server, journal):
    smtp_server.behavior.drop_connection_after_messages = 3
    cid, n = make_campaign(journal, addrs(10))
    runner(journal, make_provider(smtp_server), cid, n, FakeTime(), []).run()
    assert states(journal, cid, n) == [S.SENT] * 10
    assert sorted(smtp_server.recipients()) == sorted(addrs(10))


def test_logs_con_track_id_de_campana(smtp_server, journal, tmp_path):
    handler = setup_logging(tmp_path / "logs")
    try:
        cid, n = make_campaign(journal, addrs(2))
        runner(journal, make_provider(smtp_server), cid, n, FakeTime(), []).run()
        handler.flush()
        text = (tmp_path / "logs" / config.LOG_FILENAME).read_text(encoding="utf-8")
    finally:
        teardown_logging()
    assert f"[{cid}]" in text
    assert "u0@x.com" not in text  # direcciones enmascaradas


def test_corre_en_un_hilo(smtp_server, journal):
    cid, n = make_campaign(journal, addrs(2))
    r = runner(journal, make_provider(smtp_server), cid, n, FakeTime(), [])
    r.start()
    r.join(timeout=10)
    assert not r.is_alive()
    assert states(journal, cid, n) == [S.SENT] * 2
