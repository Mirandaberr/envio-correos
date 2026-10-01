import sys

from envio_correos import config


def test_sin_variable_usa_produccion(monkeypatch):
    monkeypatch.delenv(config.ENV_DEV_SMTP, raising=False)
    ep = config.smtp_endpoint()
    assert (ep.host, ep.port, ep.dev_ca_file) == (config.SMTP_HOST, config.SMTP_PORT, None)


def test_variable_activa_modo_dev_con_ca_propia(monkeypatch):
    monkeypatch.setenv(config.ENV_DEV_SMTP, "127.0.0.1:8025")
    ep = config.smtp_endpoint()
    assert (ep.host, ep.port) == ("127.0.0.1", 8025)
    assert ep.dev_ca_file is not None and ep.dev_ca_file.name == "ca.pem"


def test_ejecutable_congelado_ignora_modo_dev(monkeypatch):
    monkeypatch.setenv(config.ENV_DEV_SMTP, "127.0.0.1:8025")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    ep = config.smtp_endpoint()
    assert (ep.host, ep.port, ep.dev_ca_file) == (config.SMTP_HOST, config.SMTP_PORT, None)


def test_intervalo_minimo_respeta_limite():
    assert config.min_interval_s() * config.MESSAGES_PER_MINUTE >= 60.0


def test_data_dir_respeta_override(isolated_app_dirs):
    assert config.data_dir() == isolated_app_dirs
