"""Tutorial de conexión y "Recordar mi cuenta" (US6, FR-012, FR-013)."""

import pytest

from envio_correos.core.providers.base import (
    ConnectionResult,
    Failure,
    FailureKind,
    ReasonCode,
)
from envio_correos.gui.presenters.account import AccountPresenter
from envio_correos.gui.presenters.base import WizardContext
from envio_correos.gui.tutorial import content
from tests.unit.test_credentials import mem  # noqa: F401 - fixture de keyring en memoria
from tests.unit.test_presenters_us1 import FakeProvider


def failing(code):
    def factory(e, pw, dn):
        return FakeProvider(e, pw, dn, ConnectionResult(False, Failure(FailureKind.ACCOUNT, code)))

    return factory


@pytest.mark.parametrize(
    ("code", "section"),
    [
        (ReasonCode.AUTH_BAD_CREDENTIALS, "password"),
        (ReasonCode.AUTH_SMTP_DISABLED, "smtp_disabled"),
        (ReasonCode.AUTH_SECURITY_DEFAULTS, "security_defaults"),
        (ReasonCode.AUTH_UNKNOWN, "password"),
        (ReasonCode.NETWORK, "network"),
        (ReasonCode.TLS_UNAVAILABLE, "network"),
        (ReasonCode.SEND_AS_DENIED, "smtp_disabled"),
    ],
)
def test_cada_error_lleva_a_su_seccion(code, section):
    p = AccountPresenter(WizardContext(), failing(code))
    p.set_fields("yo@empresa.com", "")
    p.test_connection("x")
    assert p.help_section() == section
    assert section in content.SECTIONS


def test_mensaje_para_ti(mem):  # noqa: F811
    p = AccountPresenter(WizardContext(), failing(ReasonCode.AUTH_SMTP_DISABLED))
    p.set_fields("yo@empresa.com", "")
    p.test_connection("clave-secreta")
    text = p.it_request_text()
    assert "yo@empresa.com" in text and "Authenticated SMTP" in text
    assert "clave-secreta" not in text
    assert p.needs_it()


def test_credenciales_incorrectas_no_requieren_ti():
    p = AccountPresenter(WizardContext(), failing(ReasonCode.AUTH_BAD_CREDENTIALS))
    p.set_fields("yo@empresa.com", "")
    p.test_connection("x")
    assert not p.needs_it()


def test_recordar_y_olvidar_cuenta(mem):  # noqa: F811
    from envio_correos.core import credentials

    p = AccountPresenter(WizardContext(), FakeProvider)
    p.set_fields("yo@empresa.com", "Ventas")
    p.remember = True
    assert p.test_connection("clave").ok
    assert credentials.recall("yo@empresa.com") == "clave"

    nuevo = AccountPresenter(WizardContext(), FakeProvider)
    nuevo.on_enter()
    assert nuevo.email == "yo@empresa.com" and nuevo.remembered_password == "clave"
    assert nuevo.remember

    nuevo.forget_account()
    assert credentials.recall("yo@empresa.com") is None
    assert nuevo.email == "" and nuevo.remembered_password is None


def test_sin_recordar_no_guarda(mem):  # noqa: F811
    from envio_correos.core import credentials

    p = AccountPresenter(WizardContext(), FakeProvider)
    p.set_fields("yo@empresa.com", "")
    p.test_connection("clave")
    assert credentials.recall("yo@empresa.com") is None


def test_conexion_fallida_no_guarda_aunque_se_pida_recordar(mem):  # noqa: F811
    from envio_correos.core import credentials

    p = AccountPresenter(WizardContext(), failing(ReasonCode.AUTH_BAD_CREDENTIALS))
    p.set_fields("yo@empresa.com", "")
    p.remember = True
    p.test_connection("mala")
    assert credentials.recall("yo@empresa.com") is None


def test_contenido_del_tutorial_completo():
    for key, section in content.SECTIONS.items():
        assert section.title and section.steps, key
    app = content.SECTIONS["app_password"]
    assert "organización lo permite" in app.title and "myaccount.microsoft.com" in app.steps[0]
    assert set(content.ORDER) == set(content.SECTIONS)
