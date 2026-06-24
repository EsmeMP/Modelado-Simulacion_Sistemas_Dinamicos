import threading
import numpy as np
import sounddevice as sd

_ready_audio = threading.Event()
stream       = None
audio_level  = 0.0

def _init_audio():
    global stream, audio_level

    def audio_callback(indata, frames, time_, status):
        global audio_level
        audio_level = audio_level * 0.6 + float(np.linalg.norm(indata) * 20) * 0.4

    stream = sd.InputStream(callback=audio_callback, blocksize=512)
    stream.start()
    _ready_audio.set()

def start():
    threading.Thread(target=_init_audio, daemon=True).start()

def stop():
    if stream:
        stream.stop()