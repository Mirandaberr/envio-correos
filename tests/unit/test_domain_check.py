import threading

import dns.exception
import dns.resolver

from envio_correos.core.domain_check import DomainChecker, DomainStatus


class FakeResolver:
    def __init__(self, table):
        self.table = table  # (dominio, tipo) -> "ok" | excepción
        self.calls = []

    def resolve(self, domain, rdtype, lifetime=None):
        self.calls.append((domain, rdtype))
        r = self.table.get((domain, rdtype), dns.resolver.NoAnswer())
        if isinstance(r, Exception):
            raise r
        return [r]


def test_mx_ok():
    c = DomainChecker(FakeResolver({("x.com", "MX"): "ok"}))
    assert c.check("x.com") is DomainStatus.OK


def test_nxdomain():
    c = DomainChecker(FakeResolver({("empresa.con", "MX"): dns.resolver.NXDOMAIN()}))
    assert c.check("empresa.con") is DomainStatus.NOT_FOUND


class Mx:
    def __init__(self, exchange):
        self.exchange = exchange


def test_null_mx_no_acepta_correo():
    c = DomainChecker(FakeResolver({("example.com", "MX"): Mx("."), ("example.com", "A"): "ok"}))
    assert c.check("example.com") is DomainStatus.NOT_FOUND


def test_mx_real_es_valido():
    c = DomainChecker(FakeResolver({("x.com", "MX"): Mx("mx.x.com.")}))
    assert c.check("x.com") is DomainStatus.OK


def test_sin_mx_pero_con_a_es_valido():
    c = DomainChecker(FakeResolver({("x.com", "A"): "ok"}))
    assert c.check("x.com") is DomainStatus.OK


def test_sin_mx_ni_a_ni_aaaa_no_recibe():
    c = DomainChecker(FakeResolver({}))
    assert c.check("x.com") is DomainStatus.NOT_FOUND


def test_timeout_se_omite():
    c = DomainChecker(FakeResolver({("x.com", "MX"): dns.exception.Timeout()}))
    assert c.check("x.com") is DomainStatus.SKIPPED


def test_un_lookup_por_dominio_y_progreso():
    r = FakeResolver({("a.com", "MX"): "ok", ("b.com", "MX"): dns.resolver.NXDOMAIN()})
    c = DomainChecker(r)
    progress = []
    res = c.check_all(["a.com", "b.com", "a.com"], progress=lambda d, t: progress.append((d, t)))
    assert res == {"a.com": DomainStatus.OK, "b.com": DomainStatus.NOT_FOUND}
    assert sorted(r.calls) == [("a.com", "MX"), ("b.com", "MX")]
    assert progress[-1] == (2, 2)
    c.check_all(["a.com"])
    assert len(r.calls) == 2  # cacheado


def test_sin_red_corta_rapido():
    r = FakeResolver({(f"d{i}.com", "MX"): dns.resolver.NoNameservers() for i in range(10)})
    res = DomainChecker(r).check_all([f"d{i}.com" for i in range(10)])
    assert set(res.values()) == {DomainStatus.SKIPPED}
    assert len(r.calls) == 2  # tras 2 fallos de red seguidos no sigue consultando


def test_cancelable():
    cancel = threading.Event()
    cancel.set()
    res = DomainChecker(FakeResolver({})).check_all(["a.com"], cancel=cancel)
    assert res == {}


def test_liberar_cache():
    c = DomainChecker(FakeResolver({("a.com", "MX"): "ok"}))
    c.check_all(["a.com"])
    c.clear()
    assert c.cached() == {}
