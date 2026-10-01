"""Vista de inicio: nuevo envío, reintento de una campaña anterior, envío sin terminar (US7)
y borrado del historial (FR-065)."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from envio_correos.gui import os_open
from envio_correos.gui.app import FONT_BODY, StepView
from envio_correos.gui.presenters.base import STEP_ACCOUNT
from envio_correos.gui.presenters.retry_wait import RetryWaitPresenter
from envio_correos.gui.presenters.start import StartPresenter
from envio_correos.gui.steps.common import COLOR_WARN, message_label, small_label, title


class StartView(StepView):
    presenter: StartPresenter

    def __init__(self, master, presenter: StartPresenter, app):
        super().__init__(master, presenter, app)
        title(
            self,
            "Envío de correos",
            "Este asistente te guía paso a paso para enviar un correo a una lista de personas "
            "desde tu cuenta, usando un archivo de Excel.",
        )
        # Aviso de envío sin terminar (US7)
        self.banner = ctk.CTkFrame(self, border_width=2, border_color=COLOR_WARN)
        self.banner_text = message_label(self.banner)
        self.banner_text.pack(fill="x", padx=16, pady=(12, 4))
        self.resend_var = ctk.BooleanVar(value=False)
        self.resend_check = ctk.CTkCheckBox(
            self.banner,
            text="Reenviar también a las direcciones dudosas (pueden recibirlo dos veces)",
            variable=self.resend_var,
            font=FONT_BODY,
        )
        banner_actions = ctk.CTkFrame(self.banner, fg_color="transparent")
        banner_actions.pack(fill="x", padx=16, pady=(4, 12), side="bottom")
        ctk.CTkButton(banner_actions, text="Continuar el envío", command=self._resume).pack(
            side="left"
        )
        ctk.CTkButton(
            banner_actions,
            text="Descartar y generar reporte",
            fg_color="transparent",
            border_width=1,
            command=self._discard,
        ).pack(side="left", padx=8)
        self._unfinished = None

        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.pack(fill="x", pady=24)
        ctk.CTkButton(
            self.actions,
            text="Nuevo envío",
            font=FONT_BODY,
            height=48,
            width=340,
            command=app.on_next,
        ).pack(anchor="w", pady=6)
        ctk.CTkButton(
            self.actions,
            text="Reintentar fallidos de una campaña anterior",
            font=FONT_BODY,
            height=48,
            width=340,
            fg_color="transparent",
            border_width=1,
            command=self._retry_previous,
        ).pack(anchor="w", pady=6)

        ctk.CTkButton(
            self,
            text="Borrar historial de envíos",
            fg_color="transparent",
            text_color=("gray30", "gray70"),
            hover=False,
            command=self._clear_history,
        ).pack(anchor="w", side="bottom")
        small_label(
            self,
            "El historial guarda los datos de cada campaña 30 días para poder reintentar. "
            "Podés borrarlo cuando quieras.",
        ).pack(anchor="w", side="bottom")

    @property
    def next_label(self) -> str:
        return "Comenzar"

    def refresh(self) -> None:
        u = self._unfinished = self.presenter.unfinished()
        if u is None:
            self.banner.pack_forget()
            return
        self.banner_text.configure(text=self.presenter.unfinished_text(u), text_color=COLOR_WARN)
        self.resend_var.set(False)
        if u.unknown:
            self.resend_check.pack(anchor="w", padx=16, after=self.banner_text)
        else:
            self.resend_check.pack_forget()
        self.banner.pack(fill="x", pady=(8, 0), before=self.actions)

    # --- Envío sin terminar (US7) ---

    def _resume(self) -> None:
        if self._unfinished is None:
            return
        self.presenter.prepare_resume(self._unfinished, bool(self.resend_var.get()))
        self.app.go_to(STEP_ACCOUNT)

    def _discard(self) -> None:
        u = self._unfinished
        if u is None or not self.app.confirm(
            "¿Descartar el envío sin terminar? Los correos que faltan no se enviarán y quedarán "
            "en un Excel de fallidos para que puedas reintentarlos después."
        ):
            return
        path = self.presenter.discard(u)
        self.refresh()
        if path is not None:
            self.app.show_info(f"Se guardó el Excel con los correos pendientes:\n{path}")
            os_open.open_path(path.parent)

    # --- Reintento de una campaña anterior (US3) ---

    def _retry_previous(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Elegí el Excel de fallidos (…_fallidos_….xlsx)",
            filetypes=[("Libro de Excel", "*.xlsx"), ("Todos los archivos", "*.*")],
        )
        if path:
            self.load_retry(Path(path))

    def load_retry(self, path: Path) -> None:
        presenter = RetryWaitPresenter(self.presenter.ctx)

        def loaded(error: str | None) -> None:
            if error:
                self.app.show_error(error)
            else:
                self.app.go_to(STEP_ACCOUNT)

        self.app.run_background(lambda: presenter.load(path), loaded, name="leer-reintento")

    # --- Historial (FR-065) ---

    def _clear_history(self) -> None:
        if self.app.confirm(
            "¿Borrar el historial de envíos? Ya no vas a poder reintentar campañas anteriores "
            "desde su Excel de fallidos."
        ):
            n = self.presenter.clear_history()
            self.refresh()
            self.app.show_info(f"Historial borrado ({n} campañas).")
