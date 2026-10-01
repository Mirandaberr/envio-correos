"""Piezas visuales compartidas entre pasos."""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from envio_correos.gui.app import FONT_BODY, FONT_SMALL, FONT_TITLE

COLOR_OK = ("#1b7f3b", "#5bd282")
COLOR_ERROR = ("#b3261e", "#ff8a80")
COLOR_WARN = ("#8a5300", "#ffcc80")
COLOR_MUTED = ("gray35", "gray70")


def title(master: Any, text: str, subtitle: str | None = None) -> None:
    ctk.CTkLabel(master, text=text, font=FONT_TITLE, anchor="w").pack(fill="x", pady=(8, 2))
    if subtitle:
        ctk.CTkLabel(
            master,
            text=subtitle,
            font=FONT_BODY,
            anchor="w",
            justify="left",
            text_color=COLOR_MUTED,
            wraplength=900,
        ).pack(fill="x", pady=(0, 12))


def message_label(master: Any) -> ctk.CTkLabel:
    return ctk.CTkLabel(master, text="", font=FONT_BODY, anchor="w", justify="left", wraplength=900)


def small_label(master: Any, text: str = "") -> ctk.CTkLabel:
    return ctk.CTkLabel(
        master,
        text=text,
        font=FONT_SMALL,
        anchor="w",
        justify="left",
        text_color=COLOR_MUTED,
        wraplength=900,
    )
