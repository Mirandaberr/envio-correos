"""Variables {Columna} (FR-031, data-model.md)."""

import datetime as dt

import pytest

from envio_correos.core import template
from envio_correos.core.template import TemplateRenderer, format_value

HEADERS = ("Nombre", "Correo", "Situación", "Monto", "Alta")


def test_reemplaza_sin_distinguir_mayusculas():
    r = TemplateRenderer(HEADERS)
    assert r("Hola {nombre}, {NOMBRE}", HEADERS, ("Ana", "a@x.com", "", 0, None)) == "Hola Ana, Ana"


def test_distingue_tildes():
    assert template.unknown_variables("{Situacion}", HEADERS) == ["Situacion"]
    assert template.unknown_variables("{Situación}", HEADERS) == []


def test_llaves_literales():
    r = TemplateRenderer(HEADERS)
    assert r("{{Nombre}} es {Nombre}", HEADERS, ("Ana", "", "", 0, None)) == "{Nombre} es Ana"


def test_variable_inexistente():
    assert template.unknown_variables("Hola {Apellido} y {Nombre} y {Ciudad}", HEADERS) == [
        "Apellido",
        "Ciudad",
    ]


def test_valores_vacios_y_filas_afectadas():
    rows = [("Ana", "a", "x", 1, None), ("", "b", "x", 1, None), (None, "c", "x", 1, None)]
    r = TemplateRenderer(HEADERS)
    assert r("Hola {Nombre}!", HEADERS, rows[2]) == "Hola !"
    assert template.empty_values("Hola {Nombre} {Situación}", HEADERS, rows, [0, 1, 2]) == {
        "Nombre": [1, 2]
    }


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (None, ""),
        (1500.0, "1500"),
        (1500.5, "1500,5"),
        (42, "42"),
        (True, "Sí"),
        (dt.datetime(2026, 5, 1, 0, 0), "01/05/2026"),
        (dt.datetime(2026, 5, 1, 9, 30), "01/05/2026 09:30"),
        (dt.date(2026, 5, 1), "01/05/2026"),
        ("  texto ", "  texto "),
    ],
)
def test_formato_legible(value, text):
    assert format_value(value) == text


def test_no_expone_atributos_ni_formato():
    r = TemplateRenderer(HEADERS)
    out = r("{Nombre.__class__} {Nombre!r} {Nombre:>10}", HEADERS, ("Ana", "", "", 0, None))
    assert out == "{Nombre.__class__} {Nombre!r} {Nombre:>10}"  # no son variables válidas


def test_cache_acotada():
    r = TemplateRenderer(HEADERS)
    for i in range(50):
        r(f"texto {i} {{Nombre}}", HEADERS, ("Ana", "", "", 0, None))
    assert len(r._compiled) <= r.MAX_CACHED
