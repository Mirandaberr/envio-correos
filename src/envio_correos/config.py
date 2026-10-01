"""Configuración central: todo límite, ruta, timeout y nombre vive acá.

Los valores de Microsoft 365 están verificados en documentación oficial; ver
specs/001-envio-masivo-correos/research.md (R1, R2). No se escriben literales de
estos valores en otros módulos.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

import platformdirs

APP_NAME = "EnvioCorreos"

# --- Microsoft 365 / SMTP AUTH (research R1) ---
SMTP_HOST = "smtp.office365.com"
SMTP_PORT = 587
SMTP_TIMEOUT_S = 30.0

# --- Límites del proveedor (research R2) ---
MESSAGES_PER_MINUTE = 30
MIN_INTERVAL_MARGIN = 1.05  # 5% de margen sobre el mínimo teórico
RECIPIENTS_PER_24H = 10_000
MAX_RECIPIENTS_PER_MESSAGE = 100  # conservador; el tenant admite hasta 1000
MAX_MESSAGE_BYTES = 35 * 1024**2  # tamaño codificado
MAX_ATTACHMENTS_RAW_BYTES = 25 * 1024**2  # base64/MIME agrega ~37% (research R2, bench 4)

# --- Reintentos de errores transitorios (research R3) ---
TRANSIENT_RETRY_DELAYS_S: tuple[float, ...] = (30.0, 120.0)

# --- Verificación de dominios (research R4) ---
DNS_TIMEOUT_S = 3.0

# --- Retención y archivos locales (FR-065, FR-077) ---
JOURNAL_RETENTION_DAYS = 30
JOURNAL_FILENAME = "campaigns.db"
DRAFT_FILENAME = "borrador.json"
LOG_FILENAME = "envio-correos.log"
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 5
MEI_ORPHAN_MAX_AGE_S = 24 * 3600

# --- UI ---
EVENT_POLL_MS = 100
SEARCH_DEBOUNCE_MS = 200

# --- Columnas que agrega la app al Excel de fallidos (contracts/failed-report-xlsx.md) ---
REPORT_SHEET_NAME = "Fallidos"
REPORT_META_SHEET_NAME = "_meta"
REPORT_FORMAT_VERSION = 1
COL_STATUS = "Estado"
COL_REASON = "Motivo"
COL_CAMPAIGN = "Código de campaña"
REPORT_APP_COLUMNS: tuple[str, ...] = (COL_STATUS, COL_REASON, COL_CAMPAIGN)
APP_ADDED_COLUMNS: frozenset[str] = frozenset(REPORT_APP_COLUMNS)
# Pistas para autodetectar la columna de correo (texto ya normalizado: minúsculas, sin tildes)
EMAIL_HEADER_HINTS: tuple[str, ...] = ("correo", "email", "e-mail", "mail")
REPORT_SUFFIX = "_fallidos_"
REPORT_TIMESTAMP_FORMAT = "%Y%m%d-%H%M"

# --- Variables de entorno ---
ENV_DATA_DIR = "ENVIO_CORREOS_DATA_DIR"  # solo tests/desarrollo
ENV_DEV_SMTP = "ENVIO_CORREOS_DEV_SMTP"  # "host:puerto" del servidor de pruebas


def min_interval_s() -> float:
    return 60.0 / MESSAGES_PER_MINUTE * MIN_INTERVAL_MARGIN


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def data_dir() -> Path:
    override = os.environ.get(ENV_DATA_DIR)
    base = Path(override) if override else Path(platformdirs.user_data_dir(APP_NAME, False))
    base.mkdir(parents=True, exist_ok=True)
    return base


def log_dir() -> Path:
    d = data_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def journal_path() -> Path:
    return data_dir() / JOURNAL_FILENAME


def draft_path() -> Path:
    return data_dir() / DRAFT_FILENAME


def dev_cert_dir() -> Path:
    d = data_dir() / "dev"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass(frozen=True)
class SmtpEndpoint:
    host: str
    port: int
    dev_ca_file: Path | None = None  # solo modo desarrollo: CA del certificado autofirmado


def smtp_endpoint() -> SmtpEndpoint:
    """Servidor de envío. El modo desarrollo solo existe fuera del ejecutable empaquetado
    y nunca desactiva la verificación TLS: confía únicamente en la CA de prueba."""
    dev = os.environ.get(ENV_DEV_SMTP)
    if dev and not is_frozen():
        host, _, port = dev.rpartition(":")
        ca = dev_cert_dir() / "ca.pem"
        return SmtpEndpoint(host or "127.0.0.1", int(port), ca)
    return SmtpEndpoint(SMTP_HOST, SMTP_PORT)
