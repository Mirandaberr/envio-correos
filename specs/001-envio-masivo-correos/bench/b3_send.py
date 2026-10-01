# Bench 3: estabilidad de memoria en 2000 envíos 1 a 1 con adjunto de 3MB contra SMTP local.
import smtplib
import sys
import time
from email.message import EmailMessage

import psutil
from aiosmtpd.controller import Controller


class Sink:
    async def handle_DATA(self, server, session, envelope):
        return "250 OK"


ctl = Controller(Sink(), hostname="127.0.0.1", port=8025, data_size_limit=50_000_000)
ctl.start()
proc = psutil.Process()
N = 2000
mode = sys.argv[1]
ADJ = open("adjunto.bin", "rb").read() if mode == "cache_bytes" else None


def build(i):
    m = EmailMessage()
    m["From"] = "yo@empresa.com"
    m["To"] = f"user{i}@empresa.com"
    m["Subject"] = f"Hola {i}"
    m.set_content(f"Hola usuario {i}")
    data = ADJ if ADJ is not None else open("adjunto.bin", "rb").read()
    m.add_attachment(data, maintype="application", subtype="octet-stream", filename="adjunto.bin")
    return m


s = smtplib.SMTP("127.0.0.1", 8025)
rss = []
t = time.perf_counter()
for i in range(N):
    s.send_message(build(i))
    if i % 200 == 0:
        rss.append(proc.memory_info().rss / 1e6)
s.quit()
ctl.stop()
print(f"{mode}: {time.perf_counter() - t:.1f}s RSS MB cada 200 envíos: {[round(x) for x in rss]}")
