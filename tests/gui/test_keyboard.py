"""Accesibilidad mínima de teclado (T086, contracts/wizard-ui.md)."""

import pytest

from envio_correos.core.journal import Journal
from envio_correos.core.message_builder import MessageTemplate, SendMode
from envio_correos.gui import main_window
from envio_correos.gui.presenters.base import STEP_MESSAGE, STEP_MODE

pytestmark = pytest.mark.slow


def drive(script):
    journal = Journal()
    app = main_window.build(journal)
    app.show_info = app.show_error = lambda m: None
    out = {}

    def run():
        try:
            script(app, out)
        finally:
            app.after(20, app.destroy)

    app.after(100, run)
    app.mainloop()
    journal.close()
    return out


def test_enter_en_el_cuerpo_no_avanza(isolated_app_dirs):
    def script(app, out):
        app.go_to(STEP_MESSAGE)
        v = app.current_view()
        v.subject.insert(0, "Hola")
        v.body._textbox.focus_force()
        app.update()
        v.body._textbox.event_generate("<Return>")
        app.update()
        out["paso"] = app.wizard.index

    assert drive(script)["paso"] == STEP_MESSAGE


def test_teclas_1_y_2_eligen_el_modo(isolated_app_dirs):
    def script(app, out):
        app.wizard.steps[0].ctx.template = MessageTemplate("Aviso", "Hola")
        app.go_to(STEP_MODE)
        app.focus_force()
        app.update()
        app.event_generate("2")
        app.update()
        out["modo2"] = app.current_view().presenter.selected
        app.event_generate("1")
        app.update()
        out["modo1"] = app.current_view().presenter.selected

    out = drive(script)
    assert out["modo2"] is SendMode.ALL_AT_ONCE_BCC and out["modo1"] is SendMode.ONE_BY_ONE
