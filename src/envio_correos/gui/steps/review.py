"""Vista del paso Revisión (FR-050..052): resumen, vista previa navegable y prueba."""

from __future__ import annotations

import customtkinter as ctk

from envio_correos.gui.app import FONT_BODY, FONT_SMALL, StepView
from envio_correos.gui.presenters.review import ReviewPresenter
from envio_correos.gui.steps.common import COLOR_ERROR, COLOR_OK, COLOR_WARN, message_label, title


class ReviewView(StepView):
    presenter: ReviewPresenter

    def __init__(self, master, presenter: ReviewPresenter, app):
        super().__init__(master, presenter, app)
        title(self, presenter.title, "Si todo está bien, pulsá «Enviar».")
        self.grid_frame = ctk.CTkFrame(self)
        self.grid_frame.pack(fill="x", pady=(0, 8))
        self.warning = message_label(self)
        self.warning.pack(fill="x")

        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", pady=(8, 4))
        ctk.CTkLabel(nav, text="Vista previa", font=("", 14, "bold")).pack(side="left")
        self.prev_btn = ctk.CTkButton(nav, text="◀", width=36, command=lambda: self._move(-1))
        self.prev_btn.pack(side="left", padx=(12, 4))
        self.pos_lbl = ctk.CTkLabel(nav, text="", font=FONT_SMALL)
        self.pos_lbl.pack(side="left")
        self.next_btn = ctk.CTkButton(nav, text="▶", width=36, command=lambda: self._move(1))
        self.next_btn.pack(side="left", padx=4)
        self.test_btn = ctk.CTkButton(
            nav,
            text="Enviarme una prueba",
            fg_color="transparent",
            border_width=1,
            command=self._send_test,
        )
        self.test_btn.pack(side="right")
        self.test_lbl = ctk.CTkLabel(nav, text="", font=FONT_SMALL)
        self.test_lbl.pack(side="right", padx=8)

        self.preview = ctk.CTkTextbox(self, font=FONT_BODY, wrap="word", height=200)
        self.preview.pack(fill="both", expand=True)
        self._pos = 0

    def refresh(self) -> None:
        for w in self.grid_frame.winfo_children():
            w.destroy()
        for r, (label, value) in enumerate(self.presenter.summary()):
            ctk.CTkLabel(self.grid_frame, text=label, font=("", 14, "bold"), anchor="w").grid(
                row=r, column=0, sticky="w", padx=16, pady=3
            )
            ctk.CTkLabel(
                self.grid_frame,
                text=value,
                font=FONT_BODY,
                anchor="w",
                wraplength=700,
                justify="left",
            ).grid(row=r, column=1, sticky="w", padx=16, pady=3)
        warnings = [
            w for w in (self.presenter.daily_warning(), self.presenter.empty_values_warning()) if w
        ]
        self.warning.configure(text="\n".join(warnings), text_color=COLOR_WARN)
        self.test_lbl.configure(text="")
        self._pos = 0
        self._render_preview()

    def _move(self, delta: int) -> None:
        self._pos = max(0, min(self._pos + delta, self.presenter.preview_count - 1))
        self._render_preview()

    def _render_preview(self) -> None:
        count = self.presenter.preview_count
        self.pos_lbl.configure(text=f"{self._pos + 1} de {count}" if count else "")
        self.prev_btn.configure(state="normal" if self._pos > 0 else "disabled")
        self.next_btn.configure(state="normal" if self._pos < count - 1 else "disabled")
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        if count:
            p = self.presenter.preview(self._pos)
            text = f"Para: {p['to']}\nAsunto: {p['subject']}\n"
            if p["attachments"]:
                text += f"Adjuntos: {p['attachments']}\n"
            self.preview.insert("1.0", f"{text}\n{p['body']}")
        self.preview.configure(state="disabled")

    def _send_test(self) -> None:
        self.test_btn.configure(state="disabled", text="Enviando prueba…")
        self.app.run_background(self.presenter.send_test, self._tested, name="correo-de-prueba")

    def _tested(self, error: str | None) -> None:
        self.test_btn.configure(state="normal", text="Enviarme una prueba")
        if error:
            self.test_lbl.configure(text=error, text_color=COLOR_ERROR)
        else:
            self.test_lbl.configure(text="Prueba enviada a tu casilla.", text_color=COLOR_OK)

    @property
    def next_label(self) -> str:
        return "Enviar"
