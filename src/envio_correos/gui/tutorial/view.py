"""Ventana del tutorial de conexión (FR-012)."""

from __future__ import annotations

import customtkinter as ctk

from envio_correos.gui.app import FONT_BODY, FONT_TITLE
from envio_correos.gui.tutorial.content import ORDER, SECTIONS


class TutorialWindow(ctk.CTkToplevel):
    def __init__(self, master, section: str = "password", it_text: str | None = None):
        super().__init__(master)
        self.title("¿Cómo conecto mi cuenta?")
        self.geometry("880x520")
        self.transient(master)
        self._it_text = it_text
        menu = ctk.CTkFrame(self, width=260)
        menu.pack(side="left", fill="y", padx=(16, 8), pady=16)
        self._buttons: dict[str, ctk.CTkButton] = {}
        for key in ORDER:
            btn = ctk.CTkButton(
                menu,
                text=SECTIONS[key].title,
                anchor="w",
                width=240,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                command=lambda k=key: self.show(k),
            )
            btn.pack(fill="x", pady=2, padx=6)
            self._buttons[key] = btn
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=(8, 16), pady=16)
        self.heading = ctk.CTkLabel(
            body, text="", font=FONT_TITLE, anchor="w", justify="left", wraplength=540
        )
        self.heading.pack(fill="x")
        self.steps = ctk.CTkLabel(
            body, text="", font=FONT_BODY, anchor="nw", justify="left", wraplength=540
        )
        self.steps.pack(fill="both", expand=True, pady=12)
        self.copy_btn = ctk.CTkButton(body, text="Copiar mensaje para TI", command=self.copy_it)
        self.copied = ctk.CTkLabel(body, text="", font=FONT_BODY)
        self.show(section)

    def show(self, key: str) -> None:
        section = SECTIONS[key]
        self.heading.configure(text=section.title)
        self.steps.configure(text="\n\n".join(f"{i}. {s}" for i, s in enumerate(section.steps, 1)))
        for k, btn in self._buttons.items():
            btn.configure(fg_color=("#dbe8f6", "#24405e") if k == key else "transparent")
        if self._it_text and key in (
            "smtp_disabled",
            "security_defaults",
            "app_password",
            "password",
        ):
            self.copy_btn.pack(anchor="w")
            self.copied.pack(anchor="w", pady=4)
        else:
            self.copy_btn.pack_forget()
            self.copied.pack_forget()

    def copy_it(self) -> None:
        if self._it_text:
            self.clipboard_clear()
            self.clipboard_append(self._it_text)
            self.copied.configure(text="Mensaje copiado. Pegalo en un correo o chat a TI.")
