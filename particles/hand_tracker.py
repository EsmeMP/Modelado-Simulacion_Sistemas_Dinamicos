import threading
import mediapipe as mp

_ready_mediapipe = threading.Event()
hands            = None

def _init_mediapipe():
    global hands
    mp_h  = mp.solutions.hands
    hands = mp_h.Hands(max_num_hands=1,
                    min_detection_confidence=0.6,
                    min_tracking_confidence=0.6)
    _ready_mediapipe.set()

def start():
    threading.Thread(target=_init_mediapipe, daemon=True).start()