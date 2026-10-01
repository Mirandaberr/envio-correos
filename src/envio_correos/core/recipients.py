"""Lista de destinatarios: validación, duplicados, selección y búsqueda (data-model.md).

Estructuras elegidas por memoria (research R7, FR-075), no por legibilidad:
- `rows` son las tuplas de `SheetData` (no se copian).
- `selected` y `status` son `bytearray` (1 byte por fila) en vez de listas de bool/enum
  (~8 bytes por puntero + objeto) — con 5.000 filas son 10 KB en total.
- `_search_index` (una cadena normalizada por fila) se construye solo al primer uso de la
  búsqueda y se libera con `release_caches()` (FR-076).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

from envio_correos import config
from envio_correos.core.excel_reader import SheetData
from envio_correos.core.journal import RecipientRow, RecipientState
from envio_correos.texts import es

EXCLUDED_BY_USER = "EXCLUDED_BY_USER"


class ValidationStatus(IntEnum):
    VALID = 0
    INVALID_SYNTAX = 1
    INVALID_DOMAIN = 2
    MULTIPLE_ADDRESSES = 3
    EMPTY = 4
    DUPLICATE = 5
    ALREADY_SENT = 6


V = ValidationStatus
MARKABLE = frozenset({V.VALID, V.ALREADY_SENT})
INVALID = frozenset({V.INVALID_SYNTAX, V.INVALID_DOMAIN, V.MULTIPLE_ADDRESSES, V.EMPTY})

# Sintaxis práctica: parte local sin espacios, una @, dominio con al menos un punto y TLD
# alfabético de 2+ letras. No pretende cubrir todo RFC 5322, solo detectar errores de tipeo.
_EMAIL_RE = re.compile(
    r"^[^\s@<>()\[\],;:\"]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$"
)
_SEPARATORS_RE = re.compile(r"[;,\s]")
_DETECT_SAMPLE = 50


def normalize_address(raw: Any) -> str | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    local, at, domain = text.rpartition("@")
    return f"{local}@{domain.lower()}" if at else text


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.casefold())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def is_valid_syntax(address: str) -> bool:
    return bool(_EMAIL_RE.match(address))


def _classify(address: str | None) -> ValidationStatus:
    if address is None:
        return V.EMPTY
    if address.count("@") > 1 or (_SEPARATORS_RE.search(address) and "@" in address):
        return V.MULTIPLE_ADDRESSES
    return V.VALID if is_valid_syntax(address) else V.INVALID_SYNTAX


def detect_email_column(headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> int | None:
    candidates = [i for i, h in enumerate(headers) if h not in config.APP_ADDED_COLUMNS]
    for i in candidates:
        name = normalize_text(headers[i])
        if any(hint in name for hint in config.EMAIL_HEADER_HINTS):
            return i
    sample = rows[:_DETECT_SAMPLE]
    best, best_hits = None, 0
    for i in candidates:
        hits = sum(1 for r in sample if (a := normalize_address(r[i])) and is_valid_syntax(a))
        if hits > best_hits:
            best, best_hits = i, hits
    return best


@dataclass(frozen=True)
class Counts:
    total: int
    valid: int
    invalid: int
    duplicate: int
    already_sent: int
    excluded: int
    effective: int


class RecipientList:
    def __init__(
        self,
        sheet: SheetData,
        source_path: str,
        email_col: int | None = None,
        already_sent: Iterable[str] = (),
    ):
        self.sheet_name = sheet.sheet_name
        self.headers = sheet.headers
        self.rows = sheet.rows
        self.source_row_numbers = sheet.source_row_numbers
        self.source_path = source_path
        self._already_sent = {a.lower() for a in already_sent}
        n = len(self.rows)
        self.status = bytearray(n)
        self.selected = bytearray(n)
        self._search_index: list[str] | None = None
        detected = detect_email_column(self.headers, self.rows) if email_col is None else email_col
        self.email_col = detected if detected is not None else 0
        self._validate()

    @classmethod
    def from_sheet(
        cls, sheet: SheetData, source_path: str, already_sent: Iterable[str] = ()
    ) -> RecipientList:
        return cls(sheet, source_path, already_sent=already_sent)

    def __len__(self) -> int:
        return len(self.rows)

    # --- Validación ---

    def address(self, i: int) -> str | None:
        return normalize_address(self.rows[i][self.email_col])

    def _validate(self) -> None:
        seen: set[str] = set()
        for i in range(len(self.rows)):
            addr = self.address(i)
            st = _classify(addr)
            if st is V.VALID:
                key = addr.lower()  # type: ignore[union-attr]
                if key in seen:
                    st = V.DUPLICATE
                else:
                    seen.add(key)
                    if key in self._already_sent:
                        st = V.ALREADY_SENT
            self.status[i] = st
            self.selected[i] = 1 if st is V.VALID else 0

    def set_email_column(self, col: int) -> None:
        if not 0 <= col < len(self.headers):
            raise IndexError(col)
        self.email_col = col
        self._validate()

    def status_of(self, i: int) -> ValidationStatus:
        return V(self.status[i])

    def domains(self) -> set[str]:
        return {
            a.rpartition("@")[2]
            for i in range(len(self.rows))
            if self.status[i] in MARKABLE and (a := self.address(i))
        }

    def apply_invalid_domains(self, invalid: set[str]) -> int:
        changed = 0
        for i in range(len(self.rows)):
            if self.status[i] in MARKABLE:
                addr = self.address(i)
                if addr and addr.rpartition("@")[2] in invalid:
                    self.status[i] = V.INVALID_DOMAIN
                    self.selected[i] = 0
                    changed += 1
        return changed

    # --- Selección (FR-024) ---

    def is_selected(self, i: int) -> bool:
        return bool(self.selected[i])

    def is_markable(self, i: int) -> bool:
        return self.status[i] in MARKABLE

    def toggle(self, i: int) -> bool:
        if self.is_markable(i):
            self.selected[i] ^= 1
        return bool(self.selected[i])

    def set_selected(self, indices: Iterable[int], value: bool) -> None:
        for i in indices:
            if self.is_markable(i):
                self.selected[i] = 1 if value else 0

    def effective_indices(self) -> list[int]:
        return [i for i in range(len(self.rows)) if self.selected[i] and self.status[i] in MARKABLE]

    def counts(self) -> Counts:
        st, sel = self.status, self.selected
        valid = sum(1 for s in st if s == V.VALID)
        already = sum(1 for s in st if s == V.ALREADY_SENT)
        effective = sum(1 for i, s in enumerate(st) if sel[i] and s in MARKABLE)
        return Counts(
            total=len(st),
            valid=valid,
            invalid=sum(1 for s in st if s in INVALID),
            duplicate=sum(1 for s in st if s == V.DUPLICATE),
            already_sent=already,
            excluded=valid + already - effective,
            effective=effective,
        )

    # --- Búsqueda (FR-025) ---

    def _index(self) -> list[str]:
        if self._search_index is None:
            self._search_index = [
                normalize_text(" ".join("" if v is None else str(v) for v in row))
                for row in self.rows
            ]
        return self._search_index

    def search(self, query: str) -> list[int]:
        q = normalize_text(query.strip())
        if not q:
            return list(range(len(self.rows)))
        return [i for i, text in enumerate(self._index()) if q in text]

    def release_caches(self) -> None:
        self._search_index = None

    # --- Variables ---

    def variable_columns(self) -> tuple[str, ...]:
        return tuple(h for h in self.headers if h not in config.APP_ADDED_COLUMNS)

    # --- Paso al journal ---

    def to_attempt_rows(self) -> list[RecipientRow]:
        """Todas las filas, en orden: las efectivas como PENDING y el resto como SKIPPED con
        su motivo (inválida, duplicada, excluida por la usuaria) para el resumen y el reporte."""
        out: list[RecipientRow] = []
        for i, row in enumerate(self.rows):
            st = V(self.status[i])
            addr = self.address(i) or ""
            src = self.source_row_numbers[i]
            if st in MARKABLE and self.selected[i]:
                out.append(RecipientRow(src, addr, row))
            elif st in MARKABLE:
                out.append(
                    RecipientRow(
                        src,
                        addr,
                        row,
                        RecipientState.SKIPPED,
                        EXCLUDED_BY_USER,
                        es.SKIP_EXCLUDED_BY_USER,
                    )
                )
            else:
                out.append(
                    RecipientRow(
                        src, addr, row, RecipientState.SKIPPED, st.name, es.VALIDATION[st.name]
                    )
                )
        return out
