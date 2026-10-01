"""Paso 5 — Revisión y confirmación (FR-050, FR-052, FR-054)."""

from __future__ import annotations

import logging
import math
from pathlib import Path

from envio_correos.core import attachments
from envio_correos.core.journal import CampaignSpec
from envio_correos.core.message_builder import MessageBuilder, SendMode
from envio_correos.core.providers.base import ProviderError
from envio_correos.core.template import TemplateRenderer, empty_values
from envio_correos.gui.presenters.base import Guard, StepPresenter, WizardContext
from envio_correos.texts import es

log = logging.getLogger(__name__)

MODE_LABEL = {
    SendMode.ONE_BY_ONE: "Uno por uno",
    SendMode.ALL_AT_ONCE_BCC: "Todos a la vez (copia oculta)",
    SendMode.ALL_AT_ONCE_VISIBLE: "Todos a la vez (destinatarios visibles)",
}


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return "menos de un minuto"
    minutes = math.ceil(seconds / 60)
    if minutes < 60:
        return f"{minutes} minuto{'s' if minutes != 1 else ''}"
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if m else f"{h} h"


class ReviewPresenter(StepPresenter):
    title = "Revisá antes de enviar"

    def __init__(self, ctx: WizardContext):
        super().__init__(ctx)
        self._confirmed = False

    def on_enter(self) -> None:
        self._confirmed = False

    # --- Datos para mostrar ---

    @property
    def recipient_count(self) -> int:
        return self.ctx.recipients.counts().effective if self.ctx.recipients else 0

    @property
    def message_count(self) -> int:
        n = self.recipient_count
        if self.ctx.mode is not None and self.ctx.mode.is_batch and self.ctx.provider:
            per = self.ctx.provider.limits.max_recipients_per_message
            return math.ceil(n / per)
        return n

    def estimated_seconds(self) -> float:
        if not self.ctx.provider:
            return 0.0
        return max(self.message_count - 1, 0) * self.ctx.provider.limits.min_interval_s

    def daily_warning(self) -> str | None:
        if not (self.ctx.provider and self.ctx.journal):
            return None
        limit = self.ctx.provider.limits.recipients_per_24h
        sent = self.ctx.journal.sent_last_24h(self.ctx.account_email)
        available = max(limit - sent, 0)
        if self.recipient_count <= available:
            return None
        return es.DAILY_LIMIT_WARNING.format(limit=limit, sent=sent, today=available)

    def summary(self) -> list[tuple[str, str]]:
        t = self.ctx.template
        return [
            ("Remitente", f"{self.ctx.display_name} <{self.ctx.account_email}>".strip()),
            ("Destinatarios", str(self.recipient_count)),
            ("Forma de envío", MODE_LABEL.get(self.ctx.mode, "")),
            ("Asunto", t.subject if t else ""),
            ("Adjuntos", str(len(t.attachments)) if t else "0"),
            ("Tiempo estimado", format_duration(self.estimated_seconds())),
        ]

    def confirmation_text(self) -> str:
        n, mode = self.recipient_count, MODE_LABEL.get(self.ctx.mode, "")
        batch = ""
        if self.ctx.mode is not None and self.ctx.mode.is_batch:
            m = self.message_count
            batch = f"Se enviarán {m} correo{'s' if m != 1 else ''} con hasta " + (
                f"{self.ctx.provider.limits.max_recipients_per_message} destinatarios cada uno. "
                if self.ctx.provider
                else ""
            )
        text = (
            f"Se enviará el correo a {n} destinatario{'s' if n != 1 else ''} ({mode}). {batch}"
            f"Tiempo estimado: {format_duration(self.estimated_seconds())}.\n\n"
            "Una vez iniciado, el envío no se puede deshacer. ¿Enviar ahora?"
        )
        warning = self.daily_warning()
        return f"{warning}\n\n{text}" if warning else text

    # --- Vista previa (FR-050) y prueba (FR-051) ---

    @property
    def preview_count(self) -> int:
        return self.recipient_count

    def _builder(self, with_attachments: bool = False) -> MessageBuilder:
        ctx = self.ctx
        assert ctx.template and ctx.recipients and ctx.mode
        headers = ctx.recipients.headers
        return MessageBuilder(
            template=ctx.template,
            headers=headers,
            sender_email=ctx.account_email,
            display_name=ctx.display_name,
            attachments=attachments.load_for_attempt(ctx.template.attachments)
            if with_attachments
            else (),
            render=TemplateRenderer(headers),
            mode=ctx.mode,
        )

    def preview(self, k: int) -> dict[str, str]:
        lst = self.ctx.recipients
        assert lst is not None and self.ctx.mode is not None and self.ctx.template is not None
        i = lst.effective_indices()[k]
        address = lst.address(i) or ""
        if self.ctx.mode.is_batch:
            m = self._builder().for_batch([address])
            to = (
                f"{self.ctx.account_email} (los destinatarios van en copia oculta)"
                if self.ctx.mode is SendMode.ALL_AT_ONCE_BCC
                else "Todos los destinatarios (visibles entre sí)"
            )
        else:
            m = self._builder().for_recipient(address, lst.rows[i])
            to = address
        names = ", ".join(Path(a.path).name for a in self.ctx.template.attachments)
        return {"to": to, "subject": m.subject, "body": m.body, "attachments": names}

    def empty_values_warning(self) -> str | None:
        lst, t = self.ctx.recipients, self.ctx.template
        if lst is None or t is None or (self.ctx.mode and self.ctx.mode.is_batch):
            return None
        idx = lst.effective_indices()
        per_var = empty_values(t.subject + "\n" + t.body, lst.headers, lst.rows, idx)
        parts = []
        for var, rows in per_var.items():
            excel_rows = ", ".join(str(lst.source_row_numbers[i]) for i in rows[:10])
            more = "…" if len(rows) > 10 else ""
            parts.append(
                f"{len(rows)} destinatario{'s' if len(rows) != 1 else ''} tienen "
                f"{{{var}}} vacío (filas {excel_rows}{more})."
            )
        return " ".join(parts) or None

    def send_test(self) -> str | None:
        """Bloqueante. Envía la primera fila personalizada a la propia cuenta, sin registrarla
        en la campaña. Devuelve un error para la usuaria o None."""
        ctx = self.ctx
        assert ctx.provider and ctx.recipients
        i = ctx.recipients.effective_indices()[0]
        message = self._builder(with_attachments=True).for_recipient(
            ctx.account_email, ctx.recipients.rows[i]
        )
        try:
            outcome = ctx.provider.send(message)
        except ProviderError as exc:
            return es.reason_text(exc.failure.code, exc.failure.smtp_code)
        finally:
            ctx.provider.close()
        if outcome.rejected:
            f = next(iter(outcome.rejected.values()))
            return es.reason_text(f.code, f.smtp_code)
        log.info("Correo de prueba enviado a la propia cuenta")
        return None

    # --- Creación de la campaña ---

    def create_campaign(self) -> None:
        ctx = self.ctx
        assert ctx.journal and ctx.recipients and ctx.template and ctx.mode
        lst, t = ctx.recipients, ctx.template
        spec = CampaignSpec(
            account_email=ctx.account_email,
            source_path=lst.source_path,
            sheet_name=lst.sheet_name,
            headers=lst.headers,
            email_col=lst.email_col,
            subject=t.subject,
            body=t.body,
            attachments=tuple(a.to_dict() for a in t.attachments),
            mode=str(ctx.mode),
        )
        cid = (
            ctx.retry_source.campaign_id if ctx.retry_source else None
        ) or ctx.journal.create_campaign(spec)
        ctx.campaign_id = cid
        ctx.attempt_number = ctx.journal.start_attempt(cid, lst.to_attempt_rows(), lst.headers)
        log.info(
            "Campaña %s creada: intento %d, %d destinatarios",
            cid,
            ctx.attempt_number,
            self.recipient_count,
        )
        self._confirmed = True

    def can_advance(self) -> Guard:
        if self._confirmed:
            return Guard.allow()
        return Guard.ask(self.confirmation_text(), self.create_campaign)
