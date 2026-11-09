"""Grabación del micrófono y transcripción local con faster-whisper (sin internet)."""
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

FRECUENCIA = 16000  # Whisper trabaja con audio mono a 16 kHz


class Grabadora:
    def __init__(self):
        self._bloques = []
        self._stream = None

    def iniciar(self):
        self._bloques = []
        self._stream = sd.InputStream(
            samplerate=FRECUENCIA, channels=1, dtype="float32", callback=self._recibir
        )
        self._stream.start()

    def _recibir(self, datos, frames, tiempo, estado):
        self._bloques.append(datos.copy())

    def detener(self):
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._bloques:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._bloques).flatten()


class Transcriptor:
    def __init__(self, modelo, dispositivo, idioma):
        tipo = "float16" if dispositivo == "cuda" else "int8"
        self._modelo = WhisperModel(modelo, device=dispositivo, compute_type=tipo)
        self._idioma = idioma or None  # None = detectar el idioma automáticamente

    def transcribir(self, audio):
        if len(audio) < FRECUENCIA * 0.3:  # menos de 0.3 s: no hay nada que transcribir
            return ""
        segmentos, _ = self._modelo.transcribe(
            audio, language=self._idioma, beam_size=5, vad_filter=True
        )
        return " ".join(s.text.strip() for s in segmentos).strip()
