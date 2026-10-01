"""Presenters de US1 sin Tk (T030)."""

import dataclasses

import pytest

from envio_correos.core.journal import Journal, RecipientState
from envio_correos.core.message_builder import MessageTemplate, SendMode
from envio_correos.core.providers.base import (
    ConnectionResult,
    Failure,
    FailureKind,
    ProviderLimits,
    ReasonCode,
)
from envio_correos.gui.presenters.account import AccountPresenter
from envio_correos.gui.presenters.base import WizardContext
from envio_correos.gui.presenters.message import MessagePresenter, load_draft
from envio_correos.gui.presenters.mode import ModePresenter
from envio_correos.gui.presenters.recipients import RecipientsPresenter, StatusFilter
from envio_correos.gui.presenters.result import ResultPresenter
from envio_correos.gui.presenters.review import ReviewPresenter, format_duration
from envio_correos.texts import es

LIMITS = ProviderLimits(2.1, 10_000, 100, 35 * 1024**2, 25 * 1024**2)


class FakeProvider:
    provider_id = "fake"

    def __init__(self, email, password, display_name, result=None):
        self.sender_email = email
        self.result = result or ConnectionResult.success()
        self.limits = LIMITS

    def test_connection(self):
        return self.result


@pytest.fixture
def journal(tmp_path):
    j = Journal(tmp_path / "j.db")
    yield j
    j.close()


# --- Cuenta ---


def test_cuenta_no_avanza_sin_conexion_ok():
    p = AccountPresenter(WizardContext(), FakeProvider)
    p.set_fields("yo@empresa.com", "")
    assert not p.can_advance().ok


def test_cuenta_conectada_avanza_y_guarda_en_contexto():
    ctx = WizardContext()
    p = AccountPresenter(ctx, FakeProvider)
    p.set_fields(" Yo@Empresa.com ", "Ventas")
    assert p.test_connection("x").ok
    assert p.can_advance().ok
    assert (ctx.account_email, ctx.display_name) == ("Yo@empresa.com", "Ventas")
    p.set_fields("otra@empresa.com", "Ventas")
    assert not p.can_advance().ok  # cambió la cuenta: hay que volver a probar


def test_cuenta_error_mapeado_a_texto():
    failure = Failure(FailureKind.ACCOUNT, ReasonCode.AUTH_SMTP_DISABLED, "535 5.7.139")

    def factory(e, pw, dn):
        return FakeProvider(e, pw, dn, ConnectionResult(False, failure))

    p = AccountPresenter(WizardContext(), factory)
    p.set_fields("yo@empresa.com", "")
    p.test_connection("x")
    assert p.result_message() == es.REASONS["AUTH_SMTP_DISABLED"]


def test_cuenta_valida_campos():
    p = AccountPresenter(WizardContext(), FakeProvider)
    p.set_fields("no-es-correo", "")
    assert p.validate_fields("x")
    p.set_fields("yo@empresa.com", "")
    assert p.validate_fields("") == "Escribí tu contraseña."
    assert p.validate_fields("x") is None


# --- Destinatarios ---


class NoDns:
    def check_all(self, domains, progress=None, cancel=None):
        return {}


def test_destinatarios_no_avanza_sin_archivo_ni_con_cero(fixtures_dir):
    ctx = WizardContext()
    p = RecipientsPresenter(ctx, NoDns)
    assert not p.can_advance().ok
    assert p.load(fixtures_dir["lista_20"]) is None
    assert p.can_advance().ok
    p.mark_visible(False)
    assert "No hay destinatarios marcados" in p.can_advance().reason


def test_destinatarios_error_de_archivo(tmp_path):
    p = RecipientsPresenter(WizardContext(), NoDns)
    assert p.load(tmp_path / "no.xlsx") == es.FILE_NOT_FOUND


def test_destinatarios_busqueda_filtro_y_contadores(fixtures_dir):
    p = RecipientsPresenter(WizardContext(), NoDns)
    p.load(fixtures_dir["bordes"])
    p.set_query("ana")
    assert len(p.visible) == 2  # Ana y su duplicado
    p.set_query("")
    p.set_filter(StatusFilter.INVALID)
    assert len(p.visible) == 3
    assert p.footer_text().startswith("Se enviará a 4")


def test_destinatarios_dominios_invalidos(fixtures_dir):
    from envio_correos.core.domain_check import DomainStatus

    class Dns:
        def check_all(self, domains, progress=None, cancel=None):
            return {
                d: DomainStatus.NOT_FOUND if d == "empresa.con" else DomainStatus.OK
                for d in domains
            }

    p = RecipientsPresenter(WizardContext(), Dns)
    p.load(fixtures_dir["bordes"])
    assert p.check_domains(lambda d, t: None) == 1
    assert p.footer_text().startswith("Se enviará a 3")


def test_destinatarios_aviso_si_no_hay_red(fixtures_dir):
    from envio_correos.core.domain_check import DomainStatus

    class Dns:
        def check_all(self, domains, progress=None, cancel=None):
            return dict.fromkeys(domains, DomainStatus.SKIPPED)

    p = RecipientsPresenter(WizardContext(), Dns)
    p.load(fixtures_dir["lista_20"])
    p.check_domains(lambda d, t: None)
    assert p.domain_notice == es.DOMAIN_CHECK_SKIPPED


# --- Mensaje ---


def test_mensaje_asunto_vacio_pide_confirmacion(tmp_path):
    p = MessagePresenter(WizardContext(), tmp_path / "draft.json")
    p.on_enter()
    p.set_text("", "Hola")
    g = p.can_advance()
    assert not g.ok and g.confirm is not None
    g.confirm()
    assert p.can_advance().ok


def test_mensaje_sin_cuerpo_no_avanza(tmp_path):
    p = MessagePresenter(WizardContext(), tmp_path / "draft.json")
    p.on_enter()
    p.set_text("Asunto", "  ")
    assert not p.can_advance().ok


def test_mensaje_guarda_y_restaura_borrador(tmp_path):
    draft = tmp_path / "draft.json"
    ctx = WizardContext()
    p = MessagePresenter(ctx, draft)
    p.on_enter()
    p.set_text("Asunto", "Cuerpo")
    p.on_leave()
    assert ctx.template == MessageTemplate("Asunto", "Cuerpo")
    assert load_draft(draft) == MessageTemplate("Asunto", "Cuerpo")
    p2 = MessagePresenter(WizardContext(), draft)
    p2.on_enter()
    assert (p2.subject, p2.body) == ("Asunto", "Cuerpo")


# --- Modo ---


def test_modo_ninguno_preseleccionado():
    ctx = WizardContext()
    p = ModePresenter(ctx)
    assert p.selected is None and not p.can_advance().ok
    p.select(SendMode.ONE_BY_ONE)
    assert p.can_advance().ok


# --- Revisión ---


def review_ctx(journal, fixtures_dir, provider_limits=LIMITS):
    ctx = WizardContext(journal=journal)
    ctx.provider = FakeProvider("yo@empresa.com", "", "")
    ctx.provider.limits = provider_limits
    ctx.account_email, ctx.display_name = "yo@empresa.com", "Ventas"
    rp = RecipientsPresenter(ctx, NoDns)
    rp.load(fixtures_dir["lista_20"])
    ctx.template = MessageTemplate("Hola", "Cuerpo")
    ctx.mode = SendMode.ONE_BY_ONE
    return ctx


def test_revision_confirmacion_con_cantidad_modo_y_tiempo(journal, fixtures_dir):
    p = ReviewPresenter(review_ctx(journal, fixtures_dir))
    text = p.confirmation_text()
    assert "20 destinatarios" in text and "Uno por uno" in text and "menos de un minuto" in text
    g = p.can_advance()
    assert not g.ok and g.confirm is not None


def test_revision_crea_campana_al_confirmar(journal, fixtures_dir):
    ctx = review_ctx(journal, fixtures_dir)
    ctx.recipients.toggle(0)
    p = ReviewPresenter(ctx)
    p.can_advance().confirm()
    assert p.can_advance().ok
    rows = journal.recipients(ctx.campaign_id, ctx.attempt_number)
    assert len(rows) == 20
    assert sum(r.state is RecipientState.PENDING for r in rows) == 19


def test_revision_aviso_limite_diario(journal, fixtures_dir):
    limits = dataclasses.replace(LIMITS, recipients_per_24h=10)
    p = ReviewPresenter(review_ctx(journal, fixtures_dir, limits))
    assert "Hoy se enviarán 10" in p.daily_warning()
    assert p.daily_warning() in p.confirmation_text()


def test_formato_de_duracion():
    assert format_duration(10) == "menos de un minuto"
    assert format_duration(61) == "2 minutos"
    assert format_duration(0) == "menos de un minuto"
    assert format_duration(3 * 3600 + 5 * 60) == "3 h 5 min"


# --- Resultado ---


def test_resultado_desglose(journal, fixtures_dir):
    ctx = review_ctx(journal, fixtures_dir)
    ctx.recipients.toggle(0)
    ReviewPresenter(ctx).create_campaign()
    journal.mark_result(ctx.campaign_id, ctx.attempt_number, 1, RecipientState.SENT)
    journal.mark_result(ctx.campaign_id, ctx.attempt_number, 2, RecipientState.FAILED, "X")
    r = ResultPresenter(ctx)
    b = r.breakdown()
    assert (b["Enviados"], b["Fallidos"], b["Pendientes"], b["Excluidos por vos"]) == (1, 1, 17, 1)
    assert r.code == ctx.campaign_id
    assert r.notice() == es.LATE_BOUNCES_NOTICE
    r.reset_for_new_campaign()
    assert ctx.recipients is None and ctx.campaign_id is None


# --- Envío ---


class FakeRunner:
    def __init__(self, **kw):
        self.kw, self.started, self.stopped, self.alive = kw, False, False, False

    def start(self):
        self.started = self.alive = True

    def is_alive(self):
        return self.alive

    def stop(self):
        self.stopped = True


def test_envio_arranca_aplica_eventos_y_textos(journal, fixtures_dir):
    from envio_correos.core.engine import DAILY_LIMIT, Finished, Paused, Progress
    from envio_correos.core.journal import AttemptState
    from envio_correos.gui.presenters.sending import SendingPresenter

    ctx = review_ctx(journal, fixtures_dir)
    ReviewPresenter(ctx).create_campaign()
    p = SendingPresenter(ctx, FakeRunner)
    p.start(lambda e: None)
    assert p.runner.started and p.runner.kw["campaign_id"] == ctx.campaign_id
    assert not p.can_advance().ok  # en curso
    p.stop()
    assert p.runner.stopped
    p.apply(Progress(sent=5, failed=1, skipped=0, pending=14, total=20, eta_s=29.4))
    assert p.progress_fraction() == pytest.approx(0.3)
    assert "Enviados 5 · Fallidos 1 · Restantes 14" in p.progress_text()
    p.apply(Paused(DAILY_LIMIT))
    assert p.paused_text() == es.DAILY_LIMIT_REACHED
    p.runner.alive = False
    p.apply(Finished(AttemptState.DONE, {}))
    assert p.done and p.can_advance().ok


def test_resultado_genera_reporte_con_fallidos(journal, fixtures_dir, tmp_path):
    ctx = review_ctx(journal, fixtures_dir)
    ReviewPresenter(ctx).create_campaign()
    for seq in range(20):
        journal.mark_result(ctx.campaign_id, ctx.attempt_number, seq, RecipientState.SENT)
    journal.mark_result(ctx.campaign_id, ctx.attempt_number, 3, RecipientState.FAILED, "X", "x")
    r = ResultPresenter(ctx)
    r.on_enter()
    assert r.report_pending
    path = r.generate_report(tmp_path / "rep.xlsx")
    assert path.exists() and not r.report_pending
    assert journal.report_path(ctx.campaign_id, ctx.attempt_number) == str(path)
    assert path.name in r.report_text()


def test_resultado_sin_fallos_no_genera_reporte(journal, fixtures_dir):
    ctx = review_ctx(journal, fixtures_dir)
    ReviewPresenter(ctx).create_campaign()
    for seq in range(20):
        journal.mark_result(ctx.campaign_id, ctx.attempt_number, seq, RecipientState.SENT)
    r = ResultPresenter(ctx)
    r.on_enter()
    assert r.generate_report() is None
    assert r.report_text() == "No hubo fallos: no hace falta corregir nada."


def test_envio_reinicia_el_estado_en_un_intento_nuevo(journal, fixtures_dir):
    from envio_correos.core.engine import Progress
    from envio_correos.gui.presenters.sending import SendingPresenter

    ctx = review_ctx(journal, fixtures_dir)
    ReviewPresenter(ctx).create_campaign()
    p = SendingPresenter(ctx, FakeRunner)
    p.on_enter()
    p.start(lambda e: None)
    p.apply(Progress(1, 0, 0, 0, 1, 0))
    assert not p.needs_start
    p.on_enter()  # mismo intento (p. ej. redibujo): conserva el estado
    assert not p.needs_start
    ctx.attempt_number += 1  # reintento
    p.on_enter()
    assert p.needs_start and p.progress is None
