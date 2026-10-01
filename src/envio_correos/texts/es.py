"""Todos los textos visibles para la usuaria (FR-002, FR-003).

Regla: cada mensaje de error dice qué pasó y qué puede hacer. Sin jerga técnica en el flujo
principal. Las vistas nunca escriben strings sueltos: los toman de acá.
"""

from __future__ import annotations

APP_TITLE = "Envío de correos"

STEPS = ("Cuenta", "Destinatarios", "Mensaje", "Modo de envío", "Revisión", "Envío", "Resultado")

# --- Motivos de fallo del proveedor (contracts/send-provider.md) ---
REASONS: dict[str, str] = {
    "AUTH_BAD_CREDENTIALS": "El correo o la contraseña no son correctos.",
    "AUTH_SMTP_DISABLED": (
        "Tu organización no tiene habilitado el envío desde aplicaciones para tu cuenta. "
        "Pedile a TI que lo habilite (podés usar el botón «Copiar mensaje para TI»)."
    ),
    "AUTH_SECURITY_DEFAULTS": (
        "La política de seguridad de tu organización bloquea este tipo de acceso. "
        "Pedile a TI que lo revise."
    ),
    "AUTH_UNKNOWN": (
        "No se pudo iniciar sesión (código {code}). Revisá el tutorial o contactá a TI."
    ),
    "TLS_UNAVAILABLE": "No se pudo establecer una conexión segura con el servidor de correo.",
    "NETWORK": "No hay conexión con el servidor de correo. Revisá tu conexión a internet.",
    "SEND_AS_DENIED": "Tu cuenta no tiene permiso para enviar con ese remitente.",
    "RECIPIENT_REJECTED": "El servidor rechazó esta dirección.",
    "TOO_MANY_RECIPIENTS": "Demasiados destinatarios en un mismo correo.",
    "MESSAGE_TOO_LARGE": "El correo con adjuntos supera el tamaño permitido.",
    "THROTTLED": "Se alcanzó el límite de envío de tu cuenta. El envío se pausó.",
    "UNKNOWN": "Error inesperado (código {code}).",
}

# --- Estados de validación de destinatarios (data-model.md) ---
VALIDATION: dict[str, str] = {
    "VALID": "Válido",
    "INVALID_SYNTAX": "La dirección de correo no es válida.",
    "INVALID_DOMAIN": "El dominio no existe o no recibe correos.",
    "MULTIPLE_ADDRESSES": "Hay más de una dirección en la celda; dejá una sola por fila.",
    "EMPTY": "La celda de correo está vacía.",
    "DUPLICATE": "Dirección repetida: se envía una sola vez.",
    "ALREADY_SENT": "Ya enviado en esta campaña.",
}

# --- Motivos de omisión y estados del reporte ---
SKIP_EXCLUDED_BY_USER = "Excluido por el usuario"
SKIP_STOPPED_BY_USER = "Detenido por el usuario"
SKIP_INTERRUPTED = "El envío se interrumpió antes de llegar a esta dirección."
PENDING_PAUSED = "El envío quedó en pausa antes de llegar a esta dirección."
UNKNOWN_IF_SENT = "No se sabe si se envió (la app se cerró justo durante el envío)."

REPORT_STATUS_FAILED = "Fallido"
REPORT_STATUS_INVALID = "Inválido"
REPORT_STATUS_PENDING = "Pendiente"
REPORT_STATUS_UNKNOWN = "No se sabe si se envió"

# --- Errores de archivos ---
FILE_LOCKED = "El archivo está abierto en otro programa. Cerralo y volvé a intentar."
FILE_NOT_FOUND = "No se encontró el archivo. Revisá que no se haya movido o borrado."
FILE_FORMAT_XLS = (
    "Este archivo está en un formato antiguo de Excel (.xls). Abrilo en Excel y usá "
    "«Guardar como» → «Libro de Excel (.xlsx)»."
)
FILE_FORMAT_CSV = (
    "Este archivo es .csv. Abrilo en Excel y usá «Guardar como» → «Libro de Excel (.xlsx)»."
)
FILE_PROTECTED = (
    "El archivo está protegido con contraseña. Quitale la protección en Excel y guardalo de nuevo."
)
FILE_UNREADABLE = "No se pudo leer el archivo como Excel (.xlsx)."
FILE_NO_DATA = "El archivo no tiene filas con datos."

# --- Avisos ---
DOMAIN_CHECK_SKIPPED = (
    "No se pudieron verificar los dominios porque no hay conexión a internet. "
    "Se enviará igual; los errores de dominio aparecerán como rebotes en tu bandeja."
)
LATE_BOUNCES_NOTICE = (
    "Importante: si alguna dirección no existe, el aviso de rebote puede llegar más tarde a tu "
    "bandeja de entrada y no aparece en este resumen."
)
DAILY_LIMIT_WARNING = (
    "Tu cuenta puede enviar a {limit} destinatarios por día. En las últimas 24 horas ya "
    "enviaste a {sent}. Hoy se enviarán {today}; el resto quedará pendiente para continuar luego."
)
DAILY_LIMIT_REACHED = (
    "Se alcanzó el límite diario de envío de tu cuenta. Los correos restantes quedaron "
    "pendientes: podés continuar mañana."
)
ATTACHMENTS_TOO_BIG = (
    "Los adjuntos suman {total}. El máximo es {limit}: reducí {excess} para poder continuar."
)

IT_REQUEST_TEMPLATE = (
    "Hola, necesito enviar correos desde una aplicación de escritorio con mi cuenta {email}. "
    "¿Podrían habilitar «Authenticated SMTP» (SMTP AUTH) para mi buzón en el Centro de "
    "administración de Microsoft 365 (Usuarios > Usuarios activos > Correo > Administrar "
    "aplicaciones de correo)? Gracias."
)


def reason_text(code: str, smtp_code: str | None = None) -> str:
    return REASONS.get(code, REASONS["UNKNOWN"]).format(code=smtp_code or "?")
