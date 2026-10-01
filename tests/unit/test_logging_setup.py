import logging
import logging.handlers
import threading

import pytest

from envio_correos import config, logging_setup


@pytest.fixture
def configured(tmp_path):
    handler = logging_setup.setup_logging(tmp_path)
    yield tmp_path / config.LOG_FILENAME, handler
    logging_setup.teardown_logging()


def _read(path, handler):
    handler.flush()
    return path.read_text(encoding="utf-8")


def test_track_id_de_sesion_por_defecto(configured):
    path, handler = configured
    logging.getLogger("envio_correos.test").info("hola")
    sid = logging_setup.session_track_id()
    assert sid.startswith("S-")
    assert f"[{sid}]" in _read(path, handler)


def test_track_id_de_campana_dentro_del_contexto_y_se_restaura(configured):
    path, handler = configured
    log = logging.getLogger("envio_correos.test")
    with logging_setup.campaign_context("C-7F3A-R2"):
        log.info("dentro")
    log.info("fuera")
    lines = _read(path, handler).splitlines()
    assert "[C-7F3A-R2]" in lines[-2] and "dentro" in lines[-2]
    assert f"[{logging_setup.session_track_id()}]" in lines[-1]


def test_contexto_de_campana_funciona_dentro_de_un_hilo(configured):
    path, handler = configured

    def work():
        with logging_setup.campaign_context("C-0001"):
            logging.getLogger("envio_correos.engine").warning("en hilo")

    t = threading.Thread(target=work)
    t.start()
    t.join()
    assert "[C-0001]" in _read(path, handler)


def test_enmascara_correos_en_mensaje_y_argumentos(configured):
    path, handler = configured
    log = logging.getLogger("envio_correos.test")
    log.info("fallo para juan.perez@empresa.com")
    log.info("fallo para %s", "ana@empresa.com")
    text = _read(path, handler)
    assert "juan.perez@empresa.com" not in text and "ju***@empresa.com" in text
    assert "ana@empresa.com" not in text and "an***@empresa.com" in text


def test_mask_email_parte_local_corta():
    assert logging_setup.mask_email("a@x.com") == "a***@x.com"


def test_handler_rotativo_con_limites_configurados(configured):
    _, handler = configured
    assert isinstance(handler, logging.handlers.RotatingFileHandler)
    assert handler.maxBytes == config.LOG_MAX_BYTES
    assert handler.backupCount == config.LOG_BACKUP_COUNT


def test_setup_es_idempotente(tmp_path):
    h1 = logging_setup.setup_logging(tmp_path)
    h2 = logging_setup.setup_logging(tmp_path)
    try:
        root_handlers = [h for h in logging.getLogger().handlers if h is h1 or h is h2]
        assert len(root_handlers) == 1
    finally:
        logging_setup.teardown_logging()


def test_enmascara_correos_en_tracebacks(configured):
    path, handler = configured
    try:
        raise ValueError("rechazado juan.perez@empresa.com")
    except ValueError:
        logging.getLogger("envio_correos.test").exception("fallo")
    text = _read(path, handler)
    assert "Traceback" in text and "ValueError" in text
    assert "juan.perez@empresa.com" not in text and "ju***@empresa.com" in text
