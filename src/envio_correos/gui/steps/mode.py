"""Vista del paso Modo (FR-040): dos tarjetas grandes y claramente distintas."""

from __future__ import annotations

import customtkinter as ctk

from envio_correos.core.message_builder import SendMode
from envio_correos.gui.app import FONT_BODY, FONT_TITLE, TEXT_INPUT_CLASSES, StepView
from envio_correos.gui.presenters.mode import ModePresenter
from envio_correos.gui.steps.common import COLOR_MUTED, title

CARDS = {
    SendMode.ONE_BY_ONE: (
        "1 → 1",
        "Uno por uno",
        "Cada persona recibe su propio correo, con su nombre.\nNadie ve a los demás.",
        ("#1f6aa5", "#5fb0ff"),
    ),
    SendMode.ALL_AT_ONCE_BCC: (
        "1 → ✱",
        "Todos a la vez",
        "Un mismo correo para todos.\nPor defecto nadie ve a los demás (copia oculta).",
        ("#7b3fa0", "#c792ea"),
    ),
}


class ModeView(StepView):
    presenter: ModePresenter

    def __init__(self, master, presenter: ModePresenter, app):
        super().__init__(master, presenter, app)
        title(
            self,
            presenter.title,
            "Elegí una opción (con el mouse o con las teclas 1 y 2). Podés volver atrás y "
            "cambiarla.",
        )
        # Atajos de teclado: las tarjetas no reciben foco con Tab (accesibilidad mínima).
        app.bind("1", lambda _e: self._key_select(SendMode.ONE_BY_ONE), add="+")
        app.bind("2", lambda _e: self._key_select(SendMode.ALL_AT_ONCE_BCC), add="+")
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="both", expand=True, pady=12)
        self.cards: dict[SendMode, ctk.CTkFrame] = {}
        for col, (mode, (icon, name, desc, color)) in enumerate(CARDS.items()):
            enabled = mode in presenter.available
            card = ctk.CTkFrame(row, border_width=3, border_color="gray60", corner_radius=16)
            card.grid(row=0, column=col, sticky="nsew", padx=12)
            row.columnconfigure(col, weight=1)
            widgets = [
                ctk.CTkLabel(
                    card,
                    text=icon,
                    font=("", 40, "bold"),
                    text_color=color if enabled else COLOR_MUTED,
                ),
                ctk.CTkLabel(card, text=name, font=FONT_TITLE),
                ctk.CTkLabel(
                    card,
                    text=desc if enabled else "Disponible próximamente.",
                    font=FONT_BODY,
                    justify="center",
                    wraplength=360,
                ),
            ]
            for w in widgets:
                w.pack(pady=10, padx=20)
            if enabled:
                for w in (card, *widgets):
                    w.bind("<Button-1>", lambda _e, m=mode: self._select(m))
            self.cards[mode] = card
        self.show_var = ctk.BooleanVar(value=False)
        self.show_check = ctk.CTkCheckBox(
            self.cards[SendMode.ALL_AT_ONCE_BCC],
            text="Mostrar los destinatarios entre sí",
            variable=self.show_var,
            command=self._toggle_show,
        )

    def _key_select(self, mode: SendMode) -> None:
        if not self.winfo_ismapped():
            return
        focus = self.app.focus_get()
        if focus is not None and focus.winfo_class() in TEXT_INPUT_CLASSES:
            return
        self._select(mode)

    def _select(self, mode: SendMode) -> None:
        if mode is SendMode.ALL_AT_ONCE_BCC and self.show_var.get():
            mode = SendMode.ALL_AT_ONCE_VISIBLE
        self.presenter.select(mode)
        self.refresh()

    def _toggle_show(self) -> None:
        self.presenter.set_show_recipients(bool(self.show_var.get()))
        self.refresh()

    def refresh(self) -> None:
        for mode, card in self.cards.items():
            selected = self.presenter.selected is not None and (
                self.presenter.selected is mode
                or (mode is SendMode.ALL_AT_ONCE_BCC and self.presenter.selected.is_batch)
            )
            card.configure(
                border_color=CARDS[mode][3] if selected else "gray60",
                border_width=6 if selected else 3,
            )
        batch = self.presenter.selected is not None and self.presenter.selected.is_batch
        self.show_var.set(self.presenter.show_recipients)
        if batch:
            self.show_check.pack(pady=(0, 16))
        else:
            self.show_check.pack_forget()
