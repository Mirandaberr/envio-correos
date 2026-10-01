"""Vista del paso Destinatarios (FR-020..026, contracts/wizard-ui.md)."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from envio_correos import config
from envio_correos.gui.app import FONT_BODY, StepView
from envio_correos.gui.presenters.recipients import RecipientsPresenter, StatusFilter
from envio_correos.gui.steps.common import COLOR_WARN, small_label, title
from envio_correos.gui.widgets.recipient_table import RecipientTable


class RecipientsView(StepView):
    presenter: RecipientsPresenter

    def __init__(self, master, presenter: RecipientsPresenter, app):
        super().__init__(master, presenter, app)
        title(
            self,
            presenter.title,
            "Elegí el archivo de Excel. Revisá la lista: podés buscar y desmarcar a quien no "
            "quieras incluir.",
        )
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 8))
        ctk.CTkButton(bar, text="Elegir archivo…", font=FONT_BODY, command=self._choose_file).pack(
            side="left"
        )
        self.file_lbl = ctk.CTkLabel(bar, text="Ningún archivo elegido", font=FONT_BODY)
        self.file_lbl.pack(side="left", padx=12)

        self.opts = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.opts, text="Hoja:", font=FONT_BODY).pack(side="left")
        self.sheet_menu = ctk.CTkOptionMenu(self.opts, values=[""], command=self._sheet_changed)
        self.sheet_menu.pack(side="left", padx=(4, 16))
        ctk.CTkLabel(self.opts, text="Columna del correo:", font=FONT_BODY).pack(side="left")
        self.col_menu = ctk.CTkOptionMenu(self.opts, values=[""], command=self._col_changed)
        self.col_menu.pack(side="left", padx=(4, 16))
        ctk.CTkLabel(self.opts, text="🔍", font=FONT_BODY).pack(side="left")
        self.search = ctk.CTkEntry(
            self.opts, width=240, font=FONT_BODY, placeholder_text="Buscar nombre, correo…"
        )
        self.search.pack(side="left", padx=4)
        self.search.bind("<KeyRelease>", self._search_changed)
        ctk.CTkButton(self.opts, text="✕", width=32, command=self._clear_search).pack(side="left")

        self.filters = ctk.CTkSegmentedButton(
            self, values=[f.value for f in StatusFilter], command=self._filter_changed
        )
        self.filters.set(StatusFilter.ALL.value)

        self.table = RecipientTable(self, presenter.status_text, self._toggled)
        self.empty_lbl = small_label(self, "No hay destinatarios que coincidan.")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions = actions
        ctk.CTkButton(
            actions, text="Marcar visibles", width=150, command=lambda: self._mark(True)
        ).pack(side="left")
        ctk.CTkButton(
            actions, text="Desmarcar visibles", width=150, command=lambda: self._mark(False)
        ).pack(side="left", padx=8)
        self.footer = ctk.CTkLabel(actions, text="", font=FONT_BODY)
        self.footer.pack(side="right")
        self.notice = small_label(self)
        self._search_job: str | None = None
        self._loaded_list = None

    # --- Archivo ---

    def _choose_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Elegí el Excel con los destinatarios",
            filetypes=[("Libro de Excel", "*.xlsx"), ("Todos los archivos", "*.*")],
        )
        if path:
            self._load(Path(path))

    def _load(self, path: Path, sheet: str | None = None) -> None:
        self.file_lbl.configure(text=f"Cargando {path.name}…")
        self.app.run_background(
            lambda: self.presenter.load(path, sheet), self._loaded, name="cargar-excel"
        )

    def _loaded(self, error: str | None) -> None:
        p = self.presenter
        if error:
            self.file_lbl.configure(
                text="Ningún archivo elegido" if p.path is None else p.path.name
            )
            self.app.show_error(error)
            return
        self.file_lbl.configure(text=p.path.name if p.path else "")
        self._show_list()
        self._check_domains()

    def _show_list(self) -> None:
        p, lst = self.presenter, self.presenter.lst
        if lst is None:
            return
        self.opts.pack(fill="x", pady=(0, 8))
        self.filters.pack(anchor="w", pady=(0, 8))
        self.table.pack(fill="both", expand=True)
        self.actions.pack(fill="x", pady=(8, 0))
        self.sheet_menu.configure(values=p.sheets)
        self.sheet_menu.set(lst.sheet_name)
        self.col_menu.configure(values=list(lst.headers))
        self.col_menu.set(lst.headers[lst.email_col])
        self.search.delete(0, "end")
        self.filters.set(StatusFilter.ALL.value)
        self.table.load(lst)
        self._loaded_list = lst
        self._update()

    def _sheet_changed(self, sheet: str) -> None:
        if self.presenter.path is not None:
            self._load(self.presenter.path, sheet)

    def _col_changed(self, header: str) -> None:
        lst = self.presenter.lst
        if lst is not None:
            self.presenter.set_email_column(lst.headers.index(header))
            self.table.load(lst)
            self._update()
            self._check_domains()

    # --- Dominios ---

    def _check_domains(self) -> None:
        self.notice.configure(text="Verificando dominios…", text_color="gray50")
        self.notice.pack(fill="x", pady=(4, 0))

        def progress(done: int, total: int) -> None:
            self.app.post(
                None, lambda: self.notice.configure(text=f"Verificando dominios… {done}/{total}")
            )

        self.app.run_background(
            lambda: self.presenter.check_domains(progress),
            self._domains_checked,
            name="verificar-dominios",
        )

    def _domains_checked(self, changed: int) -> None:
        p = self.presenter
        self.table.refresh_rows()
        self._update()
        if p.domain_notice:
            self.notice.configure(text=p.domain_notice, text_color=COLOR_WARN)
        elif changed:
            self.notice.configure(
                text=f"{changed} dirección(es) tienen un dominio que no existe; quedaron "
                "marcadas como inválidas.",
                text_color=COLOR_WARN,
            )
        else:
            self.notice.configure(text="Dominios verificados.", text_color="gray50")

    # --- Búsqueda, filtro y selección ---

    def _search_changed(self, _event=None) -> None:
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(config.SEARCH_DEBOUNCE_MS, self._apply_search)

    def _apply_search(self) -> None:
        self._search_job = None
        self.presenter.set_query(self.search.get())
        self._update()

    def _clear_search(self) -> None:
        self.search.delete(0, "end")
        self._apply_search()

    def _filter_changed(self, value: str) -> None:
        self.presenter.set_filter(StatusFilter(value))
        self._update()

    def _toggled(self, i: int) -> None:
        self.presenter.toggle(i)
        self.footer.configure(text=self.presenter.footer_text())

    def _mark(self, value: bool) -> None:
        self.presenter.mark_visible(value)
        self.table.refresh_rows(self.presenter.visible)
        self._update()

    def _update(self) -> None:
        p = self.presenter
        self.table.show_only(p.visible)
        if p.visible:
            self.empty_lbl.pack_forget()
        else:
            self.empty_lbl.pack(fill="x", before=self.actions)
        self.footer.configure(text=p.footer_text())

    def refresh(self) -> None:
        if self.presenter.lst is not None and self.presenter.lst is not self._loaded_list:
            self._show_list()
