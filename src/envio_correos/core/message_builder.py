"""Arma un `OutgoingMessage` por destinatario o por lote (data-model.md: MessageTemplate,
SendMode). Cada mensaje se crea justo antes de enviarse y no se retiene (research R7.4).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from envio_correos.core.providers.base import Attachment, OutgoingMessage

_LINE_BREAKS_RE = re.compile(r"[\r\n\u2028\u2029\x0b\x0c\x85]+")


def single_line(text: str) -> str:
    """Un asunto no puede tener saltos de línea (el estándar de correo lo prohíbe y Python lanza
    ValueError). Pasa si una variable trae una celda con varias líneas: se unen con espacios."""
    return _LINE_BREAKS_RE.sub(" ", text).strip()


def batches[T](items: Sequence[T], size: int) -> list[list[T]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]


class SendMode(StrEnum):
    ONE_BY_ONE = "ONE_BY_ONE"
    ALL_AT_ONCE_BCC = "ALL_AT_ONCE_BCC"
    ALL_AT_ONCE_VISIBLE = "ALL_AT_ONCE_VISIBLE"

    @property
    def is_batch(self) -> bool:
        return self is not SendMode.ONE_BY_ONE


@dataclass(frozen=True)
class AttachmentRef:
    path: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {"path": self.path, "size": self.size, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AttachmentRef:
        return cls(str(d["path"]), int(d["size"]), str(d["sha256"]))


@dataclass(frozen=True)
class MessageTemplate:
    subject: str
    body: str
    attachments: tuple[AttachmentRef, ...] = field(default_factory=tuple)


Renderer = Callable[[str, tuple[str, ...], tuple[Any, ...]], str]


def identity_render(text: str, headers: tuple[str, ...], values: tuple[Any, ...]) -> str:
    return text


class MessageBuilder:
    def __init__(
        self,
        *,
        template: MessageTemplate,
        headers: tuple[str, ...],
        sender_email: str,
        display_name: str,
        attachments: tuple[Attachment, ...] = (),
        render: Renderer = identity_render,
        mode: SendMode = SendMode.ONE_BY_ONE,
    ):
        self.template = template
        self.headers = headers
        self.sender_email = sender_email
        self.display_name = display_name
        # Los bytes de los adjuntos se comparten entre todos los mensajes (no se copian).
        self.attachments = attachments
        self.render = render
        self.mode = mode

    def for_recipient(self, address: str, values: tuple[Any, ...]) -> OutgoingMessage:
        return OutgoingMessage(
            to=(address,),
            subject=single_line(self.render(self.template.subject, self.headers, values)),
            body=self.render(self.template.body, self.headers, values),
            attachments=self.attachments,
            display_name=self.display_name,
        )

    def for_batch(self, addresses: Sequence[str]) -> OutgoingMessage:
        """Un mismo correo para varios destinatarios (sin variables, FR-042)."""
        if self.mode is SendMode.ALL_AT_ONCE_VISIBLE:
            to, bcc = tuple(addresses), ()
        else:
            to, bcc = (self.sender_email,), tuple(addresses)
        return OutgoingMessage(
            to=to,
            bcc=bcc,
            subject=single_line(self.template.subject),
            body=self.template.body,
            attachments=self.attachments,
            display_name=self.display_name,
        )
