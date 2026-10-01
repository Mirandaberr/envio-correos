"""Pantalla de inicio (contracts/wizard-ui.md, paso 0)."""

from __future__ import annotations

import logging
from pathlib import Path

from envio_correos.core import report
from envio_correos.core.journal import UnfinishedAttempt, attempt_code
from envio_correos.core.message_builder import AttachmentRef, MessageTemplate, SendMode
from envio_correos.gui.presenters.base import StepPresenter

log = logging.getLogger(__name__)


class StartPresenter(StepPresenter):
    title = "Envío de correos"
    allows_back = False

    def clear_history(self) -> int:
        assert self.ctx.journal is not None
        n = self.ctx.journal.delete_all()
        log.info("Historial borrado por la usuaria: %d campañas", n)
        return n

    # --- Envío sin terminar (US7) ---

    def unfinished(self) -> UnfinishedAttempt | None:
        assert self.ctx.journal is not None
        items = self.ctx.journal.unfinished_attempts()
        return items[0] if items else None

    def unfinished_text(self, u: UnfinishedAttempt) -> str:
        code = attempt_code(u.campaign_id, u.number)
        text = f"Hay un envío sin terminar (campaña {code}): faltan {u.pending} correos."
        if u.unknown:
            text += (
                f" Además, {u.unknown} dirección(es) quedaron a mitad del envío y no se sabe si "
                "recibieron el correo."
            )
        return text

    def prepare_resume(self, u: UnfinishedAttempt, resend_unknown: bool) -> None:
        ctx = self.ctx
        assert ctx.journal is not None
        if resend_unknown:
            ctx.journal.requeue_unknown(u.campaign_id, u.number)
        stored = ctx.journal.get_campaign(u.campaign_id)
        assert stored is not None
        spec = stored.spec
        ctx.campaign_id, ctx.attempt_number = u.campaign_id, u.number
        ctx.template = MessageTemplate(
            spec.subject, spec.body, tuple(AttachmentRef.from_dict(a) for a in spec.attachments)
        )
        ctx.mode = SendMode(spec.mode)
        ctx.recipients = None
        ctx.extras["resume"] = True
        log.info("Reanudando el intento %s", attempt_code(u.campaign_id, u.number))

    def discard(self, u: UnfinishedAttempt) -> Path | None:
        assert self.ctx.journal is not None
        self.ctx.journal.discard_attempt(u.campaign_id, u.number)
        log.info("Intento %s descartado", attempt_code(u.campaign_id, u.number))
        return report.write_report(self.ctx.journal, u.campaign_id, u.number)
