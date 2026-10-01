"""Paso 2 — Destinatarios (FR-020..026)."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from envio_correos import config
from envio_correos.core import excel_reader
from envio_correos.core.domain_check import DomainChecker, DomainStatus
from envio_correos.core.excel_reader import ExcelReadError
from envio_correos.core.recipients import INVALID, MARKABLE, RecipientList
from envio_correos.core.recipients import ValidationStatus as V
from envio_correos.gui.presenters.base import Guard, StepPresenter, WizardContext
from envio_correos.texts import es

log = logging.getLogger(__name__)


class StatusFilter(Enum):
    ALL = "Todos"
    VALID = "Se envían"
    INVALID = "Inválidos"
    DUPLICATE = "Duplicados"
    EXCLUDED = "Excluidos"


class RecipientsPresenter(StepPresenter):
    title = "Elegí a quién enviar"

    def __init__(
        self, ctx: WizardContext, checker_factory: Callable[[], DomainChecker] | None = None
    ):
        super().__init__(ctx)
        self.path: Path | None = None
        self.sheets: list[str] = []
        self.query = ""
        self.status_filter = StatusFilter.ALL
        self.visible: list[int] = []
        self.checking_domains = False
        self.domain_progress = (0, 0)
        self.domain_notice: str | None = None
        self._checker_factory = checker_factory
        self._cancel_check = threading.Event()

    @property
    def lst(self) -> RecipientList | None:
        return self.ctx.recipients

    def on_enter(self) -> None:
        """Si la lista llegó desde otro lado (reintento), sincroniza archivo y hojas."""
        lst, src = self.lst, self.ctx.retry_source
        if lst is not None and (self.path is None or str(self.path) != lst.source_path):
            self.path = Path(lst.source_path)
            self.sheets = list(src.sheets) if src is not None else [lst.sheet_name]
            self.query, self.status_filter, self.domain_notice = "", StatusFilter.ALL, None
            self.refresh_visible()

    # --- Carga (bloqueante: se llama desde un hilo de trabajo) ---

    def load(self, path: Path, sheet: str | None = None, already_sent=()) -> str | None:
        """Devuelve un mensaje de error para la usuaria o None si cargó bien."""
        self._cancel_check.set()
        try:
            sheets = [
                s for s in excel_reader.list_sheets(path) if s != config.REPORT_META_SHEET_NAME
            ]
            data = excel_reader.read_sheet(path, sheet)
        except ExcelReadError as exc:
            return exc.user_message
        if self.lst is not None:
            self.lst.release_caches()
        self.path, self.sheets = Path(path), sheets
        self.ctx.recipients = RecipientList.from_sheet(data, str(path), already_sent=already_sent)
        self.query, self.status_filter = "", StatusFilter.ALL
        self.domain_notice = None
        self.refresh_visible()
        return None

    def set_email_column(self, col: int) -> None:
        if self.lst is not None:
            self.lst.set_email_column(col)
            self.refresh_visible()

    # --- Verificación de dominios (FR-026) ---

    def check_domains(self, progress: Callable[[int, int], None]) -> int:
        """Bloqueante. Devuelve cuántas filas quedaron inválidas por dominio."""
        lst = self.lst
        if lst is None:
            return 0
        self._cancel_check = threading.Event()
        self.checking_domains = True
        try:
            factory = self._checker_factory or DomainChecker  # se resuelve al usarse
            results = factory().check_all(
                lst.domains(), progress=progress, cancel=self._cancel_check
            )
        finally:
            self.checking_domains = False
        if self._cancel_check.is_set() or lst is not self.lst:
            return 0
        invalid = {d for d, s in results.items() if s is DomainStatus.NOT_FOUND}
        skipped = any(s is DomainStatus.SKIPPED for s in results.values())
        self.domain_notice = es.DOMAIN_CHECK_SKIPPED if skipped else None
        changed = lst.apply_invalid_domains(invalid)
        self.refresh_visible()
        return changed

    # --- Búsqueda, filtro y selección (FR-024, FR-025) ---

    def set_query(self, query: str) -> None:
        self.query = query
        self.refresh_visible()

    def set_filter(self, f: StatusFilter) -> None:
        self.status_filter = f
        self.refresh_visible()

    def _passes_filter(self, i: int) -> bool:
        lst, f = self.lst, self.status_filter
        assert lst is not None
        st = lst.status[i]
        if f is StatusFilter.ALL:
            return True
        if f is StatusFilter.VALID:
            return st in MARKABLE and lst.selected[i] == 1
        if f is StatusFilter.INVALID:
            return st in INVALID
        if f is StatusFilter.DUPLICATE:
            return st == V.DUPLICATE
        return st in MARKABLE and lst.selected[i] == 0

    def refresh_visible(self) -> None:
        if self.lst is None:
            self.visible = []
            return
        self.visible = [i for i in self.lst.search(self.query) if self._passes_filter(i)]

    def toggle(self, i: int) -> bool:
        assert self.lst is not None
        return self.lst.toggle(i)

    def mark_visible(self, value: bool) -> None:
        assert self.lst is not None
        self.lst.set_selected(self.visible, value)

    # --- Textos ---

    def status_text(self, i: int) -> str:
        assert self.lst is not None
        st = self.lst.status_of(i)
        if st in MARKABLE and not self.lst.is_selected(i):
            return es.SKIP_EXCLUDED_BY_USER if st is V.VALID else es.VALIDATION[st.name]
        return "Se envía" if st is V.VALID else es.VALIDATION[st.name]

    def footer_text(self) -> str:
        if self.lst is None:
            return ""
        c = self.lst.counts()
        parts = [
            f"Se enviará a {c.effective}",
            f"Válidos {c.valid}",
            f"Inválidos {c.invalid}",
            f"Duplicados {c.duplicate}",
            f"Excluidos {c.excluded}",
        ]
        if c.already_sent:
            parts.append(f"Ya enviados {c.already_sent}")
        return " · ".join(parts)

    def can_advance(self) -> Guard:
        if self.lst is None:
            return Guard.deny("Elegí el archivo de Excel con los destinatarios.")
        if self.checking_domains:
            return Guard.deny("Esperá a que termine la verificación de los dominios.")
        if self.lst.counts().effective == 0:
            return Guard.deny("No hay destinatarios marcados. Marcá al menos uno para continuar.")
        return Guard.allow()
