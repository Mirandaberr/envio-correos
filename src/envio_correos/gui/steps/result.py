"""Vista del paso Resultado (FR-060, FR-062, FR-071)."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from envio_correos.core.report import ReportWriteError
from envio_correos.gui import os_open
from envio_correos.gui.app import FONT_BODY, StepView
from envio_correos.gui.presenters.base import STEP_RECIPIENTS
from envio_correos.gui.presenters.result import ResultPresenter
from envio_correos.gui.presenters.retry_wait import RetryWaitPresenter
from envio_correos.gui.steps.common import COLOR_WARN, message_label, small_label, title


class ResultView(StepView):
    presenter: ResultPresenter

    def __init__(self, master, presenter: ResultPresenter, app):
        super().__init__(master, presenter, app)
        title(self, presenter.title)
        self.code_lbl = ctk.CTkLabel(self, text="", font=FONT_BODY, anchor="w")
        self.code_lbl.pack(fill="x")
        self.grid_frame = ctk.CTkFrame(self)
        self.grid_frame.pack(fill="x", pady=12)
        self.report_lbl = message_label(self)
        self.report_lbl.pack(fill="x")
        self.report_actions = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkButton(self.report_actions, text="Corregir y reintentar", command=self._retry).pack(
            side="left"
        )
        ctk.CTkButton(
            self.report_actions,
            text="Abrir Excel de fallidos",
            fg_color="transparent",
            border_width=1,
            command=self._open_report,
        ).pack(side="left", padx=8)
        self.notice = message_label(self)
        self.notice.pack(fill="x", pady=8)
        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.pack(fill="x", pady=8)
        ctk.CTkButton(self.actions, text="Nuevo envío", command=self._new).pack(side="left")
        ctk.CTkButton(
            self.actions,
            text="Abrir carpeta de registros",
            fg_color="transparent",
            border_width=1,
            command=self._open_logs,
        ).pack(side="left", padx=8)
        self.hint = small_label(
            self,
            "Si necesitás ayuda, enviá la carpeta de registros a "
            "soporte junto con el código de campaña.",
        )
        self.hint.pack(fill="x")

    def refresh(self) -> None:
        p = self.presenter
        self.code_lbl.configure(text=f"Código de campaña: {p.code}")
        for w in self.grid_frame.winfo_children():
            w.destroy()
        for r, (label, value) in enumerate(p.breakdown().items()):
            ctk.CTkLabel(self.grid_frame, text=label, font=("", 14, "bold"), anchor="w").grid(
                row=r, column=0, sticky="w", padx=16, pady=4
            )
            ctk.CTkLabel(self.grid_frame, text=str(value), font=FONT_BODY).grid(
                row=r, column=1, sticky="w", padx=16, pady=4
            )
        self.notice.configure(text=p.notice(), text_color=COLOR_WARN)
        if p.report_pending:
            self._generate_report()
        self._render_report()

    def _generate_report(self, target: Path | None = None) -> None:
        try:
            self.presenter.generate_report(target)
        except ReportWriteError as exc:
            chosen = filedialog.asksaveasfilename(
                parent=self,
                title="No se pudo guardar ahí. Elegí dónde guardar el Excel de fallidos",
                initialfile=exc.suggested_path.name,
                defaultextension=".xlsx",
                filetypes=[("Libro de Excel", "*.xlsx")],
            )
            if chosen:
                self._generate_report(Path(chosen))
            else:
                self.presenter.skip_report()

    def _render_report(self) -> None:
        p = self.presenter
        self.report_lbl.configure(text=p.report_text())
        if p.report_path:
            self.report_actions.pack(anchor="w", pady=(4, 8), after=self.report_lbl)
        else:
            self.report_actions.pack_forget()

    def _open_report(self) -> None:
        path = self.presenter.report_path
        if path and not os_open.open_path(path):
            self.app.show_error(f"No se pudo abrir el archivo. Está en:\n{path}")

    def _open_logs(self) -> None:
        if not os_open.open_path(self.presenter.logs_dir()):
            self.app.show_error(
                f"No se pudo abrir la carpeta. Está en:\n{self.presenter.logs_dir()}"
            )

    def _new(self) -> None:
        self.presenter.reset_for_new_campaign()
        self.app.go_to(STEP_RECIPIENTS)

    def _retry(self) -> None:
        from envio_correos.gui.steps.retry_wait import RetryWaitDialog

        path = self.presenter.report_path
        if path is None:
            return
        os_open.open_path(path)
        RetryWaitDialog(
            self.app,
            RetryWaitPresenter(self.presenter.ctx),
            path,
            lambda: self.app.go_to(STEP_RECIPIENTS),
        )
