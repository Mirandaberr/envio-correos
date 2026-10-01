"""Reanudación tras un cierre inesperado (US7, SC-003, SC-004)."""

import pytest

from envio_correos.core import report
from envio_correos.core.engine import CampaignRunner
from envio_correos.core.journal import AttemptState, Journal
from envio_correos.core.journal import RecipientState as S
from envio_correos.texts import es
from tests.integration.engine_helpers import FakeTime, make_builder, make_campaign, make_provider


@pytest.fixture
def journal(tmp_path):
    j = Journal(tmp_path / "j.db")
    yield j
    j.close()


def crashed_campaign(journal):
    """Simula el estado en disco tras un cierre: 10 SENT, 1 SENDING, 9 PENDING, RUNNING."""
    cid, n = make_campaign(journal, [f"u{i}@x.com" for i in range(20)])
    for seq in range(10):
        journal.mark_result(cid, n, seq, S.SENT)
    journal.mark_sending(cid, n, 10)
    return cid, n


def test_al_iniciar_marca_interrumpido_y_lo_ofrece(journal):
    cid, n = crashed_campaign(journal)
    assert journal.mark_interrupted_running() == 1
    assert journal.attempt_state(cid, n) is AttemptState.INTERRUPTED
    (u,) = journal.unfinished_attempts()
    assert (u.campaign_id, u.number, u.pending, u.unknown) == (cid, n, 9, 1)


def test_continuar_envia_solo_los_pendientes(smtp_server, journal):
    cid, n = crashed_campaign(journal)
    journal.mark_interrupted_running()
    CampaignRunner(
        provider=make_provider(smtp_server),
        journal=journal,
        campaign_id=cid,
        attempt_number=n,
        builder=make_builder(),
        monotonic=FakeTime().monotonic,
        wait=FakeTime().wait,
    ).run()
    assert sorted(smtp_server.recipients()) == sorted(f"u{i}@x.com" for i in range(11, 20))
    states = [r.state for r in journal.recipients(cid, n)]
    assert states.count(S.SENT) == 19 and states[10] is S.SENDING  # el dudoso no se reenvía
    assert journal.attempt_state(cid, n) is AttemptState.DONE
    assert journal.unfinished_attempts() == []
    rows = report.rows_to_fix(journal, cid, n)
    assert [(r.recipient.address, r.status) for r in rows] == [
        ("u10@x.com", es.REPORT_STATUS_UNKNOWN)
    ]


def test_reenviar_tambien_a_los_dudosos(smtp_server, journal):
    cid, n = crashed_campaign(journal)
    journal.mark_interrupted_running()
    journal.requeue_unknown(cid, n)
    CampaignRunner(
        provider=make_provider(smtp_server),
        journal=journal,
        campaign_id=cid,
        attempt_number=n,
        builder=make_builder(),
        monotonic=FakeTime().monotonic,
        wait=FakeTime().wait,
    ).run()
    assert "u10@x.com" in smtp_server.recipients()
    assert journal.counts(cid, n) == {S.SENT: 20}


def test_descartar_deja_pendientes_en_el_reporte(journal, tmp_path):
    cid, n = crashed_campaign(journal)
    journal.mark_interrupted_running()
    journal.discard_attempt(cid, n)
    assert journal.attempt_state(cid, n) is AttemptState.STOPPED
    assert journal.unfinished_attempts() == []
    rows = report.rows_to_fix(journal, cid, n)
    statuses = [r.status for r in rows]
    assert statuses.count(es.REPORT_STATUS_PENDING) == 9
    assert statuses.count(es.REPORT_STATUS_UNKNOWN) == 1
    assert {r.reason for r in rows if r.status == es.REPORT_STATUS_PENDING} == {es.SKIP_INTERRUPTED}


def test_pausado_por_limite_tambien_se_ofrece(journal):
    cid, n = make_campaign(journal, ["a@x.com", "b@x.com"])
    journal.mark_result(cid, n, 0, S.SENT)
    journal.set_attempt_state(cid, n, AttemptState.PAUSED)
    (u,) = journal.unfinished_attempts()
    assert (u.state, u.pending) == (AttemptState.PAUSED, 1)
