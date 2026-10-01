"""El núcleo no puede depender de la GUI (constitución, principio V)."""

import ast
from pathlib import Path

CORE = Path(__file__).resolve().parents[2] / "src" / "envio_correos" / "core"
FORBIDDEN = {"tkinter", "customtkinter"}


def _imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_core_no_importa_gui():
    files = list(CORE.rglob("*.py"))
    assert files, "no se encontró el núcleo"
    offenders = {
        str(f.relative_to(CORE)): sorted(
            _imported_roots(ast.parse(f.read_text(encoding="utf-8"))) & FORBIDDEN
        )
        for f in files
    }
    assert {k: v for k, v in offenders.items() if v} == {}
