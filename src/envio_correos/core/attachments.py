"""Adjuntos: referencias (ruta, tamaño, sha256), límite de tamaño y carga por intento.

Los bytes se leen UNA vez por intento (research R7.5): todos los destinatarios reciben la misma
versión aunque el archivo cambie en disco a mitad de campaña, y la memoria queda acotada por
MAX_ATTACHMENTS_RAW_BYTES. No se cachea la parte MIME ya codificada: ahorraría ~120 ms por
mensaje (bench 4), irrelevante frente a los 2 s entre envíos que impone el proveedor, y sumaría
una segunda copia (+37 %) en memoria.
"""

from __future__ import annotations

import hashlib
import math
import mimetypes
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from envio_correos import config
from envio_correos.core.message_builder import AttachmentRef
from envio_correos.core.providers.base import Attachment
from envio_correos.texts import es

_CHUNK = 1024 * 1024


def sha256_of(path: Path) -> str:
    """Hash por bloques de 1 MB: no carga el archivo entero en memoria."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def make_ref(path: Path) -> AttachmentRef:
    return AttachmentRef(str(path), path.stat().st_size, sha256_of(path))


@dataclass(frozen=True)
class AttachmentProblem:
    ref: AttachmentRef
    kind: str  # "missing" | "changed"


def problems(refs: Iterable[AttachmentRef]) -> list[AttachmentProblem]:
    out = []
    for ref in refs:
        p = Path(ref.path)
        if not p.is_file():
            out.append(AttachmentProblem(ref, "missing"))
        elif p.stat().st_size != ref.size or sha256_of(p) != ref.sha256:
            out.append(AttachmentProblem(ref, "changed"))
    return out


def human_size(n: int) -> str:
    if n < 1024**2:
        return f"{max(1, math.ceil(n / 1024))} KB"
    mb = round(n / 1024**2, 1)
    text = f"{mb:.1f}".replace(".", ",")
    return f"{text.removesuffix(',0')} MB"


def total_size(refs: Iterable[AttachmentRef]) -> int:
    return sum(r.size for r in refs)


def size_error(refs: Sequence[AttachmentRef], limit: int | None = None) -> str | None:
    limit = config.MAX_ATTACHMENTS_RAW_BYTES if limit is None else limit
    total = total_size(refs)
    if total <= limit:
        return None
    return es.ATTACHMENTS_TOO_BIG.format(
        total=human_size(total), limit=human_size(limit), excess=human_size(total - limit)
    )


def load_for_attempt(refs: Iterable[AttachmentRef]) -> tuple[Attachment, ...]:
    out = []
    for ref in refs:
        path = Path(ref.path)
        mime, _ = mimetypes.guess_type(path.name)
        maintype, _, subtype = (mime or "application/octet-stream").partition("/")
        out.append(Attachment(path.name, path.read_bytes(), maintype, subtype))
    return tuple(out)
