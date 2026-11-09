"""Dictado por voz para Windows.

Pulsa el atajo (Ctrl+Shift+Z por defecto), habla, y vuelve a pulsarlo:
el texto se pega en la aplicación que tengas activa (WhatsApp, Messenger,
el navegador, ChatGPT, etc.). Esc cancela la grabación.
"""
import json
import logging
import os
import sys
import threading
import time
from pathlib import Path

CARPETA = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent

# Con pythonw no hay consola: stdout/stderr son None y las barras de progreso
# de la descarga del modelo fallarían. Los mandamos al archivo de log.
if sys.stdout is None or sys.stderr is None:
    _salida = open(CARPETA / "dictado.log", "a", encoding="utf-8", buffering=1)
    sys.stdout = sys.stdout or _salida
    sys.stderr = sys.stderr or _salida

import keyboard
import pyperclip
import pystray
from PIL import Image, ImageDraw

from transcriptor import Grabadora, Transcriptor

try:
    import winsound
except ImportError:  # fuera de Windows no hay pitidos
    winsound = None

CONFIG_POR_DEFECTO = {
    "atajo": "ctrl+shift+z",
    "idioma": "es",
    "modelo": "small",
    "dispositivo": "cpu",
    "enviar_con_enter": False,
    "sonidos": True,
}

COLORES = {
    "cargando": "#9e9e9e",
    "listo": "#2e7d32",
    "grabando": "#d32f2f",
    "transcribiendo": "#f9a825",
    "error": "#212121",
}


def cargar_config():
    ruta = CARPETA / "config.json"
    config = dict(CONFIG_POR_DEFECTO)
    if ruta.exists():
        config.update(json.loads(ruta.read_text(encoding="utf-8")))
    else:
        ruta.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    return config


def crear_icono(color):
    imagen = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.ellipse((4, 4, 60, 60), fill=color)
    # Silueta sencilla de micrófono
    dibujo.rounded_rectangle((24, 14, 40, 38), radius=8, fill="white")
    dibujo.arc((18, 24, 46, 46), start=0, end=180, fill="white", width=3)
    dibujo.line((32, 46, 32, 52), fill="white", width=3)
    return imagen


def en_hilo(funcion):
    """Ejecuta el callback del atajo en otro hilo para no bloquear el teclado."""
    return lambda: threading.Thread(target=funcion, daemon=True).start()


class App:
    def __init__(self, config):
        self.config = config
        self.estado = "cargando"
        self.transcriptor = None
        self.grabadora = Grabadora()
        self.bloqueo = threading.Lock()
        self.icono = pystray.Icon(
            "dictado-voz",
            crear_icono(COLORES["cargando"]),
            "Dictado por voz: cargando modelo...",
            menu=pystray.Menu(
                pystray.MenuItem(lambda item: f"Estado: {self.estado}", None, enabled=False),
                pystray.MenuItem(f"Atajo: {config['atajo']}", None, enabled=False),
                pystray.MenuItem("Salir", self.salir),
            ),
        )

    def ejecutar(self):
        self.icono.run(setup=self._preparar)

    def _preparar(self, icono):
        icono.visible = True
        icono.notify("Cargando el modelo de voz. La primera vez se descarga y tarda unos minutos.", "Dictado por voz")
        try:
            self.transcriptor = Transcriptor(
                self.config["modelo"], self.config["dispositivo"], self.config["idioma"]
            )
        except Exception:
            logging.exception("No se pudo cargar el modelo")
            self.cambiar_estado("error", " (revisa dictado.log)")
            return
        keyboard.add_hotkey(self.config["atajo"], en_hilo(self.alternar), suppress=True)
        keyboard.add_hotkey("esc", en_hilo(self.cancelar))
        self.cambiar_estado("listo", f" - pulsa {self.config['atajo']}")
        icono.notify(f"Listo. Pulsa {self.config['atajo']} para dictar.", "Dictado por voz")

    def cambiar_estado(self, estado, detalle=""):
        self.estado = estado
        self.icono.icon = crear_icono(COLORES[estado])
        self.icono.title = f"Dictado por voz: {estado}{detalle}"
        self.icono.update_menu()

    def pitido(self, frecuencia):
        if winsound and self.config["sonidos"]:
            threading.Thread(target=winsound.Beep, args=(frecuencia, 120), daemon=True).start()

    def alternar(self):
        with self.bloqueo:
            if self.estado == "listo":
                try:
                    self.grabadora.iniciar()
                except Exception:
                    logging.exception("No se pudo abrir el micrófono")
                    self.icono.notify("No se pudo abrir el micrófono.", "Dictado por voz")
                    return
                self.cambiar_estado("grabando")
                self.pitido(880)
            elif self.estado == "grabando":
                audio = self.grabadora.detener()
                self.cambiar_estado("transcribiendo")
                self.pitido(440)
                threading.Thread(target=self._transcribir_y_pegar, args=(audio,), daemon=True).start()

    def cancelar(self):
        with self.bloqueo:
            if self.estado == "grabando":
                self.grabadora.detener()
                self.cambiar_estado("listo")
                self.pitido(300)

    def _transcribir_y_pegar(self, audio):
        try:
            texto = self.transcriptor.transcribir(audio)
            logging.info("Transcritos %.1f s de audio -> %d caracteres", len(audio) / 16000, len(texto))
            if texto:
                self.pegar(texto)
        except Exception:
            logging.exception("Fallo al transcribir o pegar")
        finally:
            self.cambiar_estado("listo")

    def pegar(self, texto):
        # Esperar a que sueltes Ctrl/Shift/Alt para que no se mezclen con el Ctrl+V
        limite = time.time() + 2
        while time.time() < limite and any(keyboard.is_pressed(t) for t in ("ctrl", "shift", "alt")):
            time.sleep(0.05)
        anterior = pyperclip.paste()
        pyperclip.copy(texto)
        time.sleep(0.05)
        keyboard.send("ctrl+v")
        if self.config["enviar_con_enter"]:
            time.sleep(0.1)
            keyboard.send("enter")
        time.sleep(0.3)  # dar tiempo a la app a leer el portapapeles antes de restaurarlo
        if anterior:
            pyperclip.copy(anterior)

    def salir(self, icono, item):
        keyboard.unhook_all()
        icono.stop()


def main():
    logging.basicConfig(
        filename=CARPETA / "dictado.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    App(cargar_config()).ejecutar()


if __name__ == "__main__":
    main()
