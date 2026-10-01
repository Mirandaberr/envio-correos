from envio_correos.core.providers.base import ReasonCode
from envio_correos.texts import es


def test_todo_reason_code_tiene_texto():
    assert {c.value for c in ReasonCode} <= set(es.REASONS)


def test_reason_text_interpola_codigo():
    assert "535 5.7.3" in es.reason_text("AUTH_UNKNOWN", "535 5.7.3")
    assert es.reason_text("NO_EXISTE") == es.REASONS["UNKNOWN"].format(code="?")
