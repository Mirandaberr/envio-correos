from envio_correos.core.message_builder import MessageBuilder, MessageTemplate, SendMode
from envio_correos.core.providers.base import Attachment

HEADERS = ("Nombre", "Correo")


def builder(**kw):
    defaults = dict(
        template=MessageTemplate("Asunto", "Cuerpo"),
        headers=HEADERS,
        sender_email="yo@empresa.com",
        display_name="Equipo",
    )
    defaults.update(kw)
    return MessageBuilder(**defaults)


def test_uno_por_uno_un_destinatario_visible():
    m = builder().for_recipient("ana@x.com", ("Ana", "ana@x.com"))
    assert m.to == ("ana@x.com",) and m.bcc == ()
    assert (m.subject, m.body, m.display_name) == ("Asunto", "Cuerpo", "Equipo")


def test_usa_el_renderizador_con_los_valores_de_la_fila():
    seen = []

    def render(text, headers, values):
        seen.append((text, headers, values))
        return text.upper()

    m = builder(render=render).for_recipient("ana@x.com", ("Ana", "ana@x.com"))
    assert (m.subject, m.body) == ("ASUNTO", "CUERPO")
    assert seen[0] == ("Asunto", HEADERS, ("Ana", "ana@x.com"))


def test_adjuntos_compartidos_sin_copiar():
    att = (Attachment("a.txt", b"x" * 10),)
    b = builder(attachments=att)
    m1 = b.for_recipient("a@x.com", ("A", "a@x.com"))
    m2 = b.for_recipient("b@x.com", ("B", "b@x.com"))
    assert m1.attachments[0] is m2.attachments[0] is att[0]


def test_modo_por_defecto_es_uno_por_uno():
    assert builder().mode is SendMode.ONE_BY_ONE


def test_todos_a_la_vez_en_copia_oculta():
    b = builder(mode=SendMode.ALL_AT_ONCE_BCC)
    m = b.for_batch(["a@x.com", "b@x.com"])
    assert m.to == ("yo@empresa.com",) and m.bcc == ("a@x.com", "b@x.com")
    assert m.all_recipients == ("yo@empresa.com", "a@x.com", "b@x.com")


def test_todos_a_la_vez_visibles():
    m = builder(mode=SendMode.ALL_AT_ONCE_VISIBLE).for_batch(["a@x.com", "b@x.com"])
    assert m.to == ("a@x.com", "b@x.com") and m.bcc == ()


def test_lotes():
    from envio_correos.core.message_builder import batches

    assert batches(list(range(250)), 100) == [
        list(range(100)),
        list(range(100, 200)),
        list(range(200, 250)),
    ]
    assert batches([], 100) == []


def test_asunto_con_saltos_de_linea_queda_en_una_linea():
    from envio_correos.core.template import TemplateRenderer

    b = builder(
        template=MessageTemplate("Hola {Nombre}", "Cuerpo"), render=TemplateRenderer(HEADERS)
    )
    m = b.for_recipient("a@x.com", ("Ana\nMaría\r\nPérez", "a@x.com"))
    assert m.subject == "Hola Ana María Pérez"
    assert (
        builder(template=MessageTemplate("A\nB", "C"), mode=SendMode.ALL_AT_ONCE_BCC)
        .for_batch(["a@x.com"])
        .subject
        == "A B"
    )
