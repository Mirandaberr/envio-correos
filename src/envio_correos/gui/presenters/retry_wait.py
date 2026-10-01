"""Corregir y reintentar (US3, FR-063, contracts/wizard-ui.md "Paso 7")."""

from __future__ import annotations

import logging
from pathlib import Path

from envio_correos.core import retry
from envio_correos.core.excel_reader import ExcelReadError
from envio_correos.gui.presenters.base import WizardContext

log = logging.getLogger(__name__)

INSTRUCTIONS = (
    "Se abrió el Excel con las direcciones a corregir.\n\n"
    "1. Corregí las direcciones que tengan errores (por ejemplo, un dominio mal escrito).\n"
    "2. Si no querés reintentar alguna fila, borrala.\n"
    "3. Guardá el archivo y cerralo.\n\n"
    "Después pulsá «Continuar»."
)


class RetryWaitPresenter:
    """Carga el Excel de fallidos (posiblemente editado) y prepara el contexto del asistente
    para el reintento: lista, mensaje y modo de la campaña original."""

    def __init__(self, ctx: WizardContext):
        self.ctx = ctx

    def load(self, path: Path) -> str | None:
        """Bloqueante (se llama en un hilo). Devuelve un error para la usuaria o None."""
        assert self.ctx.journal is not None
        try:
            loaded = retry.load_retry(path, self.ctx.journal)
        except ExcelReadError as exc:
            return exc.user_message
        self.apply(loaded)
        return None

    def apply(self, loaded: retry.RetryLoad) -> None:
        ctx = self.ctx
        if ctx.recipients is not None:
            ctx.recipients.release_caches()
        ctx.recipients = loaded.recipients
        ctx.retry_source = loaded
        ctx.campaign_id = ctx.attempt_number = None
        if loaded.template is not None:
            ctx.template = loaded.template
            ctx.mode = loaded.mode
        else:
            ctx.template = ctx.mode = None
