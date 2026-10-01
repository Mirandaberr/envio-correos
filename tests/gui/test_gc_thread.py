"""El recolector de basura no debe correr en hilos de trabajo mientras la GUI existe:
liberar objetos de Tk fuera del hilo principal traba la app (observado en CI de macOS)."""

import gc
import threading
import tkinter.font as tkfont

import pytest

from envio_correos import config
from envio_correos.core.journal import Journal
from envio_correos.gui import main_window

pytestmark = pytest.mark.slow


def test_objetos_tk_en_ciclos_se_liberan_en_el_hilo_de_la_gui(isolated_app_dirs, monkeypatch):
    monkeypatch.setattr(config, "GC_INTERVAL_MS", 50)
    journal = Journal()
    gc_estaba = gc.isenabled()
    app = main_window.build(journal)
    out = {"del_threads": []}
    original_del = tkfont.Font.__del__

    def spy_del(self):
        out["del_threads"].append(threading.current_thread() is threading.main_thread())
        original_del(self)

    monkeypatch.setattr(tkfont.Font, "__del__", spy_del)

    def script():
        out["gc_activo_con_ventana"] = gc.isenabled()

        class Ciclo:
            pass

        c = Ciclo()
        c.font = tkfont.Font(root=app, family="Helvetica", size=12)
        c.self_ref = c  # ciclo: solo el recolector puede liberarlo
        del c

        def worker():  # un hilo que genera mucha basura (como el motor de envío)
            basura = []
            for _ in range(200_000):
                basura.append([[]])
                if len(basura) > 1000:
                    basura.clear()

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        app.after(300, app.destroy)

    app.after(50, script)
    app.mainloop()
    journal.close()
    assert out["gc_activo_con_ventana"] is False
    assert out["del_threads"] and all(out["del_threads"])  # siempre en el hilo principal
    assert gc.isenabled() == gc_estaba  # se restaura al cerrar la ventana
