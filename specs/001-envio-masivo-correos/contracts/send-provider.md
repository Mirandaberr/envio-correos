# Contract: `SendProvider` (principio VII — autenticación desacoplada)

El motor de campañas depende **solo** de este contrato. v1 implementa
`M365SmtpPasswordProvider`; v2 podrá agregar `M365GraphOAuthProvider` sin tocar GUI, motor ni
reporte.

## Interfaz (Protocol)

```python
class SendProvider(Protocol):
    provider_id: str  # "m365-smtp-password"
    sender_email: str

    def test_connection(self) -> ConnectionResult: ...

    """Conecta, autentica y desconecta sin enviar nada (FR-011)."""

    def open(self) -> None: ...
    def close(self) -> None: ...  # idempotente

    """Sesión reutilizable durante el intento; el motor reabre si se cae."""

    def send(self, message: OutgoingMessage) -> SendOutcome: ...

    """Envía un mensaje (1 destinatario en ONE_BY_ONE, N en ALL_AT_ONCE).
    Nunca lanza por un rechazo de destinatario: lo informa en SendOutcome.
    Solo lanza ProviderError para fallos que afectan a la sesión completa."""

    @property
    def limits(self) -> ProviderLimits: ...
```

```python
@dataclass(frozen=True)
class ProviderLimits:
    min_interval_s: float  # 60 / MESSAGES_PER_MINUTE * 1.05
    recipients_per_24h: int
    max_recipients_per_message: int
    max_message_bytes: int
    max_attachments_raw_bytes: int


@dataclass(frozen=True)
class OutgoingMessage:
    to: tuple[str, ...]  # visibles (ONE_BY_ONE: 1; ALL_AT_ONCE_VISIBLE: N)
    bcc: tuple[str, ...]  # ALL_AT_ONCE_BCC: N, `to` = (sender_email,)
    subject: str
    body: str
    attachments: tuple[Attachment, ...]  # bytes leídos una vez por campaña (research R7.5)
    display_name: str


@dataclass(frozen=True)
class SendOutcome:
    accepted: tuple[str, ...]
    rejected: Mapping[str, Failure]  # dirección → motivo


@dataclass(frozen=True)
class Failure:
    kind: FailureKind  # PERMANENT_RECIPIENT | TRANSIENT | ACCOUNT | SIZE | UNKNOWN
    code: ReasonCode  # ver tabla
    smtp_code: str | None  # "550 5.1.1"; NUNCA el texto completo (puede traer PII)
```

`ConnectionResult` = `OK` | `Failure` con `kind == ACCOUNT` o `TRANSIENT`.

## Garantías

1. El `From` es siempre `sender_email`; `display_name` solo cambia el nombre visible.
2. TLS obligatorio (`starttls` con `ssl.create_default_context()`); si el servidor no ofrece
   STARTTLS, `ProviderError(ACCOUNT, TLS_UNAVAILABLE)` — nunca se envía en texto plano (principio IV).
3. La contraseña no aparece en excepciones, `repr`, logs ni en `SendOutcome`.
4. `send()` no reintenta: los reintentos y el ritmo son responsabilidad del motor.
5. El mensaje armado (`EmailMessage`) se crea dentro de `send()` y no se retiene después.

## Tabla de motivos (`ReasonCode` → texto en español)

| ReasonCode | Disparador (v1 SMTP) | Kind | Texto mostrado |
|---|---|---|---|
| `AUTH_BAD_CREDENTIALS` | 535 con "credentials were incorrect" / genérico 535 | ACCOUNT | "El correo o la contraseña no son correctos." |
| `AUTH_SMTP_DISABLED` | 535 5.7.139 con "SmtpClientAuthentication is disabled" | ACCOUNT | "Tu organización no tiene habilitado el envío desde aplicaciones para tu cuenta. Pedile a TI que lo habilite (botón: Copiar mensaje para TI)." |
| `AUTH_SECURITY_DEFAULTS` | 535 5.7.139 con "security defaults" | ACCOUNT | "La política de seguridad de tu organización bloquea este tipo de acceso. Pedile a TI que lo revise." |
| `AUTH_UNKNOWN` | otro 535 / 5.7.x en AUTH | ACCOUNT | "No se pudo iniciar sesión (código X). Revisá el tutorial o contactá a TI." |
| `TLS_UNAVAILABLE` | servidor sin STARTTLS / error de certificado | ACCOUNT | "No se pudo establecer una conexión segura con el servidor." |
| `NETWORK` | timeout, DNS, conexión rechazada/cortada | TRANSIENT | "No hay conexión con el servidor de correo. Revisá tu internet." |
| `SEND_AS_DENIED` | 5.7.60 | ACCOUNT | "Tu cuenta no tiene permiso para enviar con ese remitente." |
| `RECIPIENT_REJECTED` | 5xx en RCPT TO | PERMANENT_RECIPIENT | "El servidor rechazó esta dirección." |
| `TOO_MANY_RECIPIENTS` | 452/5.5.3 en lote | TRANSIENT | (interno: el motor divide el lote a la mitad) |
| `MESSAGE_TOO_LARGE` | 552 / 5.3.4 | SIZE | "El correo con adjuntos supera el tamaño permitido." |
| `THROTTLED` | 4xx durante envío / cuota | TRANSIENT | "Se alcanzó el límite de envío de tu cuenta. El envío se pausó." |
| `UNKNOWN` | cualquier otro | UNKNOWN | "Error inesperado (código X)." |

Las subcadenas usadas para distinguir variantes de 535 son `[NO VERIFICADO]` en docs oficiales
(research R3); viven en una tabla de datos (`smtp_errors.py`), no dispersas en el código, y se
ajustan tras quickstart Q1–Q2.

## Pruebas de contrato

Cada fila de la tabla tiene un test contra `aiosmtpd` con un handler que devuelve esa respuesta;
`M365SmtpPasswordProvider` se prueba apuntando a `127.0.0.1` con una opción de test que permite
TLS con certificado autofirmado **solo** en tests (nunca configurable desde la UI).
