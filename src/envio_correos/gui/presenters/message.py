"""Paso 3 — Mensaje (FR-030..033): texto, variables por columna y adjuntos."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from envio_correos import config
from envio_correos.core import attachments
from envio_correos.core.message_builder import AttachmentRef, MessageTemplate
from envio_correos.core.template import unknown_variables
from envio_correos.gui.presenters.base import Guard, StepPresenter, WizardContext

log = logging.getLogger(__name__)


def load_draft(path: Path | None = None) -> MessageTemplate | None:
    path = path or config.draft_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return MessageTemplate(
            str(data.get("subject", "")),
            str(data.get("body", "")),
            tuple(AttachmentRef.from_dict(a) for a in data.get("attachments", [])),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_draft(template: MessageTemplate, path: Path | None = None) -> None:
    path = path or config.draft_path()
    data = {
        "subject": template.subject,
        "body": template.body,
        "attachments": [a.to_dict() for a in template.attachments],
    }
    try:
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        log.warning("No se pudo guardar el borrador: %s", type(exc).__name__)


class MessagePresenter(StepPresenter):
    title = "Escribí el correo"

    def __init__(self, ctx: WizardContext, draft_path: Path | None = None):
        super().__init__(ctx)
        self._draft_path = draft_path
        self.subject = ""
        self.body = ""
        self.attachments: list[AttachmentRef] = []
        self._empty_subject_ok = False
        self._loaded = False

    def on_enter(self) -> None:
        if self.ctx.template is not None:
            t = self.ctx.template
        elif not self._loaded:
            t = load_draft(self._draft_path) or MessageTemplate("", "")
        else:
            return
        self._loaded = True
        self.subject, self.body, self.attachments = t.subject, t.body, list(t.attachments)

    def set_text(self, subject: str, body: str) -> None:
        if subject != self.subject:
            self._empty_subject_ok = False
        self.subject, self.body = subject, body

    # --- Variables (FR-031) ---

    def variables(self) -> tuple[str, ...]:
        lst = self.ctx.recipients
        return lst.variable_columns() if lst is not None else ()

    @staticmethod
    def token(column: str) -> str:
        return "{" + column + "}"

    def unknown(self) -> list[str]:
        headers = self.variables()
        seen = unknown_variables(self.subject, headers)
        return seen + [v for v in unknown_variables(self.body, headers) if v not in seen]

    # --- Adjuntos (FR-032) ---

    def add_files(self, paths) -> list[str]:
        """Agrega adjuntos. Devuelve mensajes de error de los que no se pudieron leer."""
        errors = []
        for path in paths:
            path = Path(path)
            try:
                self.attachments.append(attachments.make_ref(path))
            except OSError:
                errors.append(
                    f"No se pudo leer «{path.name}». Revisá que exista y no esté abierto."
                )
        return errors

    def remove_attachment(self, index: int) -> None:
        del self.attachments[index]

    def attachments_summary(self) -> str:
        if not self.attachments:
            return "Sin adjuntos."
        total = attachments.human_size(attachments.total_size(self.attachments))
        return f"{len(self.attachments)} adjunto(s), {total} en total."

    def attachment_warning(self) -> str | None:
        """Adjuntos que ya no están o cambiaron (borrador restaurado o reintento, US3-AS5)."""
        problems = attachments.problems(self.attachments)
        if not problems:
            return None
        lines = [
            f"• {Path(p.ref.path).name}: "
            + ("ya no está en su carpeta" if p.kind == "missing" else "cambió desde que se eligió")
            for p in problems
        ]
        return "Revisá los adjuntos:\n" + "\n".join(lines)

    def template(self) -> MessageTemplate:
        return MessageTemplate(self.subject, self.body, tuple(self.attachments))

    def on_leave(self) -> None:
        self.ctx.template = self.template()
        save_draft(self.ctx.template, self._draft_path)

    def can_advance(self) -> Guard:
        if not self.body.strip():
            return Guard.deny("Escribí el texto del correo.")
        if unknown := self.unknown():
            names = ", ".join(self.token(v) for v in unknown)
            return Guard.deny(
                f"Estos datos no existen como columna en el Excel: {names}. "
                "Usá los botones de columnas para insertarlos."
            )
        if error := attachments.size_error(self.attachments):
            return Guard.deny(error)
        missing = [p for p in attachments.problems(self.attachments) if p.kind == "missing"]
        if missing:
            names = ", ".join(Path(p.ref.path).name for p in missing)
            return Guard.deny(f"No se encuentra el adjunto {names}. Quitalo o volvé a elegirlo.")
        if not self.subject.strip() and not self._empty_subject_ok:

            def accept() -> None:
                self._empty_subject_ok = True

            return Guard.ask("El correo no tiene asunto. ¿Querés continuar igual?", accept)
        return Guard.allow()
