import pytest

from envio_correos.core.providers.base import FailureKind as K
from envio_correos.core.providers.base import ReasonCode as R
from envio_correos.core.providers.smtp_errors import Phase, classify

CASES = [
    # fase, código, texto del servidor, ReasonCode, FailureKind, smtp_code esperado
    (
        Phase.AUTH,
        535,
        "5.7.139 Authentication unsuccessful, the user credentials were incorrect.",
        R.AUTH_BAD_CREDENTIALS,
        K.ACCOUNT,
        "535 5.7.139",
    ),
    (
        Phase.AUTH,
        535,
        "5.7.8 Authentication credentials invalid",
        R.AUTH_BAD_CREDENTIALS,
        K.ACCOUNT,
        "535 5.7.8",
    ),
    (
        Phase.AUTH,
        535,
        "5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled "
        "for the Mailbox. Visit https://aka.ms/smtp_auth_disabled for more information.",
        R.AUTH_SMTP_DISABLED,
        K.ACCOUNT,
        "535 5.7.139",
    ),
    (
        Phase.AUTH,
        535,
        "5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled for the Tenant.",
        R.AUTH_SMTP_DISABLED,
        K.ACCOUNT,
        "535 5.7.139",
    ),
    (
        Phase.AUTH,
        535,
        "5.7.139 Authentication unsuccessful, user is locked by your "
        "organization's security defaults policy. Contact your administrator.",
        R.AUTH_SECURITY_DEFAULTS,
        K.ACCOUNT,
        "535 5.7.139",
    ),
    (
        Phase.AUTH,
        535,
        "5.7.139 Authentication unsuccessful, the request did not meet the "
        "criteria to be authenticated successfully.",
        R.AUTH_UNKNOWN,
        K.ACCOUNT,
        "535 5.7.139",
    ),
    (Phase.AUTH, 530, "5.7.57 Client not authenticated", R.AUTH_UNKNOWN, K.ACCOUNT, "530 5.7.57"),
    (
        Phase.AUTH,
        454,
        "4.7.0 Temporary authentication failure",
        R.THROTTLED,
        K.TRANSIENT,
        "454 4.7.0",
    ),
    (
        Phase.MAIL,
        550,
        "5.7.60 SMTP; Client does not have permissions to send as this sender",
        R.SEND_AS_DENIED,
        K.ACCOUNT,
        "550 5.7.60",
    ),
    (
        Phase.RCPT,
        550,
        "5.1.1 User unknown",
        R.RECIPIENT_REJECTED,
        K.PERMANENT_RECIPIENT,
        "550 5.1.1",
    ),
    (Phase.RCPT, 451, "4.3.2 Temporary failure", R.THROTTLED, K.TRANSIENT, "451 4.3.2"),
    (Phase.RCPT, 452, "4.5.3 Too many recipients", R.TOO_MANY_RECIPIENTS, K.TRANSIENT, "452 4.5.3"),
    (Phase.RCPT, 550, "5.5.3 Too many recipients", R.TOO_MANY_RECIPIENTS, K.TRANSIENT, "550 5.5.3"),
    (
        Phase.DATA,
        552,
        "5.3.4 Message size exceeds fixed maximum message size",
        R.MESSAGE_TOO_LARGE,
        K.SIZE,
        "552 5.3.4",
    ),
    (
        Phase.DATA,
        554,
        "5.2.0 STOREDRV.Submission.Exception:SubmissionQuotaExceededException",
        R.THROTTLED,
        K.TRANSIENT,
        "554 5.2.0",
    ),
    (
        Phase.DATA,
        432,
        "4.3.2 STOREDRV.ClientSubmit; sender thread limit exceeded",
        R.THROTTLED,
        K.TRANSIENT,
        "432 4.3.2",
    ),
    (Phase.DATA, 554, "5.6.0 Corrupt message content", R.UNKNOWN, K.UNKNOWN, "554 5.6.0"),
    (Phase.RCPT, None, "", R.UNKNOWN, K.UNKNOWN, None),
]


@pytest.mark.parametrize(("phase", "code", "text", "reason", "kind", "smtp_code"), CASES)
def test_clasificacion(phase, code, text, reason, kind, smtp_code):
    f = classify(phase, code, text)
    assert (f.code, f.kind, f.smtp_code) == (reason, kind, smtp_code)


def test_acepta_bytes_como_texto():
    f = classify(Phase.RCPT, 550, b"5.1.1 User unknown")
    assert f.code is R.RECIPIENT_REJECTED


def test_nunca_conserva_el_texto_completo_del_servidor():
    f = classify(Phase.RCPT, 550, "5.1.1 juan@empresa.com does not exist here")
    assert "juan" not in repr(f)


def test_error_de_red():
    f = classify(Phase.CONNECT, None, "")
    assert (f.code, f.kind) == (R.NETWORK, K.TRANSIENT)
