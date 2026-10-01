"""Contrato SendProvider contra un servidor SMTP local (contracts/send-provider.md)."""

from email import message_from_bytes
from email.policy import default as default_policy

import pytest

from envio_correos.config import SmtpEndpoint
from envio_correos.core.providers.base import (
    Attachment,
    OutgoingMessage,
    ProviderError,
    SendProvider,
)
from envio_correos.core.providers.base import FailureKind as K
from envio_correos.core.providers.base import ReasonCode as R
from envio_correos.core.providers.m365_smtp import M365SmtpPasswordProvider
from tests.smtp_fixtures import endpoint_for

PASSWORD = "clave-de-prueba"


def provider(srv, password=PASSWORD, **kw):
    return M365SmtpPasswordProvider(srv.username, password, endpoint=endpoint_for(srv), **kw)


def msg(*to, bcc=(), **kw):
    return OutgoingMessage(to=tuple(to), bcc=tuple(bcc), subject="Asunto", body="Hola", **kw)


def test_cumple_el_protocolo(smtp_server):
    assert isinstance(provider(smtp_server), SendProvider)


def test_conexion_ok(smtp_server):
    assert provider(smtp_server).test_connection().ok


def test_credenciales_incorrectas(smtp_server):
    r = provider(smtp_server, password="mala").test_connection()
    assert not r.ok and r.failure.code is R.AUTH_BAD_CREDENTIALS and r.failure.kind is K.ACCOUNT


def test_smtp_auth_deshabilitado(smtp_server):
    smtp_server.behavior.auth_response = (
        "535 5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled for the "
        "Mailbox."
    )
    r = provider(smtp_server).test_connection()
    assert r.failure.code is R.AUTH_SMTP_DISABLED


def test_sin_starttls_no_envia_credenciales(smtp_server_sin_tls):
    r = provider(smtp_server_sin_tls).test_connection()
    assert r.failure.code is R.TLS_UNAVAILABLE
    assert smtp_server_sin_tls.auth_attempts == 0


def test_certificado_no_confiable_falla_tls(smtp_server, tmp_path):
    import trustme

    otra_ca = tmp_path / "otra-ca.pem"
    trustme.CA().cert_pem.write_to_path(str(otra_ca))  # CA que no firmó el certificado
    ep = SmtpEndpoint(smtp_server.host, smtp_server.port, otra_ca)
    p = M365SmtpPasswordProvider(smtp_server.username, PASSWORD, endpoint=ep)
    r = p.test_connection()
    assert r.failure.code is R.TLS_UNAVAILABLE
    assert smtp_server.auth_attempts == 0


def test_sin_red():
    ep = SmtpEndpoint("127.0.0.1", 1, None)
    r = M365SmtpPasswordProvider(
        "yo@empresa.com", PASSWORD, endpoint=ep, timeout=2
    ).test_connection()
    assert r.failure.code is R.NETWORK and r.failure.kind is K.TRANSIENT


def test_destinatario_rechazado_no_lanza(smtp_server):
    smtp_server.behavior.rcpt_responses["malo@x.com"] = "550 5.1.1 User unknown"
    p = provider(smtp_server)
    p.open()
    try:
        out = p.send(msg("bueno@x.com", "malo@x.com"))
    finally:
        p.close()
    assert out.accepted == ("bueno@x.com",)
    assert out.rejected["malo@x.com"].code is R.RECIPIENT_REJECTED
    assert out.rejected["malo@x.com"].smtp_code == "550 5.1.1"


def test_todos_rechazados_no_lanza(smtp_server):
    smtp_server.behavior.rcpt_responses["malo@x.com"] = "550 5.1.1 User unknown"
    out = provider(smtp_server).send(msg("malo@x.com"))
    assert out.accepted == () and set(out.rejected) == {"malo@x.com"}


def test_rechazo_temporal_es_transitorio(smtp_server):
    smtp_server.behavior.rcpt_responses["lento@x.com"] = "451 4.3.2 Try again later"
    out = provider(smtp_server).send(msg("lento@x.com"))
    assert out.rejected["lento@x.com"].kind is K.TRANSIENT


def test_mensaje_demasiado_grande(smtp_server):
    smtp_server.behavior.data_response = "552 5.3.4 Message size exceeds fixed maximum"
    out = provider(smtp_server).send(msg("a@x.com", "b@x.com"))
    assert {f.code for f in out.rejected.values()} == {R.MESSAGE_TOO_LARGE}
    assert out.accepted == ()


def test_from_es_la_cuenta_y_bcc_no_aparece_en_cabeceras(smtp_server):
    p = provider(smtp_server, display_name="Equipo Ventas")
    out = p.send(
        msg(
            smtp_server.username,
            bcc=("a@x.com", "b@x.com"),
            attachments=(Attachment("hola.txt", b"contenido", "text", "plain"),),
        )
    )
    assert set(out.accepted) == {smtp_server.username, "a@x.com", "b@x.com"}
    received = smtp_server.messages[-1]
    assert received.mail_from == smtp_server.username
    parsed = message_from_bytes(received.data, policy=default_policy)
    assert parsed["From"].addresses[0].addr_spec == smtp_server.username
    assert parsed["From"].addresses[0].display_name == "Equipo Ventas"
    assert parsed["Bcc"] is None
    assert [a.get_filename() for a in parsed.iter_attachments()] == ["hola.txt"]


def test_reconecta_si_el_servidor_corta(smtp_server):
    smtp_server.behavior.drop_connection_after_messages = 1
    p = provider(smtp_server)
    p.open()
    p.send(msg("a@x.com"))
    with pytest.raises(ProviderError) as exc:
        p.send(msg("b@x.com"))
    assert exc.value.failure.code is R.NETWORK
    out = p.send(msg("c@x.com"))  # reabre sola
    p.close()
    assert out.accepted == ("c@x.com",)


def test_la_clave_no_se_filtra(smtp_server, caplog):
    secreto = "S3cr3t-no-mostrar"
    p = provider(smtp_server, password=secreto)
    r = p.test_connection()
    assert secreto not in repr(p)
    assert secreto not in repr(r)
    assert secreto not in caplog.text


def test_cerrar_es_idempotente(smtp_server):
    p = provider(smtp_server)
    p.close()
    p.open()
    p.close()
    p.close()


def test_no_consulta_dns_inverso_al_conectar(smtp_server, monkeypatch):
    """smtplib usa socket.getfqdn() si no se le da local_hostname; eso puede colgarse."""
    import socket

    def no_dns(*a, **k):
        raise AssertionError("se llamó a socket.getfqdn()")

    monkeypatch.setattr(socket, "getfqdn", no_dns)
    assert provider(smtp_server).test_connection().ok


def test_nombre_ehlo_valido(monkeypatch):
    import socket

    from envio_correos.core.providers import m365_smtp

    monkeypatch.setattr(socket, "gethostname", lambda: "PC-DE-ANA")
    assert m365_smtp.ehlo_name() == "PC-DE-ANA"
    monkeypatch.setattr(socket, "gethostname", lambda: "nombre con espacios")
    assert m365_smtp.ehlo_name() == "localhost"
