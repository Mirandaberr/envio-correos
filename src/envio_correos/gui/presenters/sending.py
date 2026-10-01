"""Paso 6 — Envío en curso (FR-053)."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from envio_correos.core import attachments
from envio_correos.core.engine import DAILY_LIMIT, CampaignRunner, Finished, Paused, Progress
from envio_correos.core.journal import AttemptState
from envio_correos.core.message_builder import MessageBuilder
from envio_correos.core.template import TemplateRenderer
from envio_correos.gui.presenters.base import Guard, StepPresenter, WizardContext
from envio_correos.gui.presenters.review import format_duration
from envio_correos.texts import es

log = logging.getLogger(__name__)

RunnerFactory = Callable[..., CampaignRunner]


class SendingPresenter(StepPresenter):
    title = "Enviando…"
    allows_back = False

    def __init__(self, ctx: WizardContext, runner_factory: RunnerFactory = CampaignRunner):
        super().__init__(ctx)
        self._runner_factory = runner_factory
        self.runner: CampaignRunner | None = None
        self.progress: Progress | None = None
        self.paused: Paused | None = None
        self.finished: Finished | None = None
        self.start_error: str | None = None
        self._attempt: tuple[str | None, int | None] = (None, None)

    def on_enter(self) -> None:
        """Cada intento (campaña nueva o reintento) empieza con el estado limpio."""
        current = (self.ctx.campaign_id, self.ctx.attempt_number)
        if current != self._attempt:
            self._attempt = current
            self.runner = None
            self.progress = self.paused = self.finished = None

    @property
    def needs_start(self) -> bool:
        return self.runner is None and self.start_error is None

    def builder(self) -> MessageBuilder:
        ctx = self.ctx
        assert ctx.template and ctx.mode and ctx.journal and ctx.campaign_id
        # Al reanudar no hay lista en memoria: los encabezados salen del intento guardado.
        headers = (
            ctx.recipients.headers
            if ctx.recipients is not None
            else ctx.journal.attempt_headers(ctx.campaign_id, ctx.attempt_number or 1)
        )
        return MessageBuilder(
            template=ctx.template,
            headers=headers,
            sender_email=ctx.account_email,
            display_name=ctx.display_name,
            attachments=attachments.load_for_attempt(ctx.template.attachments),
            render=TemplateRenderer(headers),
            mode=ctx.mode,
        )

    def start(self, on_event: Callable[[object], None]) -> None:
        """Arranca (o reanuda tras una pausa) el envío en un hilo."""
        ctx = self.ctx
        assert ctx.provider and ctx.journal and ctx.campaign_id and ctx.attempt_number
        self.paused = self.finished = None
        self.start_error = None
        try:
            builder = self.builder()
        except OSError as exc:
            name = Path(getattr(exc, "filename", "") or "").name or "un adjunto"
            self.start_error = (
                f"No se pudo leer el adjunto «{name}». Revisá que siga en su carpeta y volvé a "
                "intentar; los correos pendientes no se perdieron."
            )
            log.warning("No se pudo iniciar el envío: falta un adjunto")
            return
        self.runner = self._runner_factory(
            provider=ctx.provider,
            journal=ctx.journal,
            campaign_id=ctx.campaign_id,
            attempt_number=ctx.attempt_number,
            builder=builder,
            on_event=on_event,
        )
        self.runner.start()

    @property
    def running(self) -> bool:
        return self.runner is not None and self.runner.is_alive()

    def stop(self) -> None:
        if self.runner is not None:
            self.runner.stop()

    def apply(self, event: object) -> None:
        if isinstance(event, Progress):
            self.progress = event
        elif isinstance(event, Paused):
            self.paused = event
        elif isinstance(event, Finished):
            self.finished = event

    # --- Textos ---

    def progress_fraction(self) -> float:
        p = self.progress
        if not p or not p.total:
            return 0.0
        return (p.total - p.pending) / p.total

    def progress_text(self) -> str:
        p = self.progress
        if not p:
            return "Preparando el envío…"
        return (
            f"Enviados {p.sent} · Fallidos {p.failed} · Restantes {p.pending} · "
            f"Tiempo restante: {format_duration(p.eta_s)}"
        )

    def paused_text(self) -> str | None:
        if self.start_error:
            return self.start_error
        if not self.paused:
            return None
        if self.paused.reason == DAILY_LIMIT:
            return es.DAILY_LIMIT_REACHED
        return (
            es.reason_text(self.paused.reason, self.paused.smtp_code)
            + "\n\nEl envío quedó en pausa. Los correos que faltan siguen pendientes."
        )

    @property
    def done(self) -> bool:
        return self.finished is not None and self.finished.state in (
            AttemptState.DONE,
            AttemptState.STOPPED,
        )

    def can_advance(self) -> Guard:
        if self.running:
            return Guard.deny("El envío está en curso. Esperá a que termine o detenelo.")
        if self.paused and not self.finished:
            return Guard.allow()  # puede ir al resultado con pendientes
        return Guard.allow() if self.done else Guard.deny("El envío todavía no empezó.")
