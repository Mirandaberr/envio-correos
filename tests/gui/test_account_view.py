"""Vista Cuenta: ayuda por error, mensaje para TI y cuenta recordada (US6)."""

import time

import pytest

from envio_correos import config
from envio_correos.core.journal import Journal
from envio_correos.devtools.fake_smtp import DEV_PASSWORD, DEV_USER, FakeSmtpServer
from envio_correos.gui import main_window
from envio_correos.gui.presenters.base import STEP_ACCOUNT
from tests.unit.test_credentials import mem  # noqa: F401

pytestmark = pytest.mark.slow


@pytest.fixture
def srv(monkeypatch, isolated_app_dirs):
    s = FakeSmtpServer(config.dev_cert_dir()).start()
    monkeypatch.setenv(config.ENV_DEV_SMTP, f"{s.host}:{s.port}")
    yield s
    s.stop()


def drive(script):
    journal = Journal()
    app = main_window.build(journal)
    app.confirm = lambda m: True
    out = {}

    def wait_until(cond, timeout=20):
        end = time.time() + timeout
        while time.time() < end:
            app.update()
            if cond():
                return
            time.sleep(0.02)
        raise TimeoutError

    def run():
        try:
            app.go_to(STEP_ACCOUNT)
            script(app, app.current_view(), wait_until, out)
        except Exception:  # pragma: no cover
            import traceback

            out["error"] = traceback.format_exc()
        finally:
            app.after(20, app.destroy)

    app.after(100, run)
    app.mainloop()
    journal.close()
    assert "error" not in out, out["error"]
    return out


def test_smtp_deshabilitado_muestra_ayuda_y_copia_mensaje(srv, mem):  # noqa: F811
    srv.behavior.auth_response = (
        "535 5.7.139 Authentication unsuccessful, SmtpClientAuthentication is disabled for the "
        "Mailbox."
    )

    def script(app, v, wait_until, out):
        v.email.insert(0, DEV_USER)
        v.password.insert(0, DEV_PASSWORD)
        v._test()
        wait_until(lambda: not v.presenter.testing)
        app.update()
        out["help_visible"] = v.help_bar.winfo_ismapped() and v.it_btn.winfo_ismapped()
        v._copy_it()
        out["clipboard"] = app.clipboard_get()

    out = drive(script)
    assert out["help_visible"]
    assert DEV_USER in out["clipboard"] and "Authenticated SMTP" in out["clipboard"]
    assert DEV_PASSWORD not in out["clipboard"]


def test_cuenta_recordada_se_conecta_sola(srv, mem):  # noqa: F811
    from envio_correos.core import credentials

    credentials.remember(DEV_USER, DEV_PASSWORD)

    def script(app, v, wait_until, out):
        wait_until(lambda: v.presenter.connected_as is not None and not v.presenter.testing)
        out["status"] = v.status.cget("text")
        out["forget_visible"] = v.forget_btn.winfo_ismapped()
        v._forget()
        out["after_forget"] = (v.email.get(), credentials.recall(DEV_USER))

    out = drive(script)
    assert out["status"] == f"Conexión exitosa con {DEV_USER}."
    assert out["forget_visible"]
    assert out["after_forget"] == ("", None)
