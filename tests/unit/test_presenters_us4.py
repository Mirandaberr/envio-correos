"""Paso Modo con "Todos a la vez" (US4)."""

from envio_correos.core.message_builder import MessageTemplate, SendMode
from envio_correos.gui.presenters.base import WizardContext
from envio_correos.gui.presenters.mode import ModePresenter


def ctx_with(subject="Aviso", body="Hola a todos"):
    ctx = WizardContext()
    ctx.template = MessageTemplate(subject, body)
    return ctx


def test_ambas_opciones_disponibles_y_ninguna_elegida():
    p = ModePresenter(ctx_with())
    assert SendMode.ONE_BY_ONE in p.available and SendMode.ALL_AT_ONCE_BCC in p.available
    assert p.selected is None


def test_todos_a_la_vez_por_defecto_en_copia_oculta():
    p = ModePresenter(ctx_with())
    p.select(SendMode.ALL_AT_ONCE_BCC)
    assert p.selected is SendMode.ALL_AT_ONCE_BCC and p.can_advance().ok


def test_variables_bloquean_todos_a_la_vez():
    p = ModePresenter(ctx_with(body="Hola {Nombre}"))
    p.select(SendMode.ALL_AT_ONCE_BCC)
    g = p.can_advance()
    assert not g.ok and "{Nombre}" in g.reason
    p.select(SendMode.ONE_BY_ONE)
    assert p.can_advance().ok


def test_mostrar_destinatarios_exige_aceptar_advertencia():
    p = ModePresenter(ctx_with())
    p.select(SendMode.ALL_AT_ONCE_BCC)
    p.set_show_recipients(True)
    assert p.selected is SendMode.ALL_AT_ONCE_VISIBLE
    g = p.can_advance()
    assert not g.ok and g.confirm is not None and "privacidad" in g.reason.lower()
    g.confirm()
    assert p.can_advance().ok
    p.set_show_recipients(False)
    assert p.selected is SendMode.ALL_AT_ONCE_BCC


def test_confirmacion_informa_cantidad_de_mensajes(tmp_path, fixtures_dir):
    from envio_correos.core.journal import Journal
    from envio_correos.gui.presenters.recipients import RecipientsPresenter
    from envio_correos.gui.presenters.review import ReviewPresenter
    from tests.unit.test_presenters_us1 import FakeProvider, NoDns  # reutiliza dobles

    j = Journal(tmp_path / "j.db")
    try:
        ctx = ctx_with()
        ctx.journal, ctx.provider = j, FakeProvider("yo@empresa.com", "", "")
        ctx.account_email = "yo@empresa.com"
        RecipientsPresenter(ctx, NoDns).load(fixtures_dir["lista_5000"])
        ctx.mode = SendMode.ALL_AT_ONCE_BCC
        text = ReviewPresenter(ctx).confirmation_text()
        assert "5000 destinatarios" in text and "50 correos" in text
    finally:
        j.close()
