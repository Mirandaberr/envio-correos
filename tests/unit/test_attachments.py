"""Adjuntos: límite de tamaño, carga única por intento y hash (FR-032, research R7.5)."""

import hashlib

from envio_correos import config
from envio_correos.core import attachments
from envio_correos.texts import es


def test_referencia_con_tamano_y_hash(tmp_path):
    f = tmp_path / "a.pdf"
    f.write_bytes(b"x" * 1000)
    ref = attachments.make_ref(f)
    assert ref.size == 1000 and ref.sha256 == hashlib.sha256(b"x" * 1000).hexdigest()


def test_limite_de_tamano_con_cuanto_reducir(tmp_path):
    f = tmp_path / "grande.bin"
    f.write_bytes(b"0")
    ref = attachments.make_ref(f)
    big = ref.__class__(ref.path, config.MAX_ATTACHMENTS_RAW_BYTES + 3 * 1024**2, ref.sha256)
    msg = attachments.size_error([big])
    assert msg == es.ATTACHMENTS_TOO_BIG.format(total="28 MB", limit="25 MB", excess="3 MB")
    assert attachments.size_error([ref]) is None


def test_tamano_legible():
    assert attachments.human_size(512) == "1 KB"
    assert attachments.human_size(1536 * 1024) == "1,5 MB"


def test_bytes_se_leen_una_vez_por_intento(tmp_path):
    f = tmp_path / "nota.txt"
    f.write_text("versión 1")
    loaded = attachments.load_for_attempt([attachments.make_ref(f)])
    f.write_text("versión 2 modificada")  # cambia en disco a mitad de la campaña
    assert loaded[0].data == "versión 1".encode()
    assert (loaded[0].filename, loaded[0].maintype, loaded[0].subtype) == (
        "nota.txt",
        "text",
        "plain",
    )


def test_tipo_desconocido(tmp_path):
    f = tmp_path / "datos.zzz"
    f.write_bytes(b"1")
    a = attachments.load_for_attempt([attachments.make_ref(f)])[0]
    assert (a.maintype, a.subtype) == ("application", "octet-stream")
