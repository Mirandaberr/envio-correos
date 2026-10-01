"""Presenters de US5: variables, adjuntos, vista previa y prueba a sí misma."""

import pytest

from envio_correos.core.journal import Journal
from envio_correos.core.message_builder import MessageTemplate, SendMode
from envio_correos.gui.presenters.base import WizardContext
from envio_correos.gui.presenters.message import MessagePresenter, load_draft
from envio_correos.gui.presenters.recipients import RecipientsPresenter
from envio_correos.gui.presenters.review import ReviewPresenter
from tests.unit.test_presenters_us1 import LIMITS, NoDns


@pytest.fixture
def ctx(fixtures_dir, tmp_path):
    c = WizardContext()
    RecipientsPresenter(c, NoDns).load(fixtures_dir["lista_20"])
    return c


def msg(ctx, tmp_path):
    p = MessagePresenter(ctx, tmp_path / "draft.json")
    p.on_enter()
    return p


def test_variables_disponibles_son_las_columnas(ctx, tmp_path):
    p = msg(ctx, tmp_path)
    assert p.variables()[:3] == ("Nombre", "Apellido", "Correo")
    assert p.token("Nombre") == "{Nombre}"


def test_variable_inexistente_bloquea(ctx, tmp_path):
    p = msg(ctx, tmp_path)
    p.set_text("Hola {Nombre}", "Tu ciudad: {Ciudad}. Tu {Edad}")
    g = p.can_advance()
    assert not g.ok and "{Edad}" in g.reason and "{Ciudad}" not in g.reason


def test_adjuntos_agregar_quitar_y_limite(ctx, tmp_path, monkeypatch):
    from envio_correos import config

    a, b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    a.write_bytes(b"x" * 10)
    b.write_bytes(b"y" * 20)
    p = msg(ctx, tmp_path)
    p.set_text("Asunto", "Cuerpo")
    assert p.add_files([a, b]) == []
    assert [r.path for r in p.attachments] == [str(a), str(b)]
    assert p.can_advance().ok
    monkeypatch.setattr(config, "MAX_ATTACHMENTS_RAW_BYTES", 25)
    g = p.can_advance()
    assert not g.ok and "reducí" in g.reason
    p.remove_attachment(1)
    assert p.can_advance().ok


def test_adjunto_ilegible_se_informa(ctx, tmp_path):
    p = msg(ctx, tmp_path)
    errors = p.add_files([tmp_path / "no-existe.pdf"])
    assert errors and "no-existe.pdf" in errors[0] and p.attachments == []


def test_borrador_incluye_adjuntos_y_avisa_si_faltan(ctx, tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"x")
    p = msg(ctx, tmp_path)
    p.set_text("A", "B")
    p.add_files([f])
    p.on_leave()
    assert [r.path for r in load_draft(tmp_path / "draft.json").attachments] == [str(f)]
    f.unlink()
    p2 = msg(WizardContext(), tmp_path)
    assert "a.pdf" in p2.attachment_warning()
    assert not p2.can_advance().ok  # adjunto ausente: quitarlo o volver a elegirlo


def review(ctx, tmp_path, subject="Hola {Nombre}", body="Ciudad: {Ciudad}"):
    ctx.journal = Journal(tmp_path / "j.db")
    ctx.template = MessageTemplate(subject, body)
    ctx.mode = SendMode.ONE_BY_ONE
    ctx.account_email = "yo@empresa.com"
    return ReviewPresenter(ctx)


def test_vista_previa_navegable(ctx, tmp_path):
    p = review(ctx, tmp_path)
    try:
        assert p.preview_count == 20
        first, second = p.preview(0), p.preview(1)
        assert first["to"] == "user0@empresa.com" and first["subject"] == "Hola José 0"
        assert second["subject"] == "Hola María 1" and second["body"] == "Ciudad: Medellín"
        ctx.recipients.toggle(0)
        assert p.preview_count == 19 and p.preview(0)["to"] == "user1@empresa.com"
    finally:
        ctx.journal.close()


def test_vista_previa_todos_a_la_vez(ctx, tmp_path):
    p = review(ctx, tmp_path, "Aviso", "Hola a todos")
    ctx.mode = SendMode.ALL_AT_ONCE_BCC
    try:
        assert p.preview(0)["to"].startswith("yo@empresa.com")
        assert "copia oculta" in p.preview(0)["to"]
    finally:
        ctx.journal.close()


def test_aviso_de_valores_vacios(ctx, tmp_path):
    from openpyxl import Workbook

    from envio_correos.gui.presenters.recipients import RecipientsPresenter

    path = tmp_path / "vacios.xlsx"
    wb = Workbook()
    for r in (("Nombre", "Correo"), ("Ana", "a@x.com"), (None, "b@x.com"), ("", "c@x.com")):
        wb.active.append(r)
    wb.save(path)
    c = WizardContext()
    RecipientsPresenter(c, NoDns).load(path)
    p = review(c, tmp_path, "Hola {Nombre}", "x")
    try:
        assert p.empty_values_warning() == "2 destinatarios tienen {Nombre} vacío (filas 3, 4)."
    finally:
        c.journal.close()


def test_enviarme_una_prueba_no_toca_el_journal(ctx, tmp_path):
    sent = []

    class Provider:
        sender_email = "yo@empresa.com"
        limits = LIMITS

        def send(self, message):
            sent.append(message)
            from envio_correos.core.providers.base import SendOutcome

            return SendOutcome(message.to, {})

        def close(self):
            pass

    p = review(ctx, tmp_path)
    ctx.provider = Provider()
    try:
        assert p.send_test() is None
        assert sent[0].to == ("yo@empresa.com",) and sent[0].subject == "Hola José 0"
        assert ctx.campaign_id is None
    finally:
        ctx.journal.close()
