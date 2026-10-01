"""Contenido del tutorial de conexión (FR-012, US6).

Fuentes (leídas el 2026-09-30, ver research.md R1):
- Habilitar Authenticated SMTP por buzón: learn.microsoft.com, "Enable or disable SMTP AUTH in
  Exchange Online".
- Contraseñas de aplicación: support.microsoft.com, "Create app passwords for your work or
  school account"; learn.microsoft.com, "Configure app passwords for Microsoft Entra MFA".
Los nombres de menú en español no están verificados en la interfaz real: se indica también el
nombre en inglés. Pendiente: capturas reales (quickstart Q1).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    title: str
    steps: tuple[str, ...]


SECTIONS: dict[str, Section] = {
    "password": Section(
        "¿Qué contraseña uso?",
        (
            "Usá tu correo de la empresa completo (por ejemplo, nombre@empresa.com).",
            "La contraseña es la misma con la que entrás a Outlook en el navegador.",
            "Si tu organización te pide un código del celular al iniciar sesión (verificación "
            "en dos pasos), puede que necesites una «contraseña de aplicación»: mirá la sección "
            "«Contraseña de aplicación».",
            "Si la contraseña es correcta y aun así no conecta, puede que tu organización tenga "
            "bloqueado este tipo de acceso: usá «Copiar mensaje para TI».",
        ),
    ),
    "app_password": Section(
        "Contraseña de aplicación (solo si tu organización lo permite)",
        (
            "Entrá a myaccount.microsoft.com con tu cuenta de la empresa.",
            "Elegí «Información de seguridad» (en inglés: Security info).",
            "Pulsá «Agregar método» (Add method) y elegí «Contraseña de aplicación» "
            "(App password).",
            "Si esa opción no aparece, tu organización no lo permite: pedile ayuda a TI con "
            "«Copiar mensaje para TI».",
            "Poné un nombre, por ejemplo «Envío de correos», copiá la contraseña que te muestra "
            "y pegala en esta app en lugar de tu contraseña habitual.",
        ),
    ),
    "smtp_disabled": Section(
        "Tu organización tiene deshabilitado el envío desde aplicaciones",
        (
            "Por seguridad, Microsoft 365 trae deshabilitado este tipo de envío en muchas "
            "organizaciones. No es un error tuyo.",
            "Pulsá «Copiar mensaje para TI» y envialo a tu área de sistemas: el texto ya dice "
            "exactamente qué tienen que habilitar para tu buzón (Authenticated SMTP).",
            "Cuando te confirmen, volvé a pulsar «Probar conexión».",
        ),
    ),
    "security_defaults": Section(
        "La política de seguridad de tu organización bloquea el acceso",
        (
            "Tu organización usa una configuración de seguridad (valores predeterminados de "
            "seguridad) que no permite este tipo de inicio de sesión.",
            "Solo TI puede cambiarlo. Pulsá «Copiar mensaje para TI» y envialo.",
        ),
    ),
    "network": Section(
        "No hay conexión con el servidor de correo",
        (
            "Revisá que tengas internet (por ejemplo, abriendo una página web).",
            "Si estás en la red de la empresa o con VPN, puede que bloqueen la conexión de "
            "envío de correo: consultá con TI.",
            "Volvé a pulsar «Probar conexión».",
        ),
    ),
    "windows_warning": Section(
        "Windows muestra una advertencia al abrir la app",
        (
            "La primera vez, Windows puede mostrar «Windows protegió su PC» porque la app no "
            "está firmada.",
            "Pulsá «Más información» y después «Ejecutar de todas formas».",
            "Solo hace falta la primera vez.",
        ),
    ),
}

ORDER = (
    "password",
    "app_password",
    "smtp_disabled",
    "security_defaults",
    "network",
    "windows_warning",
)
