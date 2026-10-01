"""Variables {Columna} en asunto y cuerpo (FR-031, data-model.md: MessageTemplate).

Sintaxis: `{Nombre de columna}` (sin distinguir mayúsculas, sí tildes); `{{` y `}}` son llaves
literales. Parser propio en lugar de `str.format`: `format` permite `{x.__class__}` o
`{x!r}`, que expondrían atributos internos a partir de texto escrito por la usuaria.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Sequence
from typing import Any

_TOKEN_RE = re.compile(r"\{\{|\}\}|\{([^{}]+)\}")

Part = str | int  # literal o índice de columna


def find_variables(text: str) -> list[str]:
    """Nombres de variables en orden de aparición, sin repetir."""
    found: dict[str, None] = {}
    for m in _TOKEN_RE.finditer(text):
        if m.group(1) is not None:
            found.setdefault(m.group(1).strip(), None)
    return list(found)


def _column_index(headers: Sequence[str]) -> dict[str, int]:
    # casefold distingue tildes ("Situación" ≠ "Situacion") pero no mayúsculas.
    return {h.casefold(): i for i, h in enumerate(headers)}


def unknown_variables(text: str, headers: Sequence[str]) -> list[str]:
    index = _column_index(headers)
    return [v for v in find_variables(text) if v.casefold() not in index]


def compile_text(text: str, headers: Sequence[str]) -> list[Part]:
    index = _column_index(headers)
    parts: list[Part] = []
    pos = 0
    for m in _TOKEN_RE.finditer(text):
        parts.append(text[pos : m.start()])
        token = m.group(0)
        if token in ("{{", "}}"):
            parts.append(token[0])
        else:
            col = index.get(m.group(1).strip().casefold())
            parts.append(col if col is not None else token)  # desconocida: queda tal cual
        pos = m.end()
    parts.append(text[pos:])
    return [p for p in parts if p != ""]


def format_value(value: Any) -> str:
    """Valor de celda legible en español."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Sí" if value else "No"
    if isinstance(value, dt.datetime):
        if value.time() == dt.time(0, 0):
            return value.strftime("%d/%m/%Y")
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, dt.date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value).replace(".", ",")
    return str(value)


def render_parts(parts: list[Part], values: Sequence[Any]) -> str:
    return "".join(
        p if isinstance(p, str) else format_value(values[p] if p < len(values) else None)
        for p in parts
    )


class TemplateRenderer:
    """Renderiza asunto y cuerpo por destinatario. Compila cada texto una vez; la caché
    tiene tamaño acotado (FR-076): en una campaña solo hay dos textos (asunto y cuerpo)."""

    MAX_CACHED = 8

    def __init__(self, headers: Sequence[str]):
        self.headers = tuple(headers)
        self._compiled: dict[str, list[Part]] = {}

    def __call__(self, text: str, headers: Sequence[str], values: Sequence[Any]) -> str:
        parts = self._compiled.get(text)
        if parts is None:
            if len(self._compiled) >= self.MAX_CACHED:
                self._compiled.clear()
            parts = self._compiled[text] = compile_text(text, self.headers)
        return render_parts(parts, values)


def empty_values(
    text: str, headers: Sequence[str], rows: Sequence[Sequence[Any]], indices: Sequence[int]
) -> dict[str, list[int]]:
    """Para cada variable usada, las filas (de `indices`) cuyo valor queda vacío."""
    index = _column_index(headers)
    out: dict[str, list[int]] = {}
    for var in find_variables(text):
        col = index.get(var.casefold())
        if col is None:
            continue
        empty = [i for i in indices if format_value(rows[i][col]).strip() == ""]
        if empty:
            out[var] = empty
    return out
