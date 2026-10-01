# Bench 4: costo de armar+serializar un mensaje con adjunto 3MB: releer y codificar cada vez vs. parte MIME pre-codificada.
import time
import tracemalloc
from email.message import EmailMessage
from email.policy import SMTP

N = 50
RAW = open("adjunto.bin", "rb").read()


def ser(m):
    return m.as_bytes(policy=SMTP)


def a(i):
    m = EmailMessage()
    m["To"] = f"u{i}@x.com"
    m.set_content("hola")
    m.add_attachment(
        open("adjunto.bin", "rb").read(),
        maintype="application",
        subtype="octet-stream",
        filename="a.bin",
    )
    return ser(m)


PART = EmailMessage()
PART.set_content(
    RAW, maintype="application", subtype="octet-stream", filename="a.bin"
)  # codificado 1 vez


def b(i):
    m = EmailMessage()
    m["To"] = f"u{i}@x.com"
    m.set_content("hola")
    m.make_mixed()
    m.attach(PART)
    return ser(m)


for name, f in (("releer+codificar", a), ("parte pre-codificada", b)):
    tracemalloc.start()
    t = time.perf_counter()
    for i in range(N):
        out = f(i)
    dt = (time.perf_counter() - t) / N * 1000
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(f"{name}: {dt:.1f} ms/mensaje, pico {peak / 1e6:.1f}MB, tamaño {len(out) / 1e6:.2f}MB")
