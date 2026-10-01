"""Cierre forzado real: se mata el proceso que envía y se reanuda sin duplicados (SC-004)."""

import subprocess
import sys
import textwrap
import time

import pytest

from envio_correos.core.engine import CampaignRunner
from envio_correos.core.journal import Journal
from envio_correos.core.journal import RecipientState as S
from tests.integration.engine_helpers import make_builder, make_campaign, make_provider

pytestmark = pytest.mark.slow

TOTAL = 30

CHILD = textwrap.dedent(
    """
    import sys
    from pathlib import Path
    from envio_correos.config import SmtpEndpoint
    from envio_correos.core.engine import CampaignRunner
    from envio_correos.core.journal import Journal
    from envio_correos.core.providers.m365_smtp import M365SmtpPasswordProvider
    from tests.integration.engine_helpers import LimitedProvider, make_builder

    db, host, port, ca, user, pw, cid = sys.argv[1:8]
    inner = M365SmtpPasswordProvider(user, pw, endpoint=SmtpEndpoint(host, int(port), Path(ca)))
    provider = LimitedProvider(inner, min_interval_s=0.05)
    journal = Journal(Path(db))
    CampaignRunner(provider=provider, journal=journal, campaign_id=cid, attempt_number=1,
                   builder=make_builder(user)).run()
    """
)


def test_matar_el_proceso_y_reanudar(smtp_server, tmp_path):
    db = tmp_path / "j.db"
    journal = Journal(db)
    addresses = [f"u{i}@x.com" for i in range(TOTAL)]
    cid, n = make_campaign(journal, addresses, account=smtp_server.username)
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            CHILD,
            str(db),
            smtp_server.host,
            str(smtp_server.port),
            str(smtp_server.ca_file),
            smtp_server.username,
            smtp_server.password,
            cid,
        ],
        cwd=str(__import__("pathlib").Path(__file__).resolve().parents[2]),
    )
    deadline = time.time() + 30
    while len(smtp_server.messages) < 10 and time.time() < deadline:
        time.sleep(0.01)
    child.kill()  # cierre forzado a mitad del envío
    child.wait(timeout=10)
    sent_before = len(smtp_server.recipients())
    assert 10 <= sent_before < TOTAL

    assert journal.mark_interrupted_running() == 1
    CampaignRunner(
        provider=make_provider(smtp_server, min_interval_s=0.0),
        journal=journal,
        campaign_id=cid,
        attempt_number=n,
        builder=make_builder(smtp_server.username),
    ).run()
    delivered = smtp_server.recipients()
    assert len(delivered) == len(set(delivered)), "hubo duplicados"
    states = [r.state for r in journal.recipients(cid, n)]
    # Todo destinatario terminó enviado, salvo como mucho uno "en vuelo" al momento del corte
    assert states.count(S.SENT) + states.count(S.SENDING) == TOTAL
    assert states.count(S.SENDING) <= 1
    journal.close()
