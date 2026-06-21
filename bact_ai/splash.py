import cv2
import numpy as np
import time
import math as _math

SW, SH = 600, 360

def _rounded_rect(img, x1, y1, x2, y2, r, color, thickness=-1):
    cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, thickness)
    cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, thickness)
    for cx, cy in [(x1+r, y1+r), (x2-r, y1+r), (x1+r, y2-r), (x2-r, y2-r)]:
        cv2.circle(img, (cx, cy), r, color, thickness)

def draw_splash(progress: float, msg: str, fw: int = SW, fh: int = SH) -> np.ndarray:
    img = np.zeros((fh, fw, 3), dtype=np.uint8)
    CW, CH = min(440, fw - 40), min(260, fh - 40)
    CX = (fw - CW) // 2
    CY = (fh - CH) // 2

    t_now  = time.time()
    pulse  = int(4 * abs(_math.sin(t_now * 3)))
    ICX, ICY = fw // 2, CY + 58
    ICON_R   = 26 + pulse

    cv2.circle(img, (ICX, ICY), ICON_R + 4, (40, 36, 60), -1)
    for deg in range(0, int(360 * progress), 3):
        rad = _math.radians(deg - 90)
        cv2.circle(img, (int(ICX + ICON_R * _math.cos(rad)),
                         int(ICY + ICON_R * _math.sin(rad))), 3, (0, 210, 100), -1)
    cv2.circle(img, (ICX, ICY), ICON_R - 7, (30, 26, 46), -1)

    pct_str = f"{int(progress * 100)}%"
    (pw, ph), _ = cv2.getTextSize(pct_str, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    cv2.putText(img, pct_str, (ICX - pw//2, ICY + ph//2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

    title = "Iniciando GestBact AI..."
    (tw, _), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.72, 2)
    cv2.putText(img, title, (fw//2 - tw//2, CY + 118),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, (240, 240, 255), 2, cv2.LINE_AA)

    (sw2, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
    cv2.putText(img, msg, (fw//2 - sw2//2, CY + 148),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (120, 200, 140), 1, cv2.LINE_AA)

    BX, BY = CX + 30, CY + 175
    BW = CW - 60
    _rounded_rect(img, BX, BY, BX + BW, BY + 6, 3, (50, 46, 70))
    fill = max(0, int(BW * progress))
    if fill > 0:
        _rounded_rect(img, BX, BY, BX + fill, BY + 6, 3, (0, 210, 100))

    return img