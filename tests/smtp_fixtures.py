"""Fixtures de servidor SMTP compartidas por los tests de contrato e integración."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from envio_correos.config import SmtpEndpoint
from envio_correos.devtools.fake_smtp import Behavior, FakeSmtpServer


@pytest.fixture
def smtp_server(tmp_path: Path) -> Iterator[FakeSmtpServer]:
    with FakeSmtpServer(tmp_path / "certs", behavior=Behavior()) as srv:
        yield srv


@pytest.fixture
def smtp_server_sin_tls(tmp_path: Path) -> Iterator[FakeSmtpServer]:
    with FakeSmtpServer(tmp_path / "certs-plain", offer_starttls=False) as srv:
        yield srv


def endpoint_for(srv: FakeSmtpServer) -> SmtpEndpoint:
    return SmtpEndpoint(srv.host, srv.port, srv.ca_file)
