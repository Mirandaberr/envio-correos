"""Ventana principal del asistente.

Tk no es thread-safe: los hilos de trabajo (probar conexión, verificar dominios, enviar) nunca
tocan widgets; publican eventos en `self.events` y la ventana los drena cada EVENT_POLL_MS
(research R7.7). En cada tick se vacía la cola completa, así que no acumula eventos.
"""

from __future__ import annotations

import gc
import logging
import queue
import threading
import tkinter.messagebox as messagebox
from collections.abc import Callable
from typing import Any

import customtkinter as ctk

from envio_correos import config
from envio_correos.gui.presenters.base import StepPresenter, Wizard
from envio_correos.texts import es

log = logging.getLogger(__name__)

FONT_TITLE = ("", 20, "bold")
FONT_BODY = ("", 14)
FONT_SMALL = ("", 12)
# Clases Tk de los campos donde Enter y las teclas de atajo deben escribir, no navegar.
TEXT_INPUT_CLASSES = frozenset({"Text", "Entry", "TEntry"})


class StepView(ctk.CTkFrame):
    """Vista de un paso. Se crea una vez y se conserva al navegar (FR-001)."""

    def __init__(self, master: Any, presenter: StepPresenter, app: App):
        super().__init__(master, fg_color="transparent")
        self.presenter = presenter
        self.app = app

    def refresh(self) -> None:
        """Redibuja desde el estado del presenter."""

    def handle_event(self, event: Any) -> None:
        """Recibe eventos de hilos de trabajo (ya en el hilo de Tk)."""

    def commit(self) -> None:
        """Vuelca lo escrito en los campos al presenter antes de avanzar."""

    @property
    def next_label(self) -> str:
        return "Siguiente"


ViewFactory = Callable[[Any, StepPresenter, "App"], StepView]


class App(ctk.CTk):
    def __init__(
        self, wizard: Wizard, view_factories: list[ViewFactory], *, first_numbered: int = 1
    ):
        super().__init__()
        self.title(es.APP_TITLE)
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.wizard = wizard
        self.events: queue.Queue[tuple[StepView | None, Any]] = queue.Queue()
        self._factories = view_factories
        self._views: dict[int, StepView] = {}
        self._first_numbered = first_numbered  # índice del paso "1) Cuenta"

        self._build_header()
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=24, pady=(8, 8))
        self._build_footer()
        self.bind("<Return>", self._on_return)
        self.show_current()
        self.after(config.EVENT_POLL_MS, self._drain_events)
        self._gc_was_enabled = gc.isenabled()
        gc.disable()
        self.after(config.GC_INTERVAL_MS, self._collect_garbage)

    # --- Estructura ---

    def _build_header(self) -> None:
        self.header = ctk.CTkFrame(self)
        self.header.pack(fill="x", padx=24, pady=(16, 0))
        self._step_labels = []
        for i, name in enumerate(es.STEPS, 1):
            lbl = ctk.CTkLabel(self.header, text=f"{i}. {name}", font=FONT_SMALL)
            lbl.pack(side="left", padx=10, pady=8)
            self._step_labels.append(lbl)

    def _build_footer(self) -> None:
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=24, pady=(0, 16))
        self.back_btn = ctk.CTkButton(footer, text="Atrás", width=120, command=self.on_back)
        self.back_btn.pack(side="left")
        self.next_btn = ctk.CTkButton(footer, text="Siguiente", width=160, command=self.on_next)
        self.next_btn.pack(side="right")

    # --- Navegación ---

    def current_view(self) -> StepView:
        i = self.wizard.index
        if i not in self._views:
            self._views[i] = self._factories[i](self.body, self.wizard.current, self)
        return self._views[i]

    def show_current(self) -> None:
        for v in self._views.values():
            v.pack_forget()
        view = self.current_view()
        view.pack(fill="both", expand=True)
        view.refresh()
        self._update_chrome(view)

    def _update_chrome(self, view: StepView) -> None:
        numbered = self.wizard.index - self._first_numbered
        for i, lbl in enumerate(self._step_labels):
            active = i == numbered
            lbl.configure(
                font=("", 12, "bold") if active else FONT_SMALL,
                text_color=("#1f6aa5", "#5fb0ff") if active else ("gray30", "gray70"),
            )
        if numbered < 0:  # pantalla de inicio: sin indicador de pasos
            self.header.pack_forget()
        else:
            self.header.pack(fill="x", padx=24, pady=(16, 0), before=self.body)
        self.back_btn.configure(state="normal" if self.wizard.can_go_back else "disabled")
        self.next_btn.configure(
            text=view.next_label, state="disabled" if self.wizard.is_last else "normal"
        )

    def update_chrome(self) -> None:
        self._update_chrome(self.current_view())

    def _on_return(self, event: Any) -> None:
        """Enter avanza el asistente, salvo que el foco esté en un campo de texto: ahí Enter
        es un salto de línea (cuerpo del correo) o una confirmación local (buscador)."""
        widget = self.focus_get()
        if widget is not None and widget.winfo_class() in TEXT_INPUT_CLASSES:
            return
        self.on_next()

    def on_next(self) -> None:
        self.current_view().commit()
        guard = self.wizard.next()
        if not guard.ok:
            if guard.confirm is not None:
                if self.confirm(guard.reason or ""):
                    guard.confirm()
                    self.on_next()
                return
            if guard.reason:
                self.show_info(guard.reason)
            return
        self.show_current()

    def on_back(self) -> None:
        self.current_view().commit()
        if self.wizard.back():
            self.show_current()

    def go_to(self, index: int) -> None:
        self.wizard.go_to(index)
        self.show_current()

    # --- Eventos de hilos ---

    def post(self, view: StepView | None, event: Any) -> None:
        """Seguro de llamar desde cualquier hilo."""
        self.events.put((view, event))

    def run_background(
        self, work: Callable[[], Any], on_done: Callable[[Any], None], *, name: str = "tarea"
    ) -> None:
        """Ejecuta `work` en un hilo y llama a `on_done(resultado)` en el hilo de Tk.
        Si `work` lanza, se registra y se muestra un error genérico (FR-003)."""

        def target() -> None:
            try:
                result = work()
            except Exception:
                log.exception("Falló una tarea en segundo plano (%s)", name)
                self.post(
                    None,
                    lambda: self.show_error(
                        "Ocurrió un error inesperado. Probá de nuevo; si se repite, enviá la "
                        "carpeta de registros a soporte."
                    ),
                )
                return
            self.post(None, lambda: on_done(result))

        threading.Thread(target=target, name=name, daemon=True).start()

    def _drain_events(self) -> None:
        try:
            while True:
                view, event = self.events.get_nowait()
                if view is None and callable(event):
                    event()
                else:
                    (view or self.current_view()).handle_event(event)
        except queue.Empty:
            pass
        finally:
            self.after(config.EVENT_POLL_MS, self._drain_events)

    # --- Recolección de basura en el hilo de la GUI ---
    #
    # Tk no es thread-safe. Si el recolector automático de Python se dispara en un hilo de
    # trabajo (motor de envío, lectura de Excel) y libera un objeto de Tk que quedó en un ciclo
    # de referencias (p. ej. una tkinter.font.Font de un widget destruido), su __del__ llama a
    # Tcl desde ese hilo y queda bloqueado. Se observó en CI de macOS: un envío trabado justo
    # después de iniciar sesión y una lectura de Excel trabada en font.__del__.
    # Por eso, mientras la ventana existe, el recolector automático se desactiva y se ejecuta
    # periódicamente acá, en el hilo de Tk. El conteo de referencias sigue liberando al
    # instante todo lo que no forma ciclos; solo los ciclos esperan hasta GC_INTERVAL_MS.

    def _collect_garbage(self) -> None:
        gc.collect()
        self.after(config.GC_INTERVAL_MS, self._collect_garbage)

    def destroy(self) -> None:
        super().destroy()
        if self._gc_was_enabled:
            gc.enable()

    # --- Diálogos ---

    def show_error(self, message: str) -> None:
        messagebox.showerror(es.APP_TITLE, message, parent=self)

    def show_info(self, message: str) -> None:
        messagebox.showinfo(es.APP_TITLE, message, parent=self)

    def confirm(self, message: str) -> bool:
        return messagebox.askyesno(es.APP_TITLE, message, parent=self)

    def report_callback_exception(self, exc, val, tb) -> None:  # noqa: N802 - API de Tk
        log.error("Error no controlado en la interfaz", exc_info=(exc, val, tb))
        self.show_error(
            "Ocurrió un error inesperado. Podés seguir usando la app; si se repite, enviá la "
            "carpeta de registros a soporte."
        )
