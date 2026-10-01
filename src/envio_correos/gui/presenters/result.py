"""Paso 7 — Resultado (FR-060, FR-062). Reporte y reintento se agregan en US2/US3."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from envio_correos import config
from envio_correos.core import report
from envio_correos.core.journal import RecipientState, attempt_code
from envio_correos.core.recipients import EXCLUDED_BY_USER
from envio_correos.gui.presenters.base import StepPresenter, WizardContext
from envio_correos.texts import es


class ResultPresenter(StepPresenter):
    title = "Resultado del envío"
    allows_back = False

    def __init__(self, ctx: WizardContext):
        super().__init__(ctx)
        self.report_path: Path | None = None
        self._report_done = False
        self._report_skipped = False

    def on_enter(self) -> None:
        self.report_path, self._report_done, self._report_skipped = None, False, False

    # --- Excel de fallidos (FR-061) ---

    @property
    def report_pending(self) -> bool:
        return not self._report_done

    def generate_report(self, target: Path | None = None) -> Path | None:
        """Genera el reporte. Lanza report.ReportWriteError si la ubicación está bloqueada;
        la vista ofrece entonces "Guardar como" y vuelve a llamar con `target`."""
        ctx = self.ctx
        assert ctx.journal and ctx.campaign_id and ctx.attempt_number
        self.report_path = report.write_report(
            ctx.journal, ctx.campaign_id, ctx.attempt_number, target=target
        )
        self._report_done = True
        return self.report_path

    def skip_report(self) -> None:
        self._report_done = self._report_skipped = True

    def report_text(self) -> str:
        if self._report_skipped:
            return "No se guardó el Excel de fallidos (se canceló la elección de carpeta)."
        if self.report_path:
            return f"Las direcciones a corregir quedaron en: {self.report_path.name}"
        return "No hubo fallos: no hace falta corregir nada."

    @property
    def code(self) -> str:
        assert self.ctx.campaign_id and self.ctx.attempt_number
        return attempt_code(self.ctx.campaign_id, self.ctx.attempt_number)

    def breakdown(self) -> dict[str, int]:
        ctx = self.ctx
        assert ctx.journal and ctx.campaign_id and ctx.attempt_number
        rows = ctx.journal.recipients(ctx.campaign_id, ctx.attempt_number)
        c = Counter(r.state for r in rows)
        excluded = sum(1 for r in rows if r.reason_code == EXCLUDED_BY_USER)
        return {
            "Enviados": c[RecipientState.SENT],
            "Fallidos": c[RecipientState.FAILED],
            "Pendientes": c[RecipientState.PENDING] + c[RecipientState.SENDING],
            "Omitidos": c[RecipientState.SKIPPED] - excluded,
            "Excluidos por vos": excluded,
        }

    def notice(self) -> str:
        return es.LATE_BOUNCES_NOTICE

    def logs_dir(self):
        return config.log_dir()

    def reset_for_new_campaign(self) -> None:
        ctx = self.ctx
        if ctx.recipients is not None:
            ctx.recipients.release_caches()
        ctx.recipients = ctx.template = ctx.mode = None
        ctx.campaign_id = ctx.attempt_number = None
        ctx.retry_source = None
        ctx.extras.pop("resume", None)
