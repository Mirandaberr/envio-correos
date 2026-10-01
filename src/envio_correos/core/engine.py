"""Motor de campañas (FR-053..056, research R3, plan "Diseño del motor").

Reglas:
- Antes de enviar, cada destinatario pasa a SENDING con commit; el resultado se confirma
  después (constitución III: un cierre deja visible qué estaba en vuelo).
- Rechazo permanente → FAILED y se continúa. Transitorio → reintentos (TRANSIENT_RETRY_DELAYS_S);
  si persiste, el destinatario vuelve a PENDING y la campaña se PAUSA (decisión F2 del análisis).
  Error de cuenta → PAUSA. Límite diario → PAUSA. Detener → los pendientes pasan a SKIPPED.
- Ritmo: nunca menos de `limits.min_interval_s` entre envíos.
- El hilo nunca toca la GUI: publica eventos con `on_event`.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from envio_correos import config
from envio_correos.core.journal import (
    AttemptState,
    Journal,
    RecipientState,
    StoredRecipient,
    attempt_code,
)
from envio_correos.core.message_builder import MessageBuilder, SendMode, batches
from envio_correos.core.providers.base import (
    Failure,
    FailureKind,
    OutgoingMessage,
    ProviderError,
    ReasonCode,
    SendProvider,
)
from envio_correos.logging_setup import campaign_context
from envio_correos.texts import es

log = logging.getLogger(__name__)

DAILY_LIMIT = "DAILY_LIMIT"
STOPPED_CODE = "STOPPED_BY_USER"


# --- Eventos hacia la GUI ---


@dataclass(frozen=True)
class Progress:
    sent: int
    failed: int
    skipped: int
    pending: int
    total: int
    eta_s: float


@dataclass(frozen=True)
class Paused:
    reason: str  # ReasonCode o DAILY_LIMIT
    smtp_code: str | None = None


@dataclass(frozen=True)
class Finished:
    state: AttemptState
    counts: dict[str, int]


@dataclass
class _Pause(Exception):
    reason: str
    smtp_code: str | None = None


Job = Sequence[StoredRecipient]


class CampaignRunner(threading.Thread):
    def __init__(
        self,
        *,
        provider: SendProvider,
        journal: Journal,
        campaign_id: str,
        attempt_number: int,
        builder: MessageBuilder,
        on_event: Callable[[object], None] = lambda _e: None,
        monotonic: Callable[[], float] = time.monotonic,
        wait: Callable[[float], bool] | None = None,
        retry_delays: Sequence[float] = config.TRANSIENT_RETRY_DELAYS_S,
    ):
        super().__init__(name=f"envio-{campaign_id}", daemon=True)
        self.provider = provider
        self.journal = journal
        self.campaign_id = campaign_id
        self.attempt_number = attempt_number
        self.code = attempt_code(campaign_id, attempt_number)
        self.builder = builder
        self.on_event = on_event
        self._monotonic = monotonic
        self._stop_event = threading.Event()
        self._wait = wait or self._stop_event.wait
        self._retry_delays = tuple(retry_delays)
        self._last_send: float | None = None

    # --- API ---

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def stopping(self) -> bool:
        return self._stop_event.is_set()

    # --- Ciclo principal ---

    def run(self) -> None:
        with campaign_context(self.code):
            try:
                self._run()
            except Exception:
                log.exception("Fallo inesperado del motor; el intento queda pausado")
                self._finish_paused(_Pause("UNKNOWN"))
            finally:
                self.provider.close()
                # Los bytes de los adjuntos se liberan al terminar el intento (FR-075); si se
                # reanuda, la GUI arma un builder nuevo y los vuelve a leer.
                self.builder.attachments = ()

    def _run(self) -> None:
        j, cid, n = self.journal, self.campaign_id, self.attempt_number
        j.set_attempt_state(cid, n, AttemptState.RUNNING)
        account = self.provider.sender_email
        budget = self.provider.limits.recipients_per_24h - j.sent_last_24h(account)
        jobs = deque(self._plan(j.recipients(cid, n, {RecipientState.PENDING})))
        log.info("Inicio del envío: %d mensajes, cupo diario restante %d", len(jobs), budget)
        try:
            self.provider.open()
            while jobs:
                if self.stopping:
                    return self._finish_stopped()
                job = jobs[0]
                if self._cost(len(job)) > budget:
                    raise _Pause(DAILY_LIMIT)
                if not self._pace():
                    continue  # se pidió detener durante la espera
                budget -= self._cost(self._send_job(job))
                jobs.popleft()
                self._emit_progress(len(jobs))
        except _Pause as pause:
            return self._finish_paused(pause)
        except ProviderError as exc:
            return self._finish_paused(_Pause(exc.failure.code, exc.failure.smtp_code))
        self._finish(AttemptState.DONE)

    def _plan(self, pending: list[StoredRecipient]) -> list[Job]:
        if not self.builder.mode.is_batch:
            return [[r] for r in pending]
        return batches(pending, self.provider.limits.max_recipients_per_message)

    def _cost(self, recipients: int) -> int:
        """Destinatarios que cuentan para el cupo diario. En copia oculta el remitente va en
        "Para" y recibe una copia de cada lote."""
        if recipients and self.builder.mode is SendMode.ALL_AT_ONCE_BCC:
            return recipients + 1
        return recipients

    def _pace(self) -> bool:
        if self._last_send is None:
            return True
        remaining = self._last_send + self.provider.limits.min_interval_s - self._monotonic()
        if remaining <= 0:
            return True
        return not self._wait(remaining)

    def _message_for(self, rows: Job) -> OutgoingMessage:
        if len(rows) == 1 and not self.builder.mode.is_batch:
            return self.builder.for_recipient(rows[0].address, rows[0].values)
        return self.builder.for_batch([r.address for r in rows])

    # --- Envío de un trabajo con reintentos ---

    def _send_job(self, job: Job) -> int:
        """Envía y registra el resultado de cada destinatario. Devuelve cuántos se aceptaron.
        Lanza _Pause si hay que pausar la campaña."""
        j, cid, n = self.journal, self.campaign_id, self.attempt_number
        for r in job:
            j.mark_sending(cid, n, r.row_seq)
        remaining = list(job)
        delays = iter(self._retry_delays)
        accepted_total = 0
        while True:
            transient, last_failure = self._try_send(remaining)
            accepted_total += len(remaining) - len(transient)
            if not transient:
                return accepted_total
            if last_failure.code is ReasonCode.TOO_MANY_RECIPIENTS and len(transient) > 1:
                return accepted_total + self._split(transient)
            delay = next(delays, None)
            if delay is None or self._wait_retry(delay):
                for r in transient:
                    j.mark_result(cid, n, r.row_seq, RecipientState.PENDING)
                if delay is None:
                    log.error("Error transitorio persistente: %s; se pausa", last_failure.code)
                    raise _Pause(last_failure.code, last_failure.smtp_code)
                return accepted_total  # se pidió detener: el ciclo marca los pendientes
            remaining = transient

    def _split(self, rows: list[StoredRecipient]) -> int:
        """El servidor rechazó por exceso de destinatarios: se reenvía en dos mitades."""
        log.warning("Demasiados destinatarios por mensaje; se divide el lote de %d", len(rows))
        mid = len(rows) // 2
        accepted = 0
        for half in (rows[:mid], rows[mid:]):
            if self.stopping or not self._pace():
                for r in half:
                    self.journal.mark_result(
                        self.campaign_id, self.attempt_number, r.row_seq, RecipientState.PENDING
                    )
                continue
            accepted += self._send_job(half)
        return accepted

    def _wait_retry(self, delay: float) -> bool:
        log.warning("Error transitorio; se reintenta en %.0f s", delay)
        return self._wait(delay)

    def _try_send(self, rows: list[StoredRecipient]) -> tuple[list[StoredRecipient], Failure]:
        """Un intento de envío. Devuelve los destinatarios con fallo transitorio."""
        j, cid, n = self.journal, self.campaign_id, self.attempt_number
        try:
            outcome = self.provider.send(self._message_for(rows))
        except ProviderError as exc:
            self._last_send = self._monotonic()
            if exc.failure.kind is FailureKind.TRANSIENT:
                return rows, exc.failure
            for r in rows:
                j.mark_result(cid, n, r.row_seq, RecipientState.PENDING)
            log.error("Error de cuenta durante el envío: %s", exc.failure.code)
            raise _Pause(exc.failure.code, exc.failure.smtp_code) from None
        self._last_send = self._monotonic()
        transient: list[StoredRecipient] = []
        last: Failure | None = None
        for r in rows:
            failure = outcome.rejected.get(r.address)
            if failure is None:
                j.mark_result(cid, n, r.row_seq, RecipientState.SENT)
            elif failure.kind is FailureKind.TRANSIENT:
                transient.append(r)
                last = failure
            else:
                j.mark_result(
                    cid,
                    n,
                    r.row_seq,
                    RecipientState.FAILED,
                    failure.code,
                    es.reason_text(failure.code, failure.smtp_code),
                    failure.smtp_code,
                )
                log.warning("Destinatario rechazado (%s): %s", failure.smtp_code, r.address)
        return transient, last  # type: ignore[return-value]

    # --- Cierre ---

    def _emit_progress(self, jobs_left: int) -> None:
        c = self.journal.counts(self.campaign_id, self.attempt_number)
        pending = c.get(RecipientState.PENDING, 0) + c.get(RecipientState.SENDING, 0)
        self.on_event(
            Progress(
                sent=c.get(RecipientState.SENT, 0),
                failed=c.get(RecipientState.FAILED, 0),
                skipped=c.get(RecipientState.SKIPPED, 0),
                pending=pending,
                total=sum(c.values()),
                eta_s=jobs_left * self.provider.limits.min_interval_s,
            )
        )

    def _finish_stopped(self) -> None:
        j, cid, n = self.journal, self.campaign_id, self.attempt_number
        for r in j.recipients(cid, n, {RecipientState.PENDING}):
            j.mark_result(
                cid, n, r.row_seq, RecipientState.SKIPPED, STOPPED_CODE, es.SKIP_STOPPED_BY_USER
            )
        log.info("Envío detenido por el usuario")
        self._finish(AttemptState.STOPPED)

    def _finish_paused(self, pause: _Pause) -> None:
        self.journal.set_attempt_state(self.campaign_id, self.attempt_number, AttemptState.PAUSED)
        log.warning("Envío pausado: %s", pause.reason)
        self.on_event(Paused(str(pause.reason), pause.smtp_code))

    def _finish(self, state: AttemptState) -> None:
        j, cid, n = self.journal, self.campaign_id, self.attempt_number
        j.set_attempt_state(cid, n, state)
        counts = j.counts(cid, n)
        log.info("Fin del envío (%s): %s", state, counts)
        self.on_event(Finished(state, counts))
