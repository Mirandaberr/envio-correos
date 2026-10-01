"""Diálogo "Corregí el archivo y pulsá Continuar" (US3-AS1, AS2)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import customtkinter as ctk

from envio_correos.gui.app import FONT_BODY, FONT_TITLE, App
from envio_correos.gui.presenters.retry_wait import INSTRUCTIONS, RetryWaitPresenter
from envio_correos.gui.steps.common import COLOR_ERROR


class RetryWaitDialog(ctk.CTkToplevel):
    def __init__(
        self, app: App, presenter: RetryWaitPresenter, path: Path, on_loaded: Callable[[], None]
    ):
        super().__init__(app)
        self.app, self.presenter, self.path, self._on_loaded = app, presenter, path, on_loaded
        self.title("Corregir y reintentar")
        self.geometry("620x380")
        self.transient(app)
        ctk.CTkLabel(self, text="Corregí el archivo", font=FONT_TITLE).pack(
            anchor="w", padx=24, pady=(20, 8)
        )
        ctk.CTkLabel(
            self, text=INSTRUCTIONS, font=FONT_BODY, justify="left", anchor="w", wraplength=560
        ).pack(fill="x", padx=24)
        self.error = ctk.CTkLabel(
            self, text="", font=FONT_BODY, text_color=COLOR_ERROR, wraplength=560, justify="left"
        )
        self.error.pack(fill="x", padx=24, pady=8)
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=24, pady=(0, 20), side="bottom")
        ctk.CTkButton(
            buttons, text="Cancelar", fg_color="transparent", border_width=1, command=self.destroy
        ).pack(side="left")
        self.ok_btn = ctk.CTkButton(buttons, text="Continuar", command=self._continue)
        self.ok_btn.pack(side="right")
        self.after(100, self.grab_set)

    def _continue(self) -> None:
        self.ok_btn.configure(state="disabled", text="Leyendo el archivo…")
        self.error.configure(text="")
        self.app.run_background(
            lambda: self.presenter.load(self.path), self._loaded, name="leer-reintento"
        )

    def _loaded(self, error: str | None) -> None:
        if error:
            self.ok_btn.configure(state="normal", text="Continuar")
            self.error.configure(text=error)
            return
        self.grab_release()
        self.destroy()
        self._on_loaded()
