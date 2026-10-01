"""Ciclo completo: enviar → reporte → corregir a mano → reintentar (US3, SC-009)."""

import datetime as dt

import pytest
from openpyxl import load_workbook

from envio_correos import config
from envio_correos.core import excel_reader, report, retry
from envio_correos.core.engine import CampaignRunner
from envio_correos.core.journal import CampaignSpec, Journal
from envio_correos.core.journal import RecipientState as S
from envio_correos.core.message_builder import MessageBuilder
from envio_correos.core.recipients import RecipientList
from tests.fixtures.make_fixtures import make_lista
from tests.integration.engine_helpers import FakeTime, make_provider


@pytest.fixture
def journal(tmp_path):
    j = Journal(tmp_path / "j.db")
    yield j
    j.close()


def run(journal, srv, cid, n, template, headers):
    builder = MessageBuilder(
        template=template, headers=headers, sender_email=srv.username, display_name=""
    )
    CampaignRunner(
        provider=make_provider(srv),
        journal=journal,
        campaign_id=cid,
        attempt_number=n,
        builder=builder,
        monotonic=FakeTime().monotonic,
        wait=FakeTime().wait,
    ).run()


def test_corregir_typo_y_reintentar_solo_lo_corregido(smtp_server, journal, tmp_path):
    from envio_correos.core.message_builder import MessageTemplate

    source = make_lista(tmp_path / "lista.xlsx", 5, "x.com")
    smtp_server.behavior.rcpt_responses["user2@x.com"] = "550 5.1.1 User unknown"
    lst = RecipientList.from_sheet(excel_reader.read_sheet(source), str(source))
    template = MessageTemplate("Novedades", "Hola")
    spec = CampaignSpec(
        "yo@empresa.com",
        str(source),
        lst.sheet_name,
        lst.headers,
        lst.email_col,
        template.subject,
        template.body,
        (),
        "ONE_BY_ONE",
    )
    cid = journal.create_campaign(spec)
    n1 = journal.start_attempt(cid, lst.to_attempt_rows(), lst.headers)
    run(journal, smtp_server, cid, n1, template, lst.headers)
    assert len(smtp_server.messages) == 4
    path = report.write_report(journal, cid, n1, now=dt.datetime(2026, 9, 30, 10, 0))

    wb = load_workbook(path)
    wb[config.REPORT_SHEET_NAME]["C2"] = "user2@y.com"  # corrección manual
    wb.save(path)
    smtp_server.messages.clear()

    r = retry.load_retry(path, journal)
    assert r.campaign_id == cid and r.recipients.counts().effective == 1
    n2 = journal.start_attempt(cid, r.recipients.to_attempt_rows(), r.recipients.headers)
    run(journal, smtp_server, cid, n2, r.template, r.recipients.headers)

    assert [m.rcpt_tos for m in smtp_server.messages] == [["user2@y.com"]]
    assert b"Subject: Novedades" in smtp_server.messages[0].data
    assert n2 == 2 and journal.counts(cid, n2) == {"SENT": 1}
    assert report.write_report(journal, cid, n2) is None  # nada más que corregir


def test_reintentos_sucesivos(smtp_server, journal, tmp_path):
    from envio_correos.core.message_builder import MessageTemplate

    source = make_lista(tmp_path / "lista.xlsx", 3, "x.com")
    smtp_server.behavior.rcpt_responses["user1@x.com"] = "550 5.1.1 User unknown"
    lst = RecipientList.from_sheet(excel_reader.read_sheet(source), str(source))
    t = MessageTemplate("A", "B")
    cid = journal.create_campaign(
        CampaignSpec(
            "yo@empresa.com",
            str(source),
            lst.sheet_name,
            lst.headers,
            lst.email_col,
            "A",
            "B",
            (),
            "ONE_BY_ONE",
        )
    )
    n = journal.start_attempt(cid, lst.to_attempt_rows(), lst.headers)
    run(journal, smtp_server, cid, n, t, lst.headers)
    for expected in (2, 3):
        path = report.write_report(journal, cid, n)
        r = retry.load_retry(path, journal)
        n = journal.start_attempt(cid, r.recipients.to_attempt_rows(), r.recipients.headers)
        assert n == expected
        run(journal, smtp_server, cid, n, r.template, r.recipients.headers)
        assert journal.counts(cid, n) == {S.FAILED: 1}
    assert r.code == f"{cid}-R3"
