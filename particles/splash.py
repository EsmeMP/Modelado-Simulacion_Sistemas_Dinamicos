import cv2
import numpy as np
import time

SW, SH = 600, 360

def _rounded_rect(img, x1, y1, x2, y2, r, color, thickness=-1):
    """Rectángulo con esquinas redondeadas."""
    cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, thickness)
    cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, thickness)
    for cx, cy in [(x1+r, y1+r), (x2-r, y1+r), (x1+r, y2-r), (x2-r, y2-r)]:
        cv2.circle(img, (cx, cy), r, color, thickness)

def draw(progress: float, msg: str) -> np.ndarray:
    # Fondo negro puro
    img = np.zeros((SH, SW, 3), dtype=np.uint8)

    # ── Card centrada ──────────────────────────────────────────
    CW, CH   = 440, 260
    CX       = (SW - CW) // 2
    CY       = (SH - CH) // 2
    RADIUS   = 16

    # ── Ícono animado: círculo pulsante con check parcial ──────
    t_now    = time.time()
    pulse    = int(4 * abs(np.sin(t_now * 3)))
    ICX      = SW // 2
    ICY      = CY + 58
    ICON_R   = 26 + pulse

    # Anillo de fondo
    cv2.circle(img, (ICX, ICY), ICON_R + 4, (40, 36, 60), -1)
    # Arco de progreso
    total_angle = int(360 * progress)
    for deg in range(0, total_angle, 3):
        rad = np.deg2rad(deg - 90)
        x   = int(ICX + ICON_R * np.cos(rad))
        y   = int(ICY + ICON_R * np.sin(rad))
        cv2.circle(img, (x, y), 3, (0, 210, 100), -1)
    # Círculo interior (efecto "donut")
    cv2.circle(img, (ICX, ICY), ICON_R - 7, (30, 26, 46), -1)
    # Porcentaje dentro del ícono
    pct_str     = f"{int(progress*100)}%"
    (pw, ph), _ = cv2.getTextSize(pct_str, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    cv2.putText(img, pct_str, (ICX - pw//2, ICY + ph//2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

    # ── Título ────────────────────────────────────────────────
    title = "Iniciando simulacion..."
    (tw, _), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.72, 2)
    cv2.putText(img, title, (SW//2 - tw//2, CY + 118),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, (240, 240, 255), 2, cv2.LINE_AA)

    # ── Subtítulo / estado ────────────────────────────────────
    (sw2, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
    cv2.putText(img, msg, (SW//2 - sw2//2, CY + 148),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (120, 200, 140), 1, cv2.LINE_AA)

    # ── Barra de progreso slim ────────────────────────────────
    BX, BY = CX + 30, CY + 175
    BW, BH = CW - 60, 6
    _rounded_rect(img, BX, BY, BX+BW, BY+BH, 3, (50, 46, 70))
    fill = max(0, int(BW * progress))
    if fill > 0:
        _rounded_rect(img, BX, BY, BX+fill, BY+BH, 3, (0, 210, 100))

    return img

def show(ready_camera, ready_mediapipe, ready_audio):
    """Muestra el splash hasta que los 3 módulos estén listos."""
    cv2.namedWindow("Simulacion", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Simulacion", SW, SH)

    while not (ready_camera.is_set() and ready_mediapipe.is_set() and ready_audio.is_set()):
        done     = sum([ready_camera.is_set(), ready_mediapipe.is_set(), ready_audio.is_set()])
        progress = done / 3.0
        pending  = []
        if not ready_camera.is_set():    pending.append("camara")
        if not ready_mediapipe.is_set(): pending.append("MediaPipe")
        if not ready_audio.is_set():     pending.append("audio")
        msg    = "Cargando: " + ", ".join(pending) + "..." if pending else "Todo listo!"
        frame  = draw(progress, msg)
        cv2.imshow("Simulacion", frame)
        cv2.waitKey(30)

    # Mostrar brevemente el 100% antes de pasar
    cv2.imshow("Simulacion", draw(1.0, "Todo listo!"))
    cv2.waitKey(600)