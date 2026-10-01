"""Mediciones de rendimiento para quickstart P2/P3 (T085). Pensado para correr en Windows.

    uv run python scripts/perf_campaign.py [--rows 5000]

P2: carga de un Excel de N filas + búsqueda (objetivos SC-007 < 5 s, SC-010 < 0,5 s).
P3: campaña de N correos contra el SMTP de prueba con el ritmo desactivado, RSS cada 10 %
    (objetivo SC-011: < 200 MB y sin crecimiento sostenido).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ENVIO_CORREOS_DATA_DIR", tempfile.mkdtemp())

import psutil  # noqa: E402
from tests.fixtures.make_fixtures import make_lista  # noqa: E402
from tests.integration.engine_helpers import FakeTime, make_provider  # noqa: E402

from envio_correos.core import excel_reader  # noqa: E402
from envio_correos.core.engine import CampaignRunner, Progress  # noqa: E402
from envio_correos.core.journal import CampaignSpec, Journal  # noqa: E402
from envio_correos.core.message_builder import MessageBuilder, MessageTemplate  # noqa: E402
from envio_correos.core.recipients import RecipientList  # noqa: E402
from envio_correos.devtools.fake_smtp import FakeSmtpServer  # noqa: E402

log = logging.getLogger("perf")


def p2(path: Path) -> RecipientList:
    t = time.perf_counter()
    lst = RecipientList.from_sheet(excel_reader.read_sheet(path), str(path))
    load = time.perf_counter() - t
    lst.search("x")  # construye el índice
    worst = 0.0
    for q in ("jose", "user12", "bogota", ""):
        t = time.perf_counter()
        lst.search(q)
        worst = max(worst, time.perf_counter() - t)
    log.info("P2: carga %.2f s (SC-007 < 5 s) · peor búsqueda %.3f s (SC-010 < 0,5 s)", load, worst)
    return lst


def p3(lst: RecipientList, tmp: Path) -> None:
    proc = psutil.Process()
    with FakeSmtpServer(tmp / "certs") as srv:
        journal = Journal(tmp / "perf.db")
        spec = CampaignSpec(
            srv.username,
            lst.source_path,
            lst.sheet_name,
            lst.headers,
            lst.email_col,
            "Hola",
            "Cuerpo",
            (),
            "ONE_BY_ONE",
        )
        cid = journal.create_campaign(spec)
        n = journal.start_attempt(cid, lst.to_attempt_rows(), lst.headers)
        total = lst.counts().effective
        samples: list[float] = []

        def on_event(e) -> None:
            if isinstance(e, Progress):
                srv.messages.clear()
                done = e.total - e.pending
                if done % max(total // 10, 1) == 0:
                    samples.append(proc.memory_info().rss / 1e6)

        builder = MessageBuilder(
            template=MessageTemplate("Hola", "Cuerpo"),
            headers=lst.headers,
            sender_email=srv.username,
            display_name="",
        )
        t = time.perf_counter()
        ft = FakeTime()
        CampaignRunner(
            provider=make_provider(srv),
            journal=journal,
            campaign_id=cid,
            attempt_number=n,
            builder=builder,
            on_event=on_event,
            monotonic=ft.monotonic,
            wait=ft.wait,
        ).run()
        journal.close()
    log.info(
        "P3: %d envíos en %.0f s · RSS cada 10%% (MB): %s · máx %.0f MB (SC-011 < 200)",
        total,
        time.perf_counter() - t,
        [round(x) for x in samples],
        max(samples),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=5000)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tmp = Path(tempfile.mkdtemp())
    path = make_lista(tmp / "lista.xlsx", args.rows, "x.com")
    p3(p2(path), tmp)


if __name__ == "__main__":
    main()
