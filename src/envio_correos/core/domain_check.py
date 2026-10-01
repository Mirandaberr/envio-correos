"""Verificación de dominios antes de enviar (FR-026, research R4).

Resuelve MX y, si no hay, A/AAAA (MX implícito, RFC 5321 §5.1), una vez por dominio único.
Sin red, corta rápido en vez de esperar el timeout en cada dominio.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Iterable
from enum import Enum

import dns.exception
import dns.resolver

from envio_correos import config

log = logging.getLogger(__name__)

_MAX_CONSECUTIVE_NETWORK_FAILURES = 2


class DomainStatus(Enum):
    OK = "ok"
    NOT_FOUND = "not_found"
    SKIPPED = "skipped"  # no se pudo verificar (sin red, timeout, servidor DNS con error)


def _is_null_mx(answer) -> bool:
    """RFC 7505: un único MX con destino "." declara que el dominio no acepta correo."""
    records = list(answer)
    return len(records) == 1 and str(getattr(records[0], "exchange", "")) == "."


class DomainChecker:
    def __init__(self, resolver=None, timeout: float = config.DNS_TIMEOUT_S):
        self._resolver = resolver or dns.resolver.Resolver()
        self._timeout = timeout
        # Caché acotada por la cantidad de dominios únicos de la lista; se libera con clear().
        self._cache: dict[str, DomainStatus] = {}

    def check(self, domain: str) -> DomainStatus:
        for rdtype in ("MX", "A", "AAAA"):
            try:
                answer = self._resolver.resolve(domain, rdtype, lifetime=self._timeout)
                if rdtype == "MX" and _is_null_mx(answer):
                    return DomainStatus.NOT_FOUND
                return DomainStatus.OK
            except dns.resolver.NXDOMAIN:
                return DomainStatus.NOT_FOUND
            except dns.resolver.NoAnswer:
                continue
            except (dns.exception.Timeout, dns.resolver.NoNameservers, dns.exception.DNSException):
                return DomainStatus.SKIPPED
        return DomainStatus.NOT_FOUND

    def check_all(
        self,
        domains: Iterable[str],
        progress: Callable[[int, int], None] | None = None,
        cancel: threading.Event | None = None,
    ) -> dict[str, DomainStatus]:
        unique = list(dict.fromkeys(d.lower() for d in domains))
        total = len(unique)
        result: dict[str, DomainStatus] = {}
        network_failures = 0
        for done, domain in enumerate(unique, 1):
            if cancel is not None and cancel.is_set():
                return result
            if domain not in self._cache:
                if network_failures >= _MAX_CONSECUTIVE_NETWORK_FAILURES:
                    status = DomainStatus.SKIPPED
                else:
                    status = self.check(domain)
                    network_failures = network_failures + 1 if status is DomainStatus.SKIPPED else 0
                self._cache[domain] = status
            result[domain] = self._cache[domain]
            if progress:
                progress(done, total)
        skipped = sum(1 for s in result.values() if s is DomainStatus.SKIPPED)
        log.info("Dominios verificados: %d (sin verificar: %d)", total, skipped)
        return result

    def cached(self) -> dict[str, DomainStatus]:
        return dict(self._cache)

    def clear(self) -> None:
        self._cache.clear()
