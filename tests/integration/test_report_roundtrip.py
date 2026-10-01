"""Campaña real contra SMTP local → Excel de fallidos → reutilizable como fuente (US2)."""

import datetime as dt

import pytest

from envio_correos import config
from envio_correos.core import excel_reader, report
from envio_correos.core.engine import CampaignRunner
from envio_correos.core.journal import CampaignSpec, Journal
from envio_correos.core.recipients import RecipientList
from tests.fixtures.make_fixtures import make_lista
from tests.integration.engine_helpers import FakeTime, make_builder, make_provider


@pytest.fixture
def journal(tmp_path):
    j = Journal(tmp_path / "j.db")
    yield j
    j.close()


def test_dos_rechazados_generan_reporte_reutilizable(smtp_server, journal, tmp_path):
    source = make_lista(tmp_path / "lista.xlsx", 6, "x.com")
    smtp_server.behavior.rcpt_responses.update(
        {
            "user1@x.com": "550 5.1.1 User unknown",
            "user4@x.com": "550 5.1.1 User unknown",
        }
    )
    lst = RecipientList.from_sheet(excel_reader.read_sheet(source), str(source))
    spec = CampaignSpec(
        "yo@empresa.com",
        str(source),
        lst.sheet_name,
        lst.headers,
        lst.email_col,
        "Hola",
        "Cuerpo",
        (),
        "ONE_BY_ONE",
    )
    cid = journal.create_campaign(spec)
    n = journal.start_attempt(cid, lst.to_attempt_rows(), lst.headers)
    CampaignRunner(
        provider=make_provider(smtp_server),
        journal=journal,
        campaign_id=cid,
        attempt_number=n,
        builder=make_builder(),
        monotonic=FakeTime().monotonic,
        wait=FakeTime().wait,
    ).run()
    assert len(smtp_server.messages) == 4

    path = report.write_report(journal, cid, n, now=dt.datetime(2026, 9, 30, 10, 0))
    data = excel_reader.read_sheet(path)
    assert len(data.rows) == 2
    assert data.headers[: len(lst.headers)] == lst.headers
    assert [r[2] for r in data.rows] == ["user1@x.com", "user4@x.com"]

    again = RecipientList.from_sheet(data, str(path))
    assert again.headers[again.email_col] == "Correo"
    assert config.COL_STATUS not in again.variable_columns()
    assert again.counts().effective == 2
