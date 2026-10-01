"""Vista del paso Cuenta (FR-010..014, US6)."""

from __future__ import annotations

import customtkinter as ctk

from envio_correos.gui.app import FONT_BODY, StepView
from envio_correos.gui.presenters.account import AccountPresenter
from envio_correos.gui.steps.common import COLOR_ERROR, COLOR_OK, message_label, small_label, title
from envio_correos.gui.tutorial.view import TutorialWindow


class AccountView(StepView):
    presenter: AccountPresenter

    def __init__(self, master, presenter: AccountPresenter, app):
        super().__init__(master, presenter, app)
        title(
            self,
            presenter.title,
            "Escribí tu correo de la empresa y tu contraseña. Antes de seguir, probamos que la "
            "conexión funcione (no se envía ningún correo).",
        )
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x")
        self.email = self._field(form, 0, "Tu correo")
        self.password = self._field(form, 1, "Contraseña", show="•")
        self.display_name = self._field(form, 2, "Nombre que verán los destinatarios (opcional)")
        self.remember_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            form,
            text="Recordar mi cuenta en este equipo",
            variable=self.remember_var,
            font=FONT_BODY,
        ).grid(row=3, column=1, sticky="w", pady=(6, 0))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", pady=(16, 8))
        self.test_btn = ctk.CTkButton(
            buttons, text="Probar conexión", font=FONT_BODY, height=40, command=self._test
        )
        self.test_btn.pack(side="left")
        ctk.CTkButton(
            buttons,
            text="¿Cómo conecto mi cuenta?",
            fg_color="transparent",
            border_width=1,
            command=lambda: self._open_help("password"),
        ).pack(side="left", padx=12)
        self.forget_btn = ctk.CTkButton(
            buttons,
            text="Olvidar mi cuenta",
            fg_color="transparent",
            text_color=("gray30", "gray70"),
            hover=False,
            command=self._forget,
        )

        self.status = message_label(self)
        self.status.pack(fill="x")
        self.help_bar = ctk.CTkFrame(self, fg_color="transparent")
        self.help_btn = ctk.CTkButton(
            self.help_bar,
            text="Ver ayuda para este error",
            command=lambda: self._open_help(self.presenter.help_section()),
        )
        self.help_btn.pack(side="left")
        self.it_btn = ctk.CTkButton(
            self.help_bar,
            text="Copiar mensaje para TI",
            fg_color="transparent",
            border_width=1,
            command=self._copy_it,
        )
        self.copied = small_label(self.help_bar)

        self._advanced_open = False
        self.adv_btn = ctk.CTkButton(
            self,
            text="▸ Avanzado",
            fg_color="transparent",
            text_color=("gray20", "gray80"),
            hover=False,
            anchor="w",
            command=self._toggle_advanced,
            width=120,
        )
        self.adv_btn.pack(anchor="w", pady=(16, 0))
        self.adv = small_label(self, f"Servidor de envío: {presenter.server_label}")
        self._auto_tested = False

    def _field(self, form, row: int, label: str, show: str | None = None) -> ctk.CTkEntry:
        ctk.CTkLabel(form, text=label, font=FONT_BODY, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(0, 16), pady=6
        )
        entry = ctk.CTkEntry(form, width=420, font=FONT_BODY, show=show or "")
        entry.grid(row=row, column=1, sticky="w", pady=6)
        return entry

    def _toggle_advanced(self) -> None:
        self._advanced_open = not self._advanced_open
        if self._advanced_open:
            self.adv.pack(fill="x", after=self.adv_btn)
        else:
            self.adv.pack_forget()
        self.adv_btn.configure(text=("▾" if self._advanced_open else "▸") + " Avanzado")

    # --- Ciclo de vida ---

    def refresh(self) -> None:
        p = self.presenter
        if p.email and not self.email.get():
            self.email.insert(0, p.email)
            self.display_name.insert(0, p.display_name)
        if p.remembered_password and not self.password.get():
            self.password.insert(0, p.remembered_password)
        self.remember_var.set(p.remember)
        if p.remembered_password:
            self.forget_btn.pack(side="left")
        else:
            self.forget_btn.pack_forget()
        self.email.focus_set()
        # Cuenta recordada: se prueba sola la primera vez (US6-AS3).
        if p.remembered_password and not p.connected_as and not self._auto_tested:
            self._auto_tested = True
            self._test()

    def commit(self) -> None:
        self.presenter.set_fields(self.email.get(), self.display_name.get())
        self.presenter.remember = bool(self.remember_var.get())

    # --- Acciones ---

    def _test(self) -> None:
        self.commit()
        password = self.password.get()
        error = self.presenter.validate_fields(password)
        if error:
            self.status.configure(text=error, text_color=COLOR_ERROR)
            return
        self.presenter.testing = True
        self.test_btn.configure(state="disabled", text="Probando…")
        self.help_bar.pack_forget()
        self.status.configure(text="Conectando con el servidor de correo…", text_color="gray50")
        self.app.run_background(
            lambda: self.presenter.test_connection(password),
            self._tested,
            name="probar-conexion",
        )

    def _tested(self, result) -> None:
        p = self.presenter
        p.testing = False
        self.test_btn.configure(state="normal", text="Probar conexión")
        self.status.configure(
            text=p.result_message(), text_color=COLOR_OK if result.ok else COLOR_ERROR
        )
        if result.ok:
            self.help_bar.pack_forget()
            if p.remembered_password:
                self.forget_btn.pack(side="left")
            return
        self.help_bar.pack(fill="x", pady=(8, 0), after=self.status)
        if p.needs_it():
            self.it_btn.pack(side="left", padx=8)
            self.copied.pack(side="left")
        else:
            self.it_btn.pack_forget()
            self.copied.pack_forget()

    def _open_help(self, section: str) -> None:
        self.commit()
        TutorialWindow(self.app, section, it_text=self.presenter.it_request_text())

    def _copy_it(self) -> None:
        self.commit()
        self.clipboard_clear()
        self.clipboard_append(self.presenter.it_request_text())
        self.copied.configure(text="Copiado. Pegalo en un correo o chat a TI.")

    def _forget(self) -> None:
        if not self.app.confirm("¿Olvidar la cuenta guardada en este equipo?"):
            return
        self.presenter.forget_account()
        for entry in (self.email, self.password):
            entry.delete(0, "end")
        self.remember_var.set(False)
        self.forget_btn.pack_forget()
        self.status.configure(text="")
