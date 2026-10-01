"""Paso 4 — Modo de envío (FR-040, FR-041, FR-042)."""

from __future__ import annotations

from envio_correos.core.message_builder import SendMode
from envio_correos.core.template import find_variables
from envio_correos.gui.presenters.base import Guard, StepPresenter, WizardContext

PRIVACY_WARNING = (
    "Atención, privacidad: todos los destinatarios van a ver las direcciones de correo de los "
    "demás. ¿Querés continuar así?"
)


class ModePresenter(StepPresenter):
    title = "¿Cómo querés enviarlo?"
    available: tuple[SendMode, ...] = (
        SendMode.ONE_BY_ONE,
        SendMode.ALL_AT_ONCE_BCC,
        SendMode.ALL_AT_ONCE_VISIBLE,
    )

    def __init__(self, ctx: WizardContext):
        super().__init__(ctx)
        self._privacy_ok = False

    @property
    def selected(self) -> SendMode | None:
        return self.ctx.mode

    def select(self, mode: SendMode) -> None:
        if mode not in self.available:
            raise ValueError(mode)
        if mode is not SendMode.ALL_AT_ONCE_VISIBLE:
            self._privacy_ok = False
        self.ctx.mode = mode

    @property
    def show_recipients(self) -> bool:
        return self.ctx.mode is SendMode.ALL_AT_ONCE_VISIBLE

    def set_show_recipients(self, show: bool) -> None:
        self.select(SendMode.ALL_AT_ONCE_VISIBLE if show else SendMode.ALL_AT_ONCE_BCC)

    def variables_in_message(self) -> list[str]:
        t = self.ctx.template
        if t is None:
            return []
        return find_variables(t.subject) + [
            v for v in find_variables(t.body) if v not in find_variables(t.subject)
        ]

    def can_advance(self) -> Guard:
        mode = self.ctx.mode
        if mode is None:
            return Guard.deny("Elegí una de las dos formas de envío.")
        if mode.is_batch and (variables := self.variables_in_message()):
            names = ", ".join("{" + v + "}" for v in variables)
            return Guard.deny(
                f"En «Todos a la vez» todos reciben el mismo texto, así que no se pueden usar "
                f"datos personalizados ({names}). Quitalos del mensaje o elegí «Uno por uno»."
            )
        if mode is SendMode.ALL_AT_ONCE_VISIBLE and not self._privacy_ok:

            def accept() -> None:
                self._privacy_ok = True

            return Guard.ask(PRIVACY_WARNING, accept)
        return Guard.allow()
