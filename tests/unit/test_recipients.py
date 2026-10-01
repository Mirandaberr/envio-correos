import time

import pytest

from envio_correos.core import excel_reader
from envio_correos.core.excel_reader import SheetData
from envio_correos.core.recipients import (
    RecipientList,
    detect_email_column,
    normalize_address,
    normalize_text,
)
from envio_correos.core.recipients import (
    ValidationStatus as V,
)


def sheet(headers, rows):
    from array import array

    return SheetData(
        "Hoja", tuple(headers), [tuple(r) for r in rows], array("I", range(2, 2 + len(rows)))
    )


def test_normaliza_direccion():
    assert normalize_address("  Juan.Perez@EMPRESA.Com ") == "Juan.Perez@empresa.com"
    assert normalize_address(None) is None
    assert normalize_address("   ") is None


def test_normaliza_texto_de_busqueda():
    assert normalize_text("José BOGOTÁ") == "jose bogota"


def test_detecta_columna_por_encabezado():
    assert detect_email_column(("Nombre", "E-mail", "Ciudad"), [("a", "x@y.com", "z")]) == 1


def test_detecta_columna_por_contenido():
    rows = [("Ana", "Bogotá", "ana@x.com"), ("Luis", "Cali", "luis@x.com")]
    assert detect_email_column(("A", "B", "C"), rows) == 2


def test_no_detecta_columnas_agregadas_por_la_app():
    headers = ("Nombre", "Correo", "Estado", "Motivo", "Código de campaña")
    assert detect_email_column(headers, [("a", "a@x.com", "Fallido", "x", "C-1")]) == 1


def test_estados_de_validacion(fixtures_dir):
    lst = RecipientList.from_sheet(excel_reader.read_sheet(fixtures_dir["bordes"]), "bordes.xlsx")
    assert lst.headers[lst.email_col] == "Correo electrónico"
    statuses = [lst.status_of(i) for i in range(len(lst))]
    assert statuses == [
        V.VALID,  # ana@empresa.com
        V.DUPLICATE,  # "  ANA@Empresa.com " (mayúsculas y espacios)
        V.MULTIPLE_ADDRESSES,  # "a@x.com; b@x.com"
        V.EMPTY,
        V.INVALID_SYNTAX,  # "no-es-un-correo"
        V.VALID,  # juan@empresa.con: sintaxis válida; el dominio se verifica aparte
        V.VALID,  # fila con celda combinada en otra columna
        V.VALID,
    ]


def test_marcado_por_defecto_y_no_marcables():
    lst = RecipientList.from_sheet(
        sheet(("Correo",), [("a@x.com",), ("a@x.com",), ("malo",), (None,)]), "x.xlsx"
    )
    assert [lst.is_selected(i) for i in range(4)] == [True, False, False, False]
    assert lst.toggle(2) is False  # inválida: no se puede marcar
    assert lst.toggle(1) is False  # duplicada: no se puede marcar
    assert lst.toggle(0) is False and lst.toggle(0) is True


def test_contadores_y_efectivos():
    lst = RecipientList.from_sheet(
        sheet(("Correo",), [("a@x.com",), ("b@x.com",), ("b@x.com",), ("malo",)]), "x.xlsx"
    )
    lst.toggle(1)
    c = lst.counts()
    assert (c.total, c.valid, c.invalid, c.duplicate, c.excluded, c.effective) == (4, 2, 1, 1, 1, 1)
    assert lst.effective_indices() == [0]


def test_busqueda_sin_mayusculas_ni_tildes_en_cualquier_columna():
    lst = RecipientList.from_sheet(
        sheet(
            ("Nombre", "Correo", "Ciudad"),
            [("José", "j@x.com", "Bogotá"), ("Ana", "a@x.com", "Cali")],
        ),
        "x.xlsx",
    )
    assert lst.search("JOSE") == [0]
    assert lst.search("bogota") == [0]
    assert lst.search("@x.com") == [0, 1]
    assert lst.search("") == [0, 1]
    assert lst.search("zzz") == []


def test_busqueda_no_altera_seleccion_y_marcar_visibles():
    lst = RecipientList.from_sheet(
        sheet(
            ("Nombre", "Correo"), [("Ana", "a@x.com"), ("Beto", "b@x.com"), ("Ana B", "c@x.com")]
        ),
        "x.xlsx",
    )
    visibles = lst.search("ana")
    lst.set_selected(visibles, False)
    assert [lst.is_selected(i) for i in range(3)] == [False, True, False]
    lst.search("")
    assert [lst.is_selected(i) for i in range(3)] == [False, True, False]


def test_cambiar_columna_de_correo_revalida():
    lst = RecipientList.from_sheet(
        sheet(("Correo", "Alterno"), [("a@x.com", "malo"), ("b@x.com", "c@x.com")]), "x.xlsx"
    )
    lst.set_email_column(1)
    assert [lst.status_of(i) for i in range(2)] == [V.INVALID_SYNTAX, V.VALID]


def test_resultado_de_dominios_marca_invalidos():
    lst = RecipientList.from_sheet(sheet(("Correo",), [("a@empresa.con",), ("b@x.com",)]), "x.xlsx")
    assert lst.domains() == {"empresa.con", "x.com"}
    lst.apply_invalid_domains({"empresa.con"})
    assert lst.status_of(0) is V.INVALID_DOMAIN and not lst.is_selected(0)
    assert lst.status_of(1) is V.VALID


def test_ya_enviados_desmarcados_pero_marcables():
    lst = RecipientList.from_sheet(
        sheet(("Correo",), [("a@x.com",), ("b@x.com",)]), "x.xlsx", already_sent={"a@x.com"}
    )
    assert lst.status_of(0) is V.ALREADY_SENT and not lst.is_selected(0)
    assert lst.toggle(0) is True
    assert lst.effective_indices() == [0, 1]


def test_variables_excluyen_columnas_de_la_app():
    lst = RecipientList.from_sheet(
        sheet(("Nombre", "Correo", "Estado", "Motivo"), [("a", "a@x.com", "Fallido", "x")]),
        "x.xlsx",
    )
    assert lst.variable_columns() == ("Nombre", "Correo")


def test_liberar_caches():
    lst = RecipientList.from_sheet(sheet(("Correo",), [("a@x.com",)]), "x.xlsx")
    lst.search("a")
    lst.release_caches()
    assert lst._search_index is None


@pytest.mark.parametrize("query", ["jose", "user12", "bogota", ""])
def test_rendimiento_busqueda_5000(fixtures_dir, query):
    lst = RecipientList.from_sheet(excel_reader.read_sheet(fixtures_dir["lista_5000"]), "x.xlsx")
    lst.search("precalentar")  # el índice se construye una vez
    t = time.perf_counter()
    lst.search(query)
    assert time.perf_counter() - t < 0.5  # SC-010


def test_filas_para_el_journal_incluyen_omitidas_con_motivo():
    from envio_correos.core.journal import RecipientState as S
    from envio_correos.texts import es

    lst = RecipientList.from_sheet(
        sheet(("Correo",), [("a@x.com",), ("b@x.com",), ("a@x.com",), ("malo",)]), "x.xlsx"
    )
    lst.toggle(1)
    rows = lst.to_attempt_rows()
    assert [(r.state, r.reason_code) for r in rows] == [
        (S.PENDING, None),
        (S.SKIPPED, "EXCLUDED_BY_USER"),
        (S.SKIPPED, "DUPLICATE"),
        (S.SKIPPED, "INVALID_SYNTAX"),
    ]
    assert rows[1].reason_text == es.SKIP_EXCLUDED_BY_USER
    assert [r.source_row for r in rows] == [2, 3, 4, 5]
    assert rows[0].values == ("a@x.com",)
