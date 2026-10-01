"""Vista del paso Envío (FR-053): progreso, Detener y pausa."""

from __future__ import annotations

import customtkinter as ctk

from envio_correos.core.engine import Finished
from envio_correos.gui.app import FONT_BODY, StepView
from envio_correos.gui.presenters.sending import SendingPresenter
from envio_correos.gui.steps.common import COLOR_WARN, message_label, title


class SendingView(StepView):
    presenter: SendingPresenter

    def __init__(self, master, presenter: SendingPresenter, app):
        super().__init__(master, presenter, app)
        title(
            self,
            presenter.title,
            "Podés dejar la ventana abierta y seguir trabajando. No apagues el equipo.",
        )
        self.bar = ctk.CTkProgressBar(self, height=18)
        self.bar.set(0)
        self.bar.pack(fill="x", pady=(16, 8))
        self.text = ctk.CTkLabel(self, text="", font=FONT_BODY, anchor="w")
        self.text.pack(fill="x")
        self.stop_btn = ctk.CTkButton(
            self,
            text="Detener envío",
            fg_color="#b3261e",
            hover_color="#8c1d18",
            command=self._stop,
        )
        self.stop_btn.pack(anchor="w", pady=16)
        self.paused_lbl = message_label(self)
        self.resume_btn = ctk.CTkButton(self, text="Continuar envío", command=self._resume)

    def refresh(self) -> None:
        if self.presenter.needs_start:
            self.presenter.start(lambda e: self.app.post(self, e))
        self._render()

    def handle_event(self, event: object) -> None:
        self.presenter.apply(event)
        self._render()
        if isinstance(event, Finished):
            self.app.on_next()

    def _render(self) -> None:
        p = self.presenter
        self.bar.set(p.progress_fraction())
        self.text.configure(text=p.progress_text())
        running = p.running and not p.finished and not p.paused
        self.stop_btn.configure(state="normal" if running else "disabled")
        paused = p.paused_text()
        if paused:
            self.paused_lbl.configure(text=paused, text_color=COLOR_WARN)
            self.paused_lbl.pack(fill="x", pady=8)
            self.resume_btn.pack(anchor="w")
        else:
            self.paused_lbl.pack_forget()
            self.resume_btn.pack_forget()
        self.app.update_chrome()

    def _stop(self) -> None:
        if self.app.confirm("¿Detener el envío? Los correos que falten no se enviarán."):
            self.stop_btn.configure(state="disabled", text="Deteniendo…")
            self.presenter.stop()

    def _resume(self) -> None:
        self.presenter.start(lambda e: self.app.post(self, e))
        self._render()

    @property
    def next_label(self) -> str:
        return "Ver resultado"
