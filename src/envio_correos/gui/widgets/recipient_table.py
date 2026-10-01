"""Tabla de destinatarios con casillas (FR-022, FR-024).

`ttk.Treeview` (biblioteca estándar) porque CustomTkinter no tiene tabla. Los ítems se crean
una sola vez por archivo; la búsqueda y los filtros usan `detach`/`reattach`, que no recrea
widgets (research R5, bench 2: ≤ 0,09 s con 5.000 filas).
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from envio_correos.core.recipients import RecipientList

CHECKED, UNCHECKED, LOCKED = "☑", "☐", "—"
_INACTIVE_TAG = "inactiva"


def _cell(v: Any) -> str:
    if v is None:
        return ""
    if hasattr(v, "strftime"):
        return v.strftime("%d/%m/%Y %H:%M") if hasattr(v, "hour") else v.strftime("%d/%m/%Y")
    return str(v)


class RecipientTable(ttk.Frame):
    def __init__(
        self,
        master: Any,
        status_text: Callable[[int], str],
        on_toggle: Callable[[int], None],
    ):
        super().__init__(master)
        self._status_text = status_text
        self._on_toggle = on_toggle
        self._lst: RecipientList | None = None
        style = ttk.Style(self)
        style.configure("Destinatarios.Treeview", rowheight=26, font=("", 12))
        style.configure("Destinatarios.Treeview.Heading", font=("", 12, "bold"))
        self.tree = ttk.Treeview(
            self, show="headings", style="Destinatarios.Treeview", selectmode="browse"
        )
        ysb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        xsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ysb.set, xscrollcommand=xsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.tag_configure(_INACTIVE_TAG, foreground="gray50")
        self.tree.bind("<Button-1>", self._on_click)
        self.tree.bind("<space>", self._on_space)

    def load(self, lst: RecipientList) -> None:
        self._lst = lst
        self.tree.delete(*self.tree.get_children())
        cols = ("_sel", "_estado", *[f"c{i}" for i in range(len(lst.headers))])
        self.tree.configure(columns=cols)
        self.tree.heading("_sel", text="Enviar")
        self.tree.column("_sel", width=60, anchor="center", stretch=False)
        self.tree.heading("_estado", text="Estado")
        self.tree.column("_estado", width=220, stretch=False)
        for i, h in enumerate(lst.headers):
            self.tree.heading(f"c{i}", text=h)
            self.tree.column(f"c{i}", width=160, stretch=True)
        for i, row in enumerate(lst.rows):
            self.tree.insert(
                "",
                "end",
                iid=str(i),
                values=self._values(i, row),
                tags=() if lst.is_markable(i) else (_INACTIVE_TAG,),
            )

    def _mark(self, i: int) -> str:
        assert self._lst is not None
        if not self._lst.is_markable(i):
            return LOCKED
        return CHECKED if self._lst.is_selected(i) else UNCHECKED

    def _values(self, i: int, row: tuple[Any, ...]) -> tuple[str, ...]:
        return (self._mark(i), self._status_text(i), *(_cell(v) for v in row))

    def refresh_rows(self, indices: list[int] | None = None) -> None:
        """Actualiza casilla, estado y estilo (tras marcar o verificar dominios)."""
        if self._lst is None:
            return
        idx = range(len(self._lst.rows)) if indices is None else indices
        for i in idx:
            self.tree.item(
                str(i),
                values=self._values(i, self._lst.rows[i]),
                tags=() if self._lst.is_markable(i) else (_INACTIVE_TAG,),
            )

    def show_only(self, visible: list[int]) -> None:
        self.tree.detach(*self.tree.get_children())
        for pos, i in enumerate(visible):
            self.tree.reattach(str(i), "", pos)
        # Con teclado: que haya siempre una fila con foco para usar flechas y Espacio.
        if visible and self.tree.focus() not in {str(i) for i in visible[:1]} | set(
            self.tree.get_children()
        ):
            self.tree.focus(str(visible[0]))

    def _toggle_iid(self, iid: str) -> None:
        if iid:
            i = int(iid)
            self._on_toggle(i)
            self.refresh_rows([i])

    def _on_click(self, event: tk.Event) -> None:
        if self.tree.identify_column(event.x) == "#1":
            self._toggle_iid(self.tree.identify_row(event.y))

    def _on_space(self, _event: tk.Event) -> str:
        self._toggle_iid(self.tree.focus())
        return "break"
