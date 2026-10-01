"""Base de presenters: lógica de cada paso del asistente sin depender de Tk
(contracts/wizard-ui.md). Las vistas solo dibujan el estado y reenvían eventos.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from envio_correos.core.journal import Journal
    from envio_correos.core.providers.base import SendProvider


# Índices de los pasos del asistente (orden de main_window.STEPS).
STEP_START, STEP_ACCOUNT, STEP_RECIPIENTS, STEP_MESSAGE = 0, 1, 2, 3
STEP_MODE, STEP_REVIEW, STEP_SENDING, STEP_RESULT = 4, 5, 6, 7


@dataclass
class Guard:
    """Resultado de "¿puedo avanzar?": si no, `reason` explica por qué (FR-003).

    Si `confirm` está definido, no es un bloqueo sino una pregunta: la vista muestra `reason`
    como confirmación y, si la usuaria acepta, llama a `confirm()` y vuelve a intentar avanzar
    (asunto vacío, confirmación final de envío — FR-052)."""

    ok: bool
    reason: str | None = None
    confirm: Callable[[], None] | None = None

    @classmethod
    def allow(cls) -> Guard:
        return cls(True)

    @classmethod
    def deny(cls, reason: str) -> Guard:
        return cls(False, reason)

    @classmethod
    def ask(cls, question: str, on_yes: Callable[[], None]) -> Guard:
        return cls(False, question, on_yes)


@dataclass
class WizardContext:
    """Estado compartido entre pasos. Lo que se ingresa en un paso sobrevive al volver atrás
    (FR-001): cada presenter lee y escribe acá, no en sus widgets."""

    journal: Journal | None = None
    provider: SendProvider | None = None
    account_email: str = ""
    display_name: str = ""
    recipients: Any = None  # RecipientList
    template: Any = None  # MessageTemplate
    mode: Any = None  # SendMode
    campaign_id: str | None = None
    attempt_number: int | None = None
    retry_source: Any = None  # contexto de reintento (US3)
    extras: dict[str, Any] = field(default_factory=dict)


class StepPresenter:
    """Contrato de un paso. Subclases sobrescriben lo que necesiten."""

    title: str = ""
    allows_back: bool = True

    def __init__(self, ctx: WizardContext):
        self.ctx = ctx

    def on_enter(self) -> None:  # noqa: B027 - gancho opcional
        pass

    def on_leave(self) -> None:  # noqa: B027 - gancho opcional
        pass

    def can_advance(self) -> Guard:
        return Guard.allow()

    def next_step(self) -> int | None:
        """Índice del paso siguiente si no es el inmediato (p. ej. al reanudar un envío)."""
        return None


class Wizard:
    """Navegación secuencial con guardas. Pura: la vista llama next()/back() y redibuja."""

    def __init__(self, steps: list[StepPresenter]):
        if not steps:
            raise ValueError("el asistente necesita al menos un paso")
        self.steps = steps
        self.index = 0
        self.steps[0].on_enter()

    @property
    def current(self) -> StepPresenter:
        return self.steps[self.index]

    @property
    def can_go_back(self) -> bool:
        return self.index > 0 and self.current.allows_back

    @property
    def is_last(self) -> bool:
        return self.index == len(self.steps) - 1

    def next(self) -> Guard:
        guard = self.current.can_advance()
        if not guard.ok or self.is_last:
            return guard
        target = self.current.next_step()
        self.current.on_leave()
        self.index = target if target is not None else self.index + 1
        self.current.on_enter()
        return guard

    def back(self) -> bool:
        if not self.can_go_back:
            return False
        self.current.on_leave()
        self.index -= 1
        self.current.on_enter()
        return True

    def go_to(self, index: int) -> None:
        """Salto explícito (p. ej. "Nuevo envío" o "Corregir y reintentar")."""
        if not 0 <= index < len(self.steps):
            raise IndexError(index)
        self.current.on_leave()
        self.index = index
        self.current.on_enter()
