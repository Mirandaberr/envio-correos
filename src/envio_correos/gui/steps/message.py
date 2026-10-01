"""Vista del paso Mensaje (FR-030..033): texto, variables por columna y adjuntos."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from envio_correos.core import attachments
from envio_correos.gui.app import FONT_BODY, FONT_SMALL, StepView
from envio_correos.gui.presenters.message import MessagePresenter
from envio_correos.gui.steps.common import COLOR_WARN, message_label, small_label, title


class MessageView(StepView):
    presenter: MessagePresenter

    def __init__(self, master, presenter: MessagePresenter, app):
        super().__init__(master, presenter, app)
        title(self, presenter.title, "Escribí el asunto y el texto del correo.")
        self.warning = message_label(self)
        self.subject_lbl = ctk.CTkLabel(self, text="Asunto", font=FONT_BODY, anchor="w")
        self.subject_lbl.pack(fill="x")
        self.subject = ctk.CTkEntry(self, font=FONT_BODY)
        self.subject.pack(fill="x", pady=(2, 8))

        self.vars_lbl = small_label(
            self,
            "Datos de cada persona (se reemplazan al enviar uno por uno). Hacé clic para "
            "insertarlos donde está el cursor:",
        )
        self.vars_frame = ctk.CTkScrollableFrame(
            self, height=44, orientation="horizontal", fg_color="transparent"
        )

        self.body_lbl = ctk.CTkLabel(self, text="Texto del correo", font=FONT_BODY, anchor="w")
        self.body_lbl.pack(fill="x")
        self.body = ctk.CTkTextbox(self, font=FONT_BODY, wrap="word", height=220)
        self.body.pack(fill="both", expand=True, pady=(2, 8))

        att_bar = ctk.CTkFrame(self, fg_color="transparent")
        att_bar.pack(fill="x")
        ctk.CTkButton(att_bar, text="📎 Agregar adjunto…", width=180, command=self._add_files).pack(
            side="left"
        )
        self.att_summary = ctk.CTkLabel(att_bar, text="", font=FONT_SMALL)
        self.att_summary.pack(side="left", padx=12)
        self.att_list = ctk.CTkFrame(self, fg_color="transparent")
        self.att_list.pack(fill="x")

        # Campo donde se insertan las variables: el último que tuvo el foco.
        self._target: ctk.CTkEntry | ctk.CTkTextbox = self.body
        self.subject.bind("<FocusIn>", lambda _e: self._set_target(self.subject))
        self.body.bind("<FocusIn>", lambda _e: self._set_target(self.body))
        self._var_buttons: tuple[str, ...] = ()

    def _set_target(self, widget) -> None:
        self._target = widget

    # --- Variables (FR-031) ---

    def _render_variables(self) -> None:
        names = self.presenter.variables()
        if names == self._var_buttons:
            return
        self._var_buttons = names
        for w in self.vars_frame.winfo_children():
            w.destroy()
        if not names:
            self.vars_lbl.pack_forget()
            self.vars_frame.pack_forget()
            return
        self.vars_lbl.pack(fill="x", before=self.body_lbl)
        self.vars_frame.pack(fill="x", pady=(0, 8), before=self.body_lbl)
        for name in names:
            ctk.CTkButton(
                self.vars_frame,
                text=name,
                width=40,
                height=28,
                fg_color=("#e3eefb", "#1e3550"),
                text_color=("#1f6aa5", "#9fd0ff"),
                hover_color=("#cfe2f8", "#264466"),
                command=lambda n=name: self._insert(n),
            ).pack(side="left", padx=3)

    def _insert(self, column: str) -> None:
        self._target.insert("insert", self.presenter.token(column))
        self._target.focus_set()

    # --- Adjuntos (FR-032) ---

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(parent=self, title="Elegí los archivos a adjuntar")
        if not paths:
            return
        errors = self.presenter.add_files([Path(p) for p in paths])
        if errors:
            self.app.show_error("\n".join(errors))
        self._render_attachments()

    def _remove(self, index: int) -> None:
        self.presenter.remove_attachment(index)
        self._render_attachments()

    def _render_attachments(self) -> None:
        for w in self.att_list.winfo_children():
            w.destroy()
        for i, ref in enumerate(self.presenter.attachments):
            row = ctk.CTkFrame(self.att_list, fg_color="transparent")
            row.pack(fill="x")
            ctk.CTkLabel(
                row,
                text=f"{Path(ref.path).name}  ({attachments.human_size(ref.size)})",
                font=FONT_SMALL,
                anchor="w",
            ).pack(side="left")
            ctk.CTkButton(
                row,
                text="Quitar",
                width=60,
                height=24,
                fg_color="transparent",
                border_width=1,
                command=lambda i=i: self._remove(i),
            ).pack(side="left", padx=8)
        self.att_summary.configure(text=self.presenter.attachments_summary())
        warning = self.presenter.attachment_warning() or attachments.size_error(
            self.presenter.attachments
        )
        if warning:
            self.warning.configure(text=warning, text_color=COLOR_WARN)
            self.warning.pack(fill="x", pady=(0, 8), before=self.subject_lbl)
        else:
            self.warning.pack_forget()

    # --- Ciclo de vida ---

    def refresh(self) -> None:
        p = self.presenter
        self.subject.delete(0, "end")
        self.subject.insert(0, p.subject)
        self.body.delete("1.0", "end")
        self.body.insert("1.0", p.body)
        self._render_variables()
        self._render_attachments()
        self.subject.focus_set()

    def commit(self) -> None:
        self.presenter.set_text(self.subject.get(), self.body.get("1.0", "end-1c"))
