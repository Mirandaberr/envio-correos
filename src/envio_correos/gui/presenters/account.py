"""Paso 1 — Cuenta (FR-010, FR-011, FR-014)."""

from __future__ import annotations

import logging
from collections.abc import Callable

from envio_correos import config
from envio_correos.core import credentials
from envio_correos.core.providers.base import ConnectionResult, ReasonCode, SendProvider
from envio_correos.core.providers.m365_smtp import M365SmtpPasswordProvider
from envio_correos.core.recipients import is_valid_syntax, normalize_address
from envio_correos.gui.presenters.base import STEP_SENDING, Guard, StepPresenter, WizardContext
from envio_correos.texts import es

log = logging.getLogger(__name__)

ProviderFactory = Callable[[str, str, str], SendProvider]

# Error → sección del tutorial (US6)
HELP_SECTION = {
    ReasonCode.AUTH_BAD_CREDENTIALS: "password",
    ReasonCode.AUTH_UNKNOWN: "password",
    ReasonCode.AUTH_SMTP_DISABLED: "smtp_disabled",
    ReasonCode.SEND_AS_DENIED: "smtp_disabled",
    ReasonCode.AUTH_SECURITY_DEFAULTS: "security_defaults",
    ReasonCode.NETWORK: "network",
    ReasonCode.TLS_UNAVAILABLE: "network",
}
# Errores que solo puede resolver TI
NEEDS_IT = frozenset(
    {
        ReasonCode.AUTH_SMTP_DISABLED,
        ReasonCode.AUTH_SECURITY_DEFAULTS,
        ReasonCode.SEND_AS_DENIED,
        ReasonCode.AUTH_UNKNOWN,
    }
)


def default_provider_factory(email: str, password: str, display_name: str) -> SendProvider:
    return M365SmtpPasswordProvider(email, password, display_name=display_name)


class AccountPresenter(StepPresenter):
    title = "Conectá tu cuenta de correo"

    def __init__(self, ctx: WizardContext, provider_factory: ProviderFactory | None = None):
        super().__init__(ctx)
        self._factory = provider_factory or default_provider_factory
        self.email = ""
        self.display_name = ""
        self.connected_as: str | None = None
        self.last_result: ConnectionResult | None = None
        self.testing = False
        self.remember = False
        self.remembered_password: str | None = None

    def on_enter(self) -> None:
        """Si hay una cuenta recordada, la precarga (US6-AS3)."""
        if self.connected_as or self.email:
            return
        account = credentials.remembered_account()
        if account:
            self.email = account
            self.remembered_password = credentials.recall(account)
            self.remember = self.remembered_password is not None

    def forget_account(self) -> None:
        if self.email:
            credentials.forget(self.email)
        log.info("Cuenta recordada olvidada por la usuaria")
        self.email, self.remembered_password, self.remember = "", None, False
        self.connected_as = None

    @property
    def server_label(self) -> str:
        ep = config.smtp_endpoint()
        return f"{ep.host}:{ep.port} (conexión segura)"

    def set_fields(self, email: str, display_name: str) -> None:
        email = normalize_address(email) or ""
        if email != self.connected_as:
            self.connected_as = None  # cambió la cuenta: hay que volver a probar
        self.email = email
        self.display_name = display_name.strip()

    def validate_fields(self, password: str) -> str | None:
        if not self.email or not is_valid_syntax(self.email):
            return "Escribí tu dirección de correo completa (por ejemplo, nombre@empresa.com)."
        if not password:
            return "Escribí tu contraseña."
        return None

    def test_connection(self, password: str) -> ConnectionResult:
        """Bloqueante: la vista lo llama desde un hilo de trabajo."""
        provider = self._factory(self.email, password, self.display_name)
        result = provider.test_connection()
        self.last_result = result
        if result.ok:
            self.connected_as = self.email
            self.ctx.provider = provider
            self.ctx.account_email = self.email
            self.ctx.display_name = self.display_name
            if self.remember:
                credentials.remember(self.email, password)
                self.remembered_password = password
        else:
            self.connected_as = None
        return result

    def result_message(self) -> str:
        r = self.last_result
        if r is None:
            return ""
        if r.ok:
            return f"Conexión exitosa con {self.email}."
        f = r.failure
        return es.reason_text(f.code if f else "UNKNOWN", f.smtp_code if f else None)

    # --- Ayuda (US6) ---

    def _failure_code(self) -> ReasonCode | None:
        r = self.last_result
        if r is None or r.ok or r.failure is None:
            return None
        return r.failure.code

    def help_section(self) -> str:
        code = self._failure_code()
        return HELP_SECTION.get(code, "password") if code else "password"

    def needs_it(self) -> bool:
        return self._failure_code() in NEEDS_IT

    def it_request_text(self) -> str:
        return es.IT_REQUEST_TEMPLATE.format(email=self.email or "(mi correo)")

    def next_step(self) -> int | None:
        return STEP_SENDING if self.ctx.extras.get("resume") else None

    def can_advance(self) -> Guard:
        if self.testing:
            return Guard.deny("Esperá a que termine la prueba de conexión.")
        if not self.connected_as:
            return Guard.deny("Primero probá la conexión con tu cuenta.")
        return Guard.allow()
