import datetime as dt
import sqlite3

import pytest

from envio_correos.core.journal import (
    AttemptState,
    CampaignSpec,
    Journal,
    RecipientRow,
    RecipientState,
    attempt_code,
)


class Clock:
    def __init__(self):
        self.now = dt.datetime(2026, 9, 30, 12, 0, tzinfo=dt.UTC)

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def journal(tmp_path, clock):
    j = Journal(tmp_path / "campaigns.db", clock=clock)
    yield j
    j.close()


def spec(account="yo@empresa.com"):
    return CampaignSpec(
        account_email=account,
        source_path="/tmp/lista.xlsx",
        sheet_name="Hoja1",
        headers=("Nombre", "Correo", "Alta"),
        email_col=1,
        subject="Hola {Nombre}",
        body="Cuerpo",
        attachments=({"path": "/tmp/a.pdf", "size": 10, "sha256": "ab"},),
        mode="ONE_BY_ONE",
    )


def rows(n=3):
    return [
        RecipientRow(
            source_row=i + 2,
            address=f"u{i}@x.com",
            values=(f"U{i}", f"u{i}@x.com", dt.datetime(2026, 1, i + 1, 8, 30)),
        )
        for i in range(n)
    ]


def test_wal_y_esquema(journal, tmp_path):
    mode = sqlite3.connect(tmp_path / "campaigns.db").execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


def test_crear_campana_y_recuperarla(journal):
    cid = journal.create_campaign(spec())
    assert cid.startswith("C-") and len(cid) == 6
    got = journal.get_campaign(cid)
    assert got.spec == spec()


def test_codigos_unicos(journal):
    ids = {journal.create_campaign(spec()) for _ in range(50)}
    assert len(ids) == 50


def test_codigo_de_intento():
    assert attempt_code("C-7F3A", 1) == "C-7F3A"
    assert attempt_code("C-7F3A", 2) == "C-7F3A-R2"


def test_intento_inserta_destinatarios_pendientes_conservando_tipos(journal):
    cid = journal.create_campaign(spec())
    n = journal.start_attempt(cid, rows())
    assert n == 1
    stored = journal.recipients(cid, n)
    assert [r.state for r in stored] == [RecipientState.PENDING] * 3
    assert stored[0].values == ("U0", "u0@x.com", dt.datetime(2026, 1, 1, 8, 30))
    assert journal.attempt_state(cid, n) is AttemptState.RUNNING


def test_transiciones_visibles_desde_otra_conexion(journal, tmp_path):
    cid = journal.create_campaign(spec())
    n = journal.start_attempt(cid, rows(1))
    journal.mark_sending(cid, n, 0)
    other = sqlite3.connect(tmp_path / "campaigns.db")
    q = "SELECT state FROM recipient WHERE campaign_id=? AND row_seq=0"
    assert other.execute(q, (cid,)).fetchone()[0] == "SENDING"
    journal.mark_result(
        cid, n, 0, RecipientState.FAILED, "RECIPIENT_REJECTED", "Rechazada", "550 5.1.1"
    )
    assert other.execute(q, (cid,)).fetchone()[0] == "FAILED"
    r = journal.recipients(cid, n)[0]
    assert (r.reason_code, r.reason_text, r.smtp_code) == (
        "RECIPIENT_REJECTED",
        "Rechazada",
        "550 5.1.1",
    )


def test_sending_puede_volver_a_pending(journal):
    cid = journal.create_campaign(spec())
    n = journal.start_attempt(cid, rows(1))
    journal.mark_sending(cid, n, 0)
    journal.mark_result(cid, n, 0, RecipientState.PENDING)
    assert [r.row_seq for r in journal.recipients(cid, n, {RecipientState.PENDING})] == [0]


def test_estado_de_intento_y_reporte(journal):
    cid = journal.create_campaign(spec())
    n = journal.start_attempt(cid, rows(1))
    journal.set_attempt_state(cid, n, AttemptState.DONE, report_path="/tmp/r.xlsx")
    assert journal.attempt_state(cid, n) is AttemptState.DONE
    assert journal.report_path(cid, n) == "/tmp/r.xlsx"


def test_contadores(journal):
    cid = journal.create_campaign(spec())
    n = journal.start_attempt(cid, rows(3))
    journal.mark_result(cid, n, 0, RecipientState.SENT)
    journal.mark_result(cid, n, 1, RecipientState.FAILED, "RECIPIENT_REJECTED")
    assert journal.counts(cid, n) == {"SENT": 1, "FAILED": 1, "PENDING": 1}


def test_enviados_en_ultimas_24h_por_cuenta(journal, clock):
    a = journal.create_campaign(spec("yo@empresa.com"))
    b = journal.create_campaign(spec("otra@empresa.com"))
    na, nb = journal.start_attempt(a, rows(3)), journal.start_attempt(b, rows(2))
    journal.mark_result(a, na, 0, RecipientState.SENT)
    clock.now += dt.timedelta(hours=23)
    journal.mark_result(a, na, 1, RecipientState.SENT)
    journal.mark_result(b, nb, 0, RecipientState.SENT)
    assert journal.sent_last_24h("yo@empresa.com") == 2
    clock.now += dt.timedelta(hours=2)
    assert journal.sent_last_24h("yo@empresa.com") == 1
    assert journal.sent_last_24h("YO@empresa.com") == 1


def test_direcciones_ya_enviadas_en_la_campana(journal):
    cid = journal.create_campaign(spec())
    n = journal.start_attempt(cid, rows(3))
    journal.mark_result(cid, n, 0, RecipientState.SENT)
    journal.mark_result(cid, n, 1, RecipientState.FAILED, "X")
    assert journal.already_sent_addresses(cid) == {"u0@x.com"}


def test_siguiente_intento(journal):
    cid = journal.create_campaign(spec())
    assert journal.start_attempt(cid, rows(1)) == 1
    assert journal.start_attempt(cid, rows(1)) == 2
    assert journal.latest_attempt(cid) == 2


def test_purga_campanas_viejas(journal, clock):
    vieja = journal.create_campaign(spec())
    journal.start_attempt(vieja, rows(2))
    clock.now += dt.timedelta(days=31)
    nueva = journal.create_campaign(spec())
    journal.start_attempt(nueva, rows(1))
    assert journal.purge(30) == 1
    assert journal.get_campaign(vieja) is None
    assert journal.get_campaign(nueva) is not None
    assert journal.recipients(vieja, 1) == []


def test_borrar_campana_y_todo_el_historial(journal):
    a = journal.create_campaign(spec())
    journal.start_attempt(a, rows(2))
    b = journal.create_campaign(spec())
    journal.start_attempt(b, rows(1))
    journal.delete_campaign(a)
    assert journal.get_campaign(a) is None and journal.recipients(a, 1) == []
    assert journal.get_campaign(b) is not None
    assert journal.delete_all() == 1
    assert journal.get_campaign(b) is None


def test_encabezados_del_intento(journal):
    cid = journal.create_campaign(spec())
    n1 = journal.start_attempt(cid, rows(1))
    n2 = journal.start_attempt(cid, rows(1), ("Correo", "Nombre", "Alta", "Estado"))
    assert journal.attempt_headers(cid, n1) == ("Nombre", "Correo", "Alta")  # los de la campaña
    assert journal.attempt_headers(cid, n2) == ("Correo", "Nombre", "Alta", "Estado")
