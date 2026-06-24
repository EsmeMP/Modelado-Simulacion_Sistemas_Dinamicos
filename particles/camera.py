import threading
import cv2

_ready_camera = threading.Event()
cap           = None

def _init_camera():
    global cap
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS,          30)
    for _ in range(5):
        cap.read()
    _ready_camera.set()

def start():
    threading.Thread(target=_init_camera, daemon=True).start()

def release():
    if cap:
        cap.release()