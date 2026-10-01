"""Pantalla de inicio: reanudar (US7), descartar, reintentar anterior (US3) y borrar historial."""

import time

import pytest

from envio_correos import config
from envio_correos.core import report
from envio_correos.core.journal import AttemptState, Journal
from envio_correos.core.journal import RecipientState as S
from envio_correos.devtools.fake_smtp import DEV_PASSWORD, DEV_USER, FakeSmtpServer
from envio_correos.gui import main_window, os_open
from envio_correos.gui.presenters import recipients as recipients_presenter
from tests.gui.conftest import dump_threads
from tests.gui.test_wizard_e2e import AllDomainsOk
from tests.integration.engine_helpers import make_campaign

pytestmark = pytest.mark.slow


@pytest.fixture
def srv(monkeypatch, isolated_app_dirs):
    monkeypatch.setattr(config, "MESSAGES_PER_MINUTE", 6000)
    monkeypatch.setattr(recipients_presenter, "DomainChecker", AllDomainsOk)
    monkeypatch.setattr(os_open, "open_path", lambda p: True)
    s = FakeSmtpServer(config.dev_cert_dir()).start()
    monkeypatch.setenv(config.ENV_DEV_SMTP, f"{s.host}:{s.port}")
    yield s
    s.stop()


def crashed(journal, n_total=6, sent=3):
    cid, n = make_campaign(journal, [f"u{i}@x.com" for i in range(n_total)], account=DEV_USER)
    for seq in range(sent):
        journal.mark_result(cid, n, seq, S.SENT)
    journal.mark_sending(cid, n, sent)
    journal.mark_interrupted_running()
    return cid, n


def drive(journal, script):
    app = main_window.build(journal)
    out = {"dialogs": []}
    app.confirm = lambda m: True
    app.show_info = app.show_error = lambda m: out["dialogs"].append(m)

    def wait_until(cond, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            app.update()
            if cond():
                return
            time.sleep(0.02)
        dump_threads()
        raise TimeoutError

    def run():
        try:
            app.update()
            script(app, app.current_view(), wait_until, out)
        except Exception:  # pragma: no cover
            import traceback

            out["error"] = traceback.format_exc()
        finally:
            app.after(20, app.destroy)

    app.after(100, run)
    app.mainloop()
    assert "error" not in out, out["error"]
    return out


def connect(app, wait_until):
    v = app.current_view()
    v.email.insert(0, DEV_USER)
    v.password.insert(0, DEV_PASSWORD)
    v._test()
    wait_until(lambda: not v.presenter.testing)


def test_continuar_envio_interrumpido(srv):
    journal = Journal()
    cid, n = crashed(journal)

    def script(app, v, wait_until, out):
        out["banner"] = v.banner.winfo_ismapped() and v.banner_text.cget("text")
        out["dudosos"] = v.resend_check.winfo_ismapped()
        v._resume()
        connect(app, wait_until)
        app.on_next()  # Cuenta → directo a Envío
        out["paso"] = app.wizard.index
        wait_until(lambda: app.wizard.index == 7)
        out["resultado"] = app.current_view().presenter.breakdown()

    out = drive(journal, script)
    assert "faltan 2 correos" in out["banner"] and "no se sabe" in out["banner"]
    assert out["dudosos"]
    assert out["paso"] == 6
    assert sorted(srv.recipients()) == ["u4@x.com", "u5@x.com"]  # ni repetidos ni el dudoso
    assert out["resultado"]["Enviados"] == 5 and out["resultado"]["Pendientes"] == 1
    assert journal.unfinished_attempts() == []
    journal.close()


def test_descartar_genera_reporte_y_oculta_el_aviso(srv):
    journal = Journal()
    cid, n = crashed(journal)

    def script(app, v, wait_until, out):
        v._discard()
        app.update()
        out["banner_visible"] = v.banner.winfo_ismapped()

    out = drive(journal, script)
    assert not out["banner_visible"]
    assert journal.attempt_state(cid, n) is AttemptState.STOPPED
    assert any("correos pendientes" in d for d in out["dialogs"])
    path = journal.report_path(cid, n)
    assert path is not None and "fallidos" in path
    journal.close()


def test_reintentar_campana_anterior_desde_inicio(srv, tmp_path):
    journal = Journal()
    cid, n = make_campaign(journal, ["ok@x.com", "malo@x.com"], account=DEV_USER)
    journal.mark_result(cid, n, 0, S.SENT)
    journal.mark_result(cid, n, 1, S.FAILED, "RECIPIENT_REJECTED", "Rechazada")
    journal.set_attempt_state(cid, n, AttemptState.DONE)
    path = report.write_report(journal, cid, n, target=tmp_path / "fallidos.xlsx")

    def script(app, v, wait_until, out):
        v.load_retry(path)
        wait_until(lambda: app.wizard.index == 1)
        connect(app, wait_until)
        app.on_next()
        rv = app.current_view()
        wait_until(lambda: rv.table.tree.get_children())
        out["footer"] = rv.footer.cget("text")
        out["retry"] = app.wizard.current.ctx.retry_source.code

    out = drive(journal, script)
    assert out["footer"].startswith("Se enviará a 1")
    assert out["retry"] == f"{cid}-R2"
    journal.close()


def test_borrar_historial(srv):
    journal = Journal()
    crashed(journal)

    def script(app, v, wait_until, out):
        v._clear_history()
        app.update()
        out["banner_visible"] = v.banner.winfo_ismapped()

    out = drive(journal, script)
    assert not out["banner_visible"]
    assert journal.unfinished_attempts() == []
    assert any("Historial borrado (1 campañas)" in d for d in out["dialogs"])
    journal.close()
