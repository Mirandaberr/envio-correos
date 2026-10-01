"""Journal persistente de campañas (data-model.md, research R6, constitución III).

Cada transición de un destinatario se confirma (commit) al instante: un cierre inesperado deja
en disco qué se envió, qué falló y qué estaba en vuelo (`SENDING`). SQLite en modo WAL.

Una sola conexión compartida por el hilo de la GUI y el del motor, serializada con un lock:
el volumen es bajo (≤ 30 escrituras/min por el límite del proveedor) y así se evita la
complejidad de una conexión por hilo.
"""

from __future__ import annotations

import datetime as dt
import json
import secrets
import sqlite3
import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from envio_correos import config
from envio_correos.texts import es

_SCHEMA = """
CREATE TABLE IF NOT EXISTS campaign (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    account_email TEXT NOT NULL,
    source_path TEXT NOT NULL,
    sheet_name TEXT NOT NULL,
    headers_json TEXT NOT NULL,
    email_col INTEGER NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    attachments_json TEXT NOT NULL,
    mode TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attempt (
    campaign_id TEXT NOT NULL REFERENCES campaign(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    state TEXT NOT NULL,
    report_path TEXT,
    headers_json TEXT,
    PRIMARY KEY (campaign_id, number)
);
CREATE TABLE IF NOT EXISTS recipient (
    campaign_id TEXT NOT NULL,
    attempt_number INTEGER NOT NULL,
    row_seq INTEGER NOT NULL,
    source_row INTEGER NOT NULL,
    address TEXT NOT NULL,
    row_values_json TEXT NOT NULL,
    state TEXT NOT NULL,
    reason_code TEXT,
    reason_text TEXT,
    smtp_code TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (campaign_id, attempt_number, row_seq),
    FOREIGN KEY (campaign_id, attempt_number) REFERENCES attempt(campaign_id, number)
        ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS ix_recipient_address ON recipient(campaign_id, address, state);
CREATE INDEX IF NOT EXISTS ix_recipient_state_time ON recipient(state, updated_at);
"""


class RecipientState(StrEnum):
    PENDING = "PENDING"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class AttemptState(StrEnum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    INTERRUPTED = "INTERRUPTED"
    DONE = "DONE"


@dataclass(frozen=True)
class CampaignSpec:
    account_email: str
    source_path: str
    sheet_name: str
    headers: tuple[str, ...]
    email_col: int
    subject: str
    body: str
    attachments: tuple[dict[str, Any], ...]
    mode: str


@dataclass(frozen=True)
class StoredCampaign:
    id: str
    created_at: dt.datetime
    spec: CampaignSpec


@dataclass(frozen=True)
class RecipientRow:
    source_row: int
    address: str
    values: tuple[Any, ...]
    state: RecipientState = RecipientState.PENDING
    reason_code: str | None = None
    reason_text: str | None = None


@dataclass(frozen=True)
class StoredRecipient:
    row_seq: int
    source_row: int
    address: str
    values: tuple[Any, ...]
    state: RecipientState
    reason_code: str | None
    reason_text: str | None
    smtp_code: str | None


@dataclass(frozen=True)
class UnfinishedAttempt:
    campaign_id: str
    number: int
    state: AttemptState
    pending: int
    unknown: int  # SENDING: se cortó justo durante el envío ("no se sabe si se envió")
    account_email: str
    started_at: str


INTERRUPTED_CODE = "INTERRUPTED"


def attempt_code(campaign_id: str, number: int) -> str:
    return campaign_id if number == 1 else f"{campaign_id}-R{number}"


# --- Serialización de valores de celdas conservando tipos (SC-005) ---

_TAGS: tuple[tuple[type, str], ...] = (
    (dt.datetime, "__dt__"),  # datetime antes que date: es subclase
    (dt.date, "__d__"),
    (dt.time, "__t__"),
)


def _encode(value: Any) -> Any:
    for typ, tag in _TAGS:
        if isinstance(value, typ):
            return {tag: value.isoformat()}
    if isinstance(value, dt.timedelta):
        return {"__td__": value.total_seconds()}
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict) and len(value) == 1:
        ((tag, raw),) = value.items()
        if tag == "__dt__":
            return dt.datetime.fromisoformat(raw)
        if tag == "__d__":
            return dt.date.fromisoformat(raw)
        if tag == "__t__":
            return dt.time.fromisoformat(raw)
        if tag == "__td__":
            return dt.timedelta(seconds=raw)
    return value


def dump_values(values: Iterable[Any]) -> str:
    return json.dumps([_encode(v) for v in values], ensure_ascii=False, default=str)


def load_values(raw: str) -> tuple[Any, ...]:
    return tuple(_decode(v) for v in json.loads(raw))


def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


class Journal:
    def __init__(self, path: Path | None = None, *, clock: Callable[[], dt.datetime] = _utc_now):
        self._path = path or config.journal_path()
        self._clock = clock
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self._path, check_same_thread=False, isolation_level=None)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(_SCHEMA)

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _now(self) -> str:
        return self._clock().isoformat()

    def _tx(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._db.execute(sql, tuple(params))

    # --- Campañas ---

    def create_campaign(self, spec: CampaignSpec) -> str:
        with self._lock:
            while True:
                cid = f"C-{secrets.token_hex(2).upper()}"
                if not self._tx("SELECT 1 FROM campaign WHERE id=?", (cid,)).fetchone():
                    break
            self._tx(
                "INSERT INTO campaign VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    cid,
                    self._now(),
                    spec.account_email.lower(),
                    spec.source_path,
                    spec.sheet_name,
                    json.dumps(list(spec.headers), ensure_ascii=False),
                    spec.email_col,
                    spec.subject,
                    spec.body,
                    json.dumps(list(spec.attachments), ensure_ascii=False),
                    spec.mode,
                ),
            )
            return cid

    def get_campaign(self, campaign_id: str) -> StoredCampaign | None:
        row = self._tx("SELECT * FROM campaign WHERE id=?", (campaign_id,)).fetchone()
        if row is None:
            return None
        spec = CampaignSpec(
            account_email=row["account_email"],
            source_path=row["source_path"],
            sheet_name=row["sheet_name"],
            headers=tuple(json.loads(row["headers_json"])),
            email_col=row["email_col"],
            subject=row["subject"],
            body=row["body"],
            attachments=tuple(json.loads(row["attachments_json"])),
            mode=row["mode"],
        )
        return StoredCampaign(row["id"], dt.datetime.fromisoformat(row["created_at"]), spec)

    # --- Intentos ---

    def start_attempt(
        self,
        campaign_id: str,
        recipients: Iterable[RecipientRow],
        headers: tuple[str, ...] | None = None,
    ) -> int:
        """Crea el intento siguiente e inserta todos sus destinatarios en UNA transacción
        (5.000 inserts individuales con commit serían ~100× más lentos)."""
        now = self._now()
        with self._lock:
            self._db.execute("BEGIN")
            try:
                number = self._next_attempt_number(campaign_id)
                self._db.execute(
                    "INSERT INTO attempt (campaign_id, number, started_at, state, headers_json) "
                    "VALUES (?,?,?,?,?)",
                    (
                        campaign_id,
                        number,
                        now,
                        AttemptState.RUNNING,
                        json.dumps(list(headers), ensure_ascii=False) if headers else None,
                    ),
                )
                self._db.executemany(
                    "INSERT INTO recipient (campaign_id, attempt_number, row_seq, source_row, "
                    "address, row_values_json, state, reason_code, reason_text, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        (
                            campaign_id,
                            number,
                            seq,
                            r.source_row,
                            r.address,
                            dump_values(r.values),
                            r.state,
                            r.reason_code,
                            r.reason_text,
                            now,
                        )
                        for seq, r in enumerate(recipients)
                    ),
                )
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return number

    def _next_attempt_number(self, campaign_id: str) -> int:
        row = self._db.execute(
            "SELECT COALESCE(MAX(number), 0) FROM attempt WHERE campaign_id=?", (campaign_id,)
        ).fetchone()
        return row[0] + 1

    def latest_attempt(self, campaign_id: str) -> int | None:
        row = self._tx(
            "SELECT MAX(number) FROM attempt WHERE campaign_id=?", (campaign_id,)
        ).fetchone()
        return row[0]

    def set_attempt_state(
        self, campaign_id: str, number: int, state: AttemptState, report_path: str | None = None
    ) -> None:
        finished = self._now() if state in (AttemptState.DONE, AttemptState.STOPPED) else None
        self._tx(
            "UPDATE attempt SET state=?, finished_at=COALESCE(?, finished_at), "
            "report_path=COALESCE(?, report_path) WHERE campaign_id=? AND number=?",
            (state, finished, report_path, campaign_id, number),
        )

    def attempt_headers(self, campaign_id: str, number: int) -> tuple[str, ...]:
        """Encabezados del archivo de ese intento (un reintento usa el Excel de fallidos, cuyas
        columnas pueden diferir de las de la campaña original)."""
        row = self._tx(
            "SELECT a.headers_json, c.headers_json FROM attempt a JOIN campaign c "
            "ON c.id = a.campaign_id WHERE a.campaign_id=? AND a.number=?",
            (campaign_id, number),
        ).fetchone()
        if row is None:
            return ()
        return tuple(json.loads(row[0] or row[1]))

    def set_report_path(self, campaign_id: str, number: int, report_path: str) -> None:
        self._tx(
            "UPDATE attempt SET report_path=? WHERE campaign_id=? AND number=?",
            (report_path, campaign_id, number),
        )

    def attempt_state(self, campaign_id: str, number: int) -> AttemptState | None:
        row = self._tx(
            "SELECT state FROM attempt WHERE campaign_id=? AND number=?", (campaign_id, number)
        ).fetchone()
        return AttemptState(row[0]) if row else None

    def report_path(self, campaign_id: str, number: int) -> str | None:
        row = self._tx(
            "SELECT report_path FROM attempt WHERE campaign_id=? AND number=?",
            (campaign_id, number),
        ).fetchone()
        return row[0] if row else None

    # --- Destinatarios ---

    def mark_sending(self, campaign_id: str, number: int, row_seq: int) -> None:
        self.mark_result(campaign_id, number, row_seq, RecipientState.SENDING)

    def mark_result(
        self,
        campaign_id: str,
        number: int,
        row_seq: int,
        state: RecipientState,
        reason_code: str | None = None,
        reason_text: str | None = None,
        smtp_code: str | None = None,
    ) -> None:
        self._tx(
            "UPDATE recipient SET state=?, reason_code=?, reason_text=?, smtp_code=?, "
            "updated_at=? WHERE campaign_id=? AND attempt_number=? AND row_seq=?",
            (state, reason_code, reason_text, smtp_code, self._now(), campaign_id, number, row_seq),
        )

    def recipients(
        self, campaign_id: str, number: int, states: set[RecipientState] | None = None
    ) -> list[StoredRecipient]:
        sql = "SELECT * FROM recipient WHERE campaign_id=? AND attempt_number=?"
        params: list[Any] = [campaign_id, number]
        if states:
            sql += f" AND state IN ({','.join('?' * len(states))})"
            params += sorted(states)
        rows = self._tx(sql + " ORDER BY row_seq", params).fetchall()
        return [
            StoredRecipient(
                r["row_seq"],
                r["source_row"],
                r["address"],
                load_values(r["row_values_json"]),
                RecipientState(r["state"]),
                r["reason_code"],
                r["reason_text"],
                r["smtp_code"],
            )
            for r in rows
        ]

    def counts(self, campaign_id: str, number: int) -> dict[str, int]:
        rows = self._tx(
            "SELECT state, COUNT(*) FROM recipient WHERE campaign_id=? AND attempt_number=? "
            "GROUP BY state",
            (campaign_id, number),
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    def sent_last_24h(self, account_email: str) -> int:
        since = (self._clock() - dt.timedelta(hours=24)).isoformat()
        row = self._tx(
            "SELECT COUNT(*) FROM recipient r JOIN campaign c ON c.id = r.campaign_id "
            "WHERE c.account_email=? AND r.state=? AND r.updated_at>=?",
            (account_email.lower(), RecipientState.SENT, since),
        ).fetchone()
        return row[0]

    def already_sent_addresses(self, campaign_id: str) -> set[str]:
        rows = self._tx(
            "SELECT DISTINCT lower(address) FROM recipient WHERE campaign_id=? AND state=?",
            (campaign_id, RecipientState.SENT),
        ).fetchall()
        return {r[0] for r in rows}

    # --- Reanudación (US7) ---

    def mark_interrupted_running(self) -> int:
        """Al iniciar la app: un intento RUNNING solo puede ser de una ejecución que se cortó."""
        cur = self._tx(
            "UPDATE attempt SET state=? WHERE state=?",
            (AttemptState.INTERRUPTED, AttemptState.RUNNING),
        )
        return cur.rowcount

    def unfinished_attempts(self) -> list[UnfinishedAttempt]:
        rows = self._tx(
            "SELECT a.campaign_id, a.number, a.state, a.started_at, c.account_email, "
            "SUM(r.state=?) AS pending, SUM(r.state=?) AS unknown "
            "FROM attempt a JOIN campaign c ON c.id=a.campaign_id "
            "JOIN recipient r ON r.campaign_id=a.campaign_id AND r.attempt_number=a.number "
            "WHERE a.state IN (?, ?) GROUP BY a.campaign_id, a.number "
            "HAVING pending + unknown > 0 ORDER BY a.started_at DESC",
            (
                RecipientState.PENDING,
                RecipientState.SENDING,
                AttemptState.INTERRUPTED,
                AttemptState.PAUSED,
            ),
        ).fetchall()
        return [
            UnfinishedAttempt(
                r["campaign_id"],
                r["number"],
                AttemptState(r["state"]),
                r["pending"],
                r["unknown"],
                r["account_email"],
                r["started_at"],
            )
            for r in rows
        ]

    def requeue_unknown(self, campaign_id: str, number: int) -> int:
        """La usuaria decide reenviar a los dudosos: SENDING → PENDING."""
        cur = self._tx(
            "UPDATE recipient SET state=?, updated_at=? WHERE campaign_id=? AND "
            "attempt_number=? AND state=?",
            (RecipientState.PENDING, self._now(), campaign_id, number, RecipientState.SENDING),
        )
        return cur.rowcount

    def discard_attempt(self, campaign_id: str, number: int) -> None:
        """ "Descartar": los pendientes quedan omitidos por interrupción (van al reporte)."""
        self._tx(
            "UPDATE recipient SET state=?, reason_code=?, reason_text=?, updated_at=? "
            "WHERE campaign_id=? AND attempt_number=? AND state=?",
            (
                RecipientState.SKIPPED,
                INTERRUPTED_CODE,
                es.SKIP_INTERRUPTED,
                self._now(),
                campaign_id,
                number,
                RecipientState.PENDING,
            ),
        )
        self.set_attempt_state(campaign_id, number, AttemptState.STOPPED)

    # --- Retención (FR-065, FR-077) ---

    def purge(self, older_than_days: int = config.JOURNAL_RETENTION_DAYS) -> int:
        cutoff = (self._clock() - dt.timedelta(days=older_than_days)).isoformat()
        with self._lock:
            ids = [
                r[0]
                for r in self._db.execute("SELECT id FROM campaign WHERE created_at<?", (cutoff,))
            ]
            self._db.execute("BEGIN")
            try:
                for cid in ids:
                    self._delete(cid)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise
            return len(ids)

    def delete_campaign(self, campaign_id: str) -> None:
        with self._lock:
            self._db.execute("BEGIN")
            try:
                self._delete(campaign_id)
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def delete_all(self) -> int:
        """ "Borrar historial" (FR-065). Devuelve cuántas campañas se borraron."""
        with self._lock:
            ids = [r[0] for r in self._db.execute("SELECT id FROM campaign")]
            for cid in ids:
                self.delete_campaign(cid)
            self._db.execute("VACUUM")  # que los datos borrados no queden en el archivo
            return len(ids)

    def _delete(self, campaign_id: str) -> None:
        # Borrado explícito en orden (además del ON DELETE CASCADE) por claridad.
        self._db.execute("DELETE FROM recipient WHERE campaign_id=?", (campaign_id,))
        self._db.execute("DELETE FROM attempt WHERE campaign_id=?", (campaign_id,))
        self._db.execute("DELETE FROM campaign WHERE id=?", (campaign_id,))
