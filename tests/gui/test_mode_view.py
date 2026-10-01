"""Vista Modo: dos tarjetas distintas y casilla de privacidad (US4, FR-040, FR-041)."""

import pytest

from envio_correos.core.journal import Journal
from envio_correos.core.message_builder import MessageTemplate, SendMode
from envio_correos.gui import main_window
from envio_correos.gui.presenters.base import STEP_MODE

pytestmark = pytest.mark.slow


def test_tarjetas_y_casilla(isolated_app_dirs):
    journal = Journal()
    app = main_window.build(journal)
    result = {}

    def script():
        try:
            app.wizard.steps[0].ctx.template = MessageTemplate("Aviso", "Hola")
            app.go_to(STEP_MODE)
            v = app.current_view()
            app.update()
            result["casilla_inicial"] = v.show_check.winfo_ismapped()
            v._select(SendMode.ALL_AT_ONCE_BCC)
            app.update()
            result["casilla_batch"] = v.show_check.winfo_ismapped()
            v.show_var.set(True)
            v._toggle_show()
            result["modo_visible"] = v.presenter.selected
            v._select(SendMode.ONE_BY_ONE)
            app.update()
            result["casilla_uno"] = v.show_check.winfo_ismapped()
            result["bordes"] = {m: int(c.cget("border_width")) for m, c in v.cards.items()}
        finally:
            app.after(20, app.destroy)

    app.after(100, script)
    app.mainloop()
    journal.close()
    assert result["casilla_inicial"] == 0 and result["casilla_batch"] == 1
    assert result["modo_visible"] is SendMode.ALL_AT_ONCE_VISIBLE
    assert result["casilla_uno"] == 0
    assert result["bordes"] == {SendMode.ONE_BY_ONE: 6, SendMode.ALL_AT_ONCE_BCC: 3}
