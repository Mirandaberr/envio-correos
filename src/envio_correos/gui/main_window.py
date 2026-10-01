"""Arma el asistente (presenters + vistas) y lanza la ventana."""

from __future__ import annotations

from envio_correos.core.journal import Journal
from envio_correos.gui.app import App
from envio_correos.gui.presenters.account import AccountPresenter
from envio_correos.gui.presenters.base import Wizard, WizardContext
from envio_correos.gui.presenters.message import MessagePresenter
from envio_correos.gui.presenters.mode import ModePresenter
from envio_correos.gui.presenters.recipients import RecipientsPresenter
from envio_correos.gui.presenters.result import ResultPresenter
from envio_correos.gui.presenters.review import ReviewPresenter
from envio_correos.gui.presenters.sending import SendingPresenter
from envio_correos.gui.presenters.start import StartPresenter
from envio_correos.gui.steps.account import AccountView
from envio_correos.gui.steps.message import MessageView
from envio_correos.gui.steps.mode import ModeView
from envio_correos.gui.steps.recipients import RecipientsView
from envio_correos.gui.steps.result import ResultView
from envio_correos.gui.steps.review import ReviewView
from envio_correos.gui.steps.sending import SendingView
from envio_correos.gui.steps.start import StartView

# (presenter, vista) en orden. El índice 0 es la pantalla de inicio (sin número de paso).
STEPS = (
    (StartPresenter, StartView),
    (AccountPresenter, AccountView),
    (RecipientsPresenter, RecipientsView),
    (MessagePresenter, MessageView),
    (ModePresenter, ModeView),
    (ReviewPresenter, ReviewView),
    (SendingPresenter, SendingView),
    (ResultPresenter, ResultView),
)


def build(journal: Journal) -> App:
    ctx = WizardContext(journal=journal)
    presenters = [presenter_cls(ctx) for presenter_cls, _ in STEPS]
    return App(Wizard(presenters), [view for _, view in STEPS], first_numbered=1)


def run(journal: Journal, argv: list[str]) -> int:
    app = build(journal)
    app.mainloop()
    return 0
