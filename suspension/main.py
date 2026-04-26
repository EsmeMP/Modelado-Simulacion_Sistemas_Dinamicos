"""
Simulación de Suspensión — v12
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Cambios vs v11:
  • Partículas eliminadas completamente
  • Llanta delantera reposicionada (wx_f_base 0.62 → 0.56)
  • Splash/pantalla de carga unificada en la ventana principal
  • Eliminado sistema de splash threading (ready_camera, etc.) innecesario
  • Eliminados _road_mask_buf, _road_ty_buf, _road_tex_px (broadcast H×W ya removido)
  • Eliminada clase Particle y código relacionado
  • Eliminado _mp_rgb_buf shape-check redundante (siempre coincide)
  • draw_graph_overlay: np.fromiter → np.array directo (más rápido con deques)
  • road_profile_vec_inplace simplificada (sin doble np.add innecesario)
  • overlay_alpha_fast: casting unsafe mantenido, sin cambios de lógica
  • Loop principal más limpio y directo
"""

import cv2
import mediapipe as mp
import numpy as np
import math as _math
import random
import datetime
import os
import threading
from collections import deque
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ══════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════
WIN_W, WIN_H   = 1100, 700
ROAD_Y_RATIO   = 0.62
DT             = 0.022
MAX_HIST       = 4000
GRAPH_H        = 160
WHEEL_SIZE     = 72
WHEEL_FRAMES   = 36
WHEEL_SPEED    = 5.5
ROAD_TEX_H     = 250
_RP_A1, _RP_W1 = 35.0, 0.015
_RP_A2, _RP_W2 = 18.0, 0.040

# ══════════════════════════════════════════════════════════
# IMÁGENES
# ══════════════════════════════════════════════════════════
car_path   = os.path.join(BASE_DIR, "car.png")
wheel_path = os.path.join(BASE_DIR, "wheel.png")

car_img   = cv2.imread(car_path,   cv2.IMREAD_UNCHANGED)
wheel_img = cv2.imread(wheel_path, cv2.IMREAD_UNCHANGED)

if car_img is None:
    car_img = np.zeros((120, 280, 4), dtype=np.uint8)
    car_img[:, :, :3] = 60
    car_img[:, :,  3] = 200
if wheel_img is None:
    wheel_img = np.zeros((72, 72, 4), dtype=np.uint8)
    cv2.circle(wheel_img, (36, 36), 34, (80, 80, 80, 220), -1)
    cv2.circle(wheel_img, (36, 36), 20, (30, 30, 30, 220), -1)

# ══════════════════════════════════════════════════════════
# MEDIAPIPE
# ══════════════════════════════════════════════════════════
mp_hands  = mp.solutions.hands
hands_sol = mp_hands.Hands(
    max_num_hands=1, model_complexity=0,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7,
)

# ══════════════════════════════════════════════════════════
# PARÁMETROS — 8 deslizadores
# ══════════════════════════════════════════════════════════
SLIDER_DEFS = [
    [0,  1200.0,   500.0,  2500.0, "masa m",    "kg",   "Masa suspendida"],
    [1, 18000.0,  3000.0, 30000.0, "rigidez k", "N/m",  "Rigidez resorte"],
    [2,  4200.0,   500.0,  6000.0, "amortig c", "Ns/m", "Amortiguamiento"],
    [3,    60.0,    20.0,   150.0, "masa mu",   "kg",   "Masa no suspendida"],
    [4, 180000.0,100000.0,300000.0,"rigidez kt","N/m",  "Rigidez llanta"],
    [5,    14.0,     5.0,    30.0, "velocidad", "u/f",  "Velocidad camino"],
    [6,   -86.0,   -60.0,    60.0, "altura",    "px",   "Altura vehiculo"],
    [7,    35.0,    10.0,    80.0, "amplitud",  "px",   "Amplitud baches"],
]
slider_vals = [s[1] for s in SLIDER_DEFS]

SL_PX = 8; SL_PY = 58; SL_W = 218; SL_RH = 30
SL_BX = 84; SL_BW = 118; SL_KR = 6

SLIDER_COLORS = [
    (68, 200, 255), (255, 120,  60), (80, 255, 160), (200, 100, 255),
    (255, 220,  50), (255,  80, 120), (130, 255, 200), (200, 180, 255),
]

_drag_idx    = -1
_knob_cache  = [(0, 0)] * 8
_slider_dark_buf = None
_slider_dark_key = None


def _update_knob_cache():
    bx0  = SL_PX + SL_BX
    half = SL_RH >> 1
    for idx in range(8):
        s      = SLIDER_DEFS[idx]
        lo, hi = s[2], s[3]
        t      = max(0.0, min(1.0, (slider_vals[idx] - lo) / (hi - lo)))
        _knob_cache[idx] = (bx0 + int(t * SL_BW), SL_PY + idx * SL_RH + half)


def draw_sliders(frame):
    global _slider_dark_buf, _slider_dark_key
    H, W = frame.shape[:2]
    ph   = SL_RH * 8 + 14
    x0   = SL_PX - 4;  y0 = SL_PY - 8
    x1   = SL_PX + SL_W + 4; y1 = SL_PY + ph
    x0c  = max(0, x0);  y0c = max(0, y0)
    x1c  = min(W, x1);  y1c = min(H, y1)
    if x1c > x0c and y1c > y0c:
        key = (x1c - x0c, y1c - y0c)
        if _slider_dark_key != key:
            _slider_dark_buf = np.full((key[1], key[0], 3), (4, 8, 20), dtype=np.uint8)
            _slider_dark_key = key
        roi = frame[y0c:y1c, x0c:x1c]
        cv2.addWeighted(_slider_dark_buf, 0.82, roi, 0.18, 0, dst=roi)

    cv2.rectangle(frame, (x0, y0), (x1, y1), (30, 55, 110), 1, cv2.LINE_AA)
    cv2.putText(frame, "PARAMETROS", (SL_PX + 2, SL_PY - 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.38, (100, 160, 255), 1, cv2.LINE_AA)

    bx0 = SL_PX + SL_BX; bx1 = bx0 + SL_BW
    for idx in range(8):
        s       = SLIDER_DEFS[idx]
        col     = SLIDER_COLORS[idx]
        kx, ky  = _knob_cache[idx]
        cv2.putText(frame, s[4], (SL_PX + 2, ky + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.30, (155, 175, 215), 1, cv2.LINE_AA)
        cv2.line(frame,   (bx0, ky), (bx1, ky), (35, 40, 70),    3, cv2.LINE_AA)
        cv2.line(frame,   (bx0, ky), (kx,  ky), col,              3, cv2.LINE_AA)
        cv2.circle(frame, (kx,  ky), SL_KR, col,           -1, cv2.LINE_AA)
        cv2.circle(frame, (kx,  ky), SL_KR, (255, 255, 255), 1, cv2.LINE_AA)
        v    = slider_vals[idx]
        vstr = f"{int(v)}" if abs(v) >= 10 else f"{v:.1f}"
        cv2.putText(frame, vstr, (bx1 + 4, ky + 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.28, col, 1, cv2.LINE_AA)

    mm2 = slider_vals[0]; kk2 = slider_vals[1]; cc2 = slider_vals[2]
    wn2 = _math.sqrt(max(kk2 / mm2, 1e-6))
    z2  = cc2 / (2 * _math.sqrt(max(kk2 * mm2, 1e-6)))
    rg  = "sub" if z2 < 0.999 else ("crit" if z2 < 1.001 else "sobre")
    iy  = SL_PY + 8 * SL_RH + 6
    cv2.putText(frame, f"wn={wn2:.2f}r/s z={z2:.3f}({rg})",
                (SL_PX + 2, iy + 12),
                cv2.FONT_HERSHEY_SIMPLEX, 0.30, (140, 220, 140), 1, cv2.LINE_AA)


def mouse_callback(event, mx, my, flags, param):
    global _drag_idx
    if event == cv2.EVENT_LBUTTONDOWN:
        for idx in range(8):
            kx, ky = _knob_cache[idx]
            if abs(mx - kx) <= SL_KR + 5 and abs(my - ky) <= SL_KR + 5:
                _drag_idx = idx; return
        bx0 = SL_PX + SL_BX; bx1 = bx0 + SL_BW
        for idx in range(8):
            _, ky = _knob_cache[idx]
            if bx0 <= mx <= bx1 and abs(my - ky) <= 10:
                _drag_idx = idx; return
    elif event == cv2.EVENT_MOUSEMOVE and _drag_idx >= 0:
        s   = SLIDER_DEFS[_drag_idx]
        bx0 = SL_PX + SL_BX
        t   = max(0.0, min(1.0, (mx - bx0) / SL_BW))
        slider_vals[_drag_idx] = s[2] + t * (s[3] - s[2])
    elif event == cv2.EVENT_LBUTTONUP:
        _drag_idx = -1

# ══════════════════════════════════════════════════════════
# FÍSICA
# ══════════════════════════════════════════════════════════
st_f = np.array([0.0, 0.0])
st_b = np.array([0.0, 0.0])
car_y_front_s = car_y_back_s = 0.0


def road_profile(x, amp=1.0):
    return amp * (_RP_A1 * _math.sin(x * _RP_W1) + _RP_A2 * _math.sin(x * _RP_W2))


# xs precalculados por ancho de ventana
_road_xs_f32  = {}
_road_pts_buf = {}
_tmp_f32      = np.empty(WIN_W, dtype=np.float32)
_tmp2_f32     = np.empty(WIN_W, dtype=np.float32)


def _ensure_road_buffers(fw):
    if fw not in _road_xs_f32:
        _road_xs_f32.clear(); _road_pts_buf.clear()
        xs = np.arange(fw, dtype=np.float32)
        _road_xs_f32[fw]  = xs
        _road_pts_buf[fw] = np.empty(fw, dtype=np.int32)
    return _road_xs_f32[fw], _road_pts_buf[fw]


def road_profile_vec_inplace(xs, offset, amp, out):
    """Perfil de carretera sin arrays temporales extra."""
    np.add(xs, offset, out=_tmp_f32)
    np.multiply(_tmp_f32, _RP_W1, out=_tmp_f32)
    np.sin(_tmp_f32, out=_tmp_f32)
    np.multiply(_tmp_f32, _RP_A1 * amp, out=out)

    np.add(xs, offset, out=_tmp2_f32)
    np.multiply(_tmp2_f32, _RP_W2, out=_tmp2_f32)
    np.sin(_tmp2_f32, out=_tmp2_f32)
    np.multiply(_tmp2_f32, _RP_A2 * amp, out=_tmp2_f32)
    np.add(out, _tmp2_f32, out=out)


# ── Métodos numéricos ──────────────────────────────────────
def analytic_solution(t_arr, mm, cc, kk, F0):
    wn  = _math.sqrt(kk / mm)
    z   = cc / (2 * _math.sqrt(kk * mm))
    xss = F0 / kk
    out = np.zeros(len(t_arr))
    for i, t in enumerate(t_arr):
        if t <= 0:
            out[i] = 0.0
        elif z < 0.9999:
            wd = wn * _math.sqrt(1 - z**2)
            out[i] = xss * (1 - _math.exp(-z*wn*t) * (
                _math.cos(wd*t) + (z / _math.sqrt(1 - z**2)) * _math.sin(wd*t)))
        elif z < 1.0001:
            out[i] = xss * (1 - _math.exp(-wn*t) * (1 + wn*t))
        else:
            r1 = -wn*(z + _math.sqrt(z**2 - 1))
            r2 = -wn*(z - _math.sqrt(z**2 - 1))
            A  = xss*r2/(r2 - r1); B = -xss*r1/(r2 - r1)
            out[i] = xss - A*_math.exp(r1*t) - B*_math.exp(r2*t)
    return out


def euler_method(x0, v0, F, dt, mm, cc, kk, steps):
    xs = np.zeros(steps); vs = np.zeros(steps)
    xs[0] = x0; vs[0] = v0
    for i in range(1, steps):
        a = (F - cc*vs[i-1] - kk*xs[i-1]) / mm
        vs[i] = vs[i-1] + a*dt
        xs[i] = xs[i-1] + vs[i-1]*dt
    return xs


def heun_method(x0, v0, F, dt, mm, cc, kk, steps):
    xs = np.zeros(steps); vs = np.zeros(steps)
    xs[0] = x0; vs[0] = v0
    for i in range(1, steps):
        x, v = xs[i-1], vs[i-1]
        a1   = (F - cc*v - kk*x) / mm
        xp   = x + a1*dt; vp = v + a1*dt
        a2   = (F - cc*vp - kk*xp) / mm
        vs[i] = v + (a1 + a2)*0.5*dt
        xs[i] = x + (v + vp)*0.5*dt
    return xs


def laplace_linearized(t_arr, x0, mm, cc, kk, F0):
    tau = mm/cc if cc > 0 else 1e-3
    return (F0/kk) * (1 - np.exp(-t_arr / tau))


def relative_error(N_num, N_ref):
    return np.abs(N_num - N_ref) / (np.abs(N_ref) + 1e-12) * 100.0

# ══════════════════════════════════════════════════════════
# GEOMETRÍA CHASIS
# ══════════════════════════════════════════════════════════
rear_mount_dx  = -48; rear_mount_dy  = 205
front_mount_dx =  48; front_mount_dy = 205
wheel_y_offset = 2
escala_susp    = 165

# ══════════════════════════════════════════════════════════
# HISTORIAL
# ══════════════════════════════════════════════════════════
hist_xf    = deque(maxlen=MAX_HIST); hist_xb    = deque(maxlen=MAX_HIST)
hist_vf    = deque(maxlen=MAX_HIST); hist_vb    = deque(maxlen=MAX_HIST)
hist_road  = deque(maxlen=MAX_HIST); hist_kk    = deque(maxlen=MAX_HIST)
hist_cc    = deque(maxlen=MAX_HIST); hist_pitch = deque(maxlen=MAX_HIST)
frame_count = 0

# ══════════════════════════════════════════════════════════
# RUEDAS precacheadas
# ══════════════════════════════════════════════════════════
wheel_angle = 0.0


def _build_wheel_cache(src, size, n):
    s = cv2.resize(src, (size, size)); c = size // 2
    return [cv2.warpAffine(s, cv2.getRotationMatrix2D((c, c), i*360.0/n, 1.0),
            (size, size), flags=cv2.INTER_LINEAR,
            borderValue=(0, 0, 0, 0)) for i in range(n)]


def _build_blur_cache(cache, n, blur_n=4):
    out = []
    for i in range(n):
        acc = cache[i].astype(np.float32)
        for j in range(1, blur_n):
            acc += cache[(i + j) % n].astype(np.float32)
        out.append(np.clip(acc / blur_n, 0, 255).astype(np.uint8))
    return out


wheel_cache      = _build_wheel_cache(wheel_img, WHEEL_SIZE, WHEEL_FRAMES)
wheel_blur_cache = _build_blur_cache(wheel_cache, WHEEL_FRAMES)

# ══════════════════════════════════════════════════════════
# OVERLAY ALPHA — buffers preallocados
# ══════════════════════════════════════════════════════════
_OV_MAX   = 512
_ov_roi_f = np.empty((_OV_MAX, _OV_MAX, 3), dtype=np.float32)
_ov_alpha = np.empty((_OV_MAX, _OV_MAX, 1), dtype=np.float32)
_ov_fgd   = np.empty((_OV_MAX, _OV_MAX, 3), dtype=np.float32)


def overlay_alpha_fast(img, ov, x, y):
    h, w = ov.shape[:2]
    x, y = int(x), int(y)
    x0 = max(0, x);  y0 = max(0, y)
    x1 = min(img.shape[1], x + w); y1 = min(img.shape[0], y + h)
    ox0 = x0 - x; oy0 = y0 - y
    ox1 = ox0 + (x1 - x0); oy1 = oy0 + (y1 - y0)
    if ox1 <= ox0 or oy1 <= oy0:
        return
    crop = ov[oy0:oy1, ox0:ox1]
    ch, cw = crop.shape[:2]
    a   = _ov_alpha[:ch, :cw]
    roi = _ov_roi_f[:ch, :cw]
    fgd = _ov_fgd[:ch, :cw]
    # Conversiones explícitas — sin casting unsafe que corrompe dtype en Windows
    a[:]   = crop[..., 3:].astype(np.float32) * (1.0 / 255.0)
    roi[:] = img[y0:y1, x0:x1].astype(np.float32)
    roi   *= (1.0 - a)
    fgd[:] = crop[..., :3].astype(np.float32)
    fgd   *= a
    roi   += fgd
    np.clip(roi, 0.0, 255.0, out=roi)
    img[y0:y1, x0:x1] = roi.astype(np.uint8)


def overlay_image_alpha(img, ov, x, y, scale=1.0):
    h, w = ov.shape[:2]
    sc   = cv2.resize(ov, (max(1, int(w*scale)), max(1, int(h*scale))),
                      interpolation=cv2.INTER_LINEAR)
    overlay_alpha_fast(img, sc, x, y)

# ══════════════════════════════════════════════════════════
# SOL + NUBES
# ══════════════════════════════════════════════════════════
clouds = [{"x": random.uniform(0, 1), "y": random.uniform(0.05, 0.30),
           "w": random.uniform(0.13, 0.22), "h": random.uniform(0.04, 0.09),
           "speed": random.uniform(0.00018, 0.00050)} for _ in range(5)]
_cloud_imgs  = []
_sun_img     = None
_overlay_key = None


def _make_sun(size=88):
    img = np.zeros((size, size, 4), dtype=np.uint8); c = size // 2
    for r in range(size//2, 8, -5):
        t = 1.0 - r/(size//2); a = int(25*t)
        cv2.circle(img, (c, c), r, (255, 240, 140, a), -1, cv2.LINE_AA)
    cv2.circle(img, (c, c), 22, (210, 245, 255, 220), -1, cv2.LINE_AA)
    cv2.circle(img, (c, c), 14, (235, 255, 255, 255), -1, cv2.LINE_AA)
    img[:, :, :3] = cv2.GaussianBlur(img[:, :, :3], (9, 9), 0)
    return img


def _make_cloud(fw, fh, cloud):
    cw  = int(cloud["w"]*fw); ch = max(10, int(cloud["h"]*fh*0.35))
    img = np.zeros((ch*2+8, cw+12, 4), dtype=np.uint8)
    cx0, cy0 = 6, ch+4
    for bx, by, br in [(0, 0, int(ch*.9)), (cw//4, -ch//4, int(ch*1.1)),
                       (cw//2, 0, int(ch*.95)), (3*cw//4, -ch//5, int(ch*.85)),
                       (cw, 0, int(ch*.75))]:
        cv2.ellipse(img, (cx0+bx, cy0+by),
                    (max(1, br), max(1, int(br*.52))),
                    0, 0, 360, (252, 254, 255, 175), -1, cv2.LINE_AA)
    img[:, :, :3] = cv2.GaussianBlur(img[:, :, :3], (7, 7), 0)
    return img


def _ensure_overlay_cache(fw, fh):
    global _cloud_imgs, _sun_img, _overlay_key
    if _overlay_key != (fw, fh):
        _sun_img     = _make_sun(88)
        _cloud_imgs  = [_make_cloud(fw, fh, c) for c in clouds]
        _overlay_key = (fw, fh)


def draw_sun_and_clouds(frame, fw, fh, horizon_y):
    _ensure_overlay_cache(fw, fh)
    overlay_alpha_fast(frame, _sun_img,
                       int(fw*.78) - 44, int(horizon_y*.22) - 44)
    for i, cloud in enumerate(clouds):
        cloud["x"] += cloud["speed"]
        if cloud["x"] > 1.15:
            cloud["x"] = -0.25
        cimg = _cloud_imgs[i]
        overlay_alpha_fast(frame, cimg,
            int(cloud["x"]*fw) - cimg.shape[1]//2,
            int(cloud["y"]*horizon_y) - cimg.shape[0]//2)

# ══════════════════════════════════════════════════════════
# CARRETERA ONDULADA
# ══════════════════════════════════════════════════════════
_road_tex     = None
_road_tex_key = None


def _make_road_tex(fw, h):
    rng   = np.random.default_rng()
    noise = cv2.GaussianBlur(
        rng.integers(16, 38, (h, fw), dtype=np.uint8), (5, 5), 0)
    base  = np.full((h, fw, 3), (34, 34, 42), dtype=np.uint8)
    tex   = cv2.addWeighted(base, 0.68,
                            cv2.cvtColor(noise, cv2.COLOR_GRAY2BGR), 0.32, 0)
    t_row = np.linspace(0.70, 1.0, h, dtype=np.float32).reshape(-1, 1, 1)
    tex   = np.clip(tex.astype(np.float32) * t_row, 0, 255).astype(np.uint8)
    lx    = max(0, fw//2 - int(fw*.28))
    rx    = min(fw-1, fw//2 + int(fw*.28))
    cv2.line(tex, (lx, 0), (lx, h-1), (215, 215, 215), 2, cv2.LINE_AA)
    cv2.line(tex, (rx, 0), (rx, h-1), (215, 215, 215), 2, cv2.LINE_AA)
    return tex


def _ensure_road_tex(fw):
    global _road_tex, _road_tex_key
    if _road_tex_key != fw:
        _road_tex     = _make_road_tex(fw, ROAD_TEX_H)
        _road_tex_key = fw


# Buffers scanline reutilizables
_scan_below  = None
_scan_ty     = None
_scan_tex_px = None
_scan_key    = None


def draw_road_wavy(frame, fw, fh, road_y, offset_val, amp=1.0):
    global _scan_below, _scan_ty, _scan_tex_px, _scan_key
    _ensure_road_tex(fw)
    xs, pts_buf = _ensure_road_buffers(fw)

    road_profile_vec_inplace(xs, offset_val, amp, _tmp_f32)
    np.add(road_y, _tmp_f32, out=_tmp_f32)
    np.clip(_tmp_f32, 0, fh-1, out=_tmp_f32)
    pts_y    = pts_buf
    pts_y[:] = _tmp_f32.astype(np.int32)

    key = (fw, fh)
    if _scan_key != key:
        _scan_below  = np.empty((fh, fw), dtype=np.bool_)
        _scan_ty     = np.empty((fh, fw), dtype=np.int32)
        _scan_tex_px = np.empty((fh, fw, 3), dtype=np.uint8)
        _scan_key    = key

    rows = np.arange(fh, dtype=np.int32)
    np.greater_equal(rows[:, np.newaxis], pts_y[np.newaxis, :], out=_scan_below)
    np.subtract(rows[:, np.newaxis], pts_y[np.newaxis, :], out=_scan_ty)
    np.clip(_scan_ty, 0, ROAD_TEX_H-1, out=_scan_ty)
    xs_int = xs.astype(np.int32) % fw
    _scan_tex_px[:] = _road_tex[_scan_ty, xs_int]

    # Indexación directa — segura en Windows/OpenCV 4.11 (evita np.copyto con where=)
    mask = _scan_below  # bool (fh, fw)
    frame[mask] = _scan_tex_px[mask]

    border_pts = np.stack(
        [np.arange(fw, dtype=np.int32), pts_y], axis=1
    ).reshape(-1, 1, 2)
    cv2.polylines(frame, [border_pts], False, (200, 200, 215), 2, cv2.LINE_AA)

    cx     = fw // 2; dash = 24; gap = 14; period = dash + gap
    phase  = int(offset_val * .85) % period
    y0_d   = int(pts_y[cx]) + 6
    starts = np.arange(-1, (fh - y0_d) // period + 3) * period + y0_d - phase
    ends   = np.minimum(fh - 1, starts + dash)
    starts = np.maximum(int(pts_y[cx]), starts)
    for sy, ey in zip(starts.tolist(), ends.tolist()):
        if ey > sy:
            cv2.line(frame, (cx, int(sy)), (cx, int(ey)),
                     (210, 188, 42), 2, cv2.LINE_AA)

    return pts_y

# ══════════════════════════════════════════════════════════
# GRÁFICAS EN TIEMPO REAL
# ══════════════════════════════════════════════════════════
_graph_dark_buf = {}
_graph_pts_buf  = np.empty((WIN_W, 1, 2), dtype=np.int32)


def draw_graph_overlay(frame, road_y, fw, fh):
    y0      = road_y + 3
    panel_h = min(GRAPH_H, fh - y0 - 2)
    if panel_h < 40:
        return
    gw = fw // 2; gh = panel_h // 2
    key = (fw, panel_h)
    if key not in _graph_dark_buf:
        _graph_dark_buf.clear()
        _graph_dark_buf[key] = np.full((panel_h, fw, 3), (10, 10, 22), dtype=np.uint8)
    panel_roi = frame[y0:y0+panel_h, 0:fw]
    cv2.addWeighted(_graph_dark_buf[key], 0.80, panel_roi, 0.20, 0, dst=panel_roi)

    cv2.line(frame, (gw, y0), (gw, y0+panel_h), (30, 30, 55), 1)
    cv2.line(frame, (0, y0+gh), (fw, y0+gh),    (30, 30, 55), 1)

    graphs = [
        (hist_xf,    (255, 102, 136), "Delantera x_f (m)", 0, 0),
        (hist_xb,    (68,  170, 255), "Trasera x_b (m)",   1, 0),
        (hist_pitch, (255, 221,  68), "Pitch (grados)",    0, 1),
        (hist_kk,    (68,  255, 170), "Rigidez k (N/m)",   1, 1),
    ]
    MT = 20; MB = 6; MLR = 6
    plot_w = gw - MLR*2; plot_h = gh - MT - MB

    for data, color, label, col, row in graphs:
        n = len(data)
        if n < 2:
            continue
        x0c = col * gw; y0c = y0 + row * gh
        window = np.array(data, dtype=np.float32)[-plot_w:]
        nw     = len(window)
        mn     = float(window.min()); mx2 = float(window.max())
        if mx2 == mn:
            mx2 = mn + 1e-6

        px = _graph_pts_buf[:nw, 0, 0]
        py = _graph_pts_buf[:nw, 0, 1]
        np.copyto(px,
                  np.linspace(x0c + MLR, x0c + MLR + plot_w,
                              nw, dtype=np.float32).astype(np.int32))
        tmp_f = (1.0 - (window - mn) / (mx2 - mn)) * plot_h + (y0c + MT)
        np.floor(tmp_f, out=tmp_f)
        np.clip(tmp_f, y0c + MT, y0c + gh - MB, out=tmp_f)
        np.copyto(py, tmp_f, casting='unsafe')

        pts_view = _graph_pts_buf[:nw]
        if mn < 0 < mx2:
            zy = int(y0c + MT + plot_h - (0 - mn)/(mx2 - mn)*plot_h)
            cv2.line(frame, (x0c+MLR, zy), (x0c+MLR+plot_w, zy),
                     (55, 55, 75), 1, cv2.LINE_AA)
        cv2.polylines(frame, [pts_view], False, color, 1, cv2.LINE_AA)
        cv2.circle(frame, (int(px[-1]), int(py[-1])), 3,
                   (255, 255, 255), -1, cv2.LINE_AA)
        vstr = (f"{window[-1]:+.3f}" if abs(window[-1]) < 1000
                else f"{int(window[-1]):,}")
        cv2.putText(frame, label, (x0c+5, y0c+14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1, cv2.LINE_AA)
        cv2.putText(frame, vstr,  (x0c+gw-68, y0c+14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (190, 200, 220), 1, cv2.LINE_AA)

# ══════════════════════════════════════════════════════════
# HELPERS ESCENA
# ══════════════════════════════════════════════════════════
def draw_spring(frame, x1, y1, x2, y2, color=(120, 110, 40), n_coils=5):
    dx = x2 - x1; dy = y2 - y1
    lng = _math.hypot(dx, dy)
    if lng < 4:
        return
    ux = dx/lng; uy = dy/lng
    steps  = n_coils * 14
    pts    = np.empty((steps+1, 1, 2), dtype=np.int32)
    inv    = 1.0 / steps
    nx     = -uy; ny = -ux
    pi2n   = n_coils * 2 * _math.pi
    for i in range(steps+1):
        ts   = i * inv
        env  = _math.sin(_math.pi * ts)
        wave = 4 * env * _math.sin(ts * pi2n)
        pts[i, 0, 0] = int(x1 + ux*lng*ts + nx*wave)
        pts[i, 0, 1] = int(y1 + uy*lng*ts + ny*wave)
    cv2.polylines(frame, [pts], False, color, 1, cv2.LINE_AA)


def draw_shock(frame, x1, y1, x2, y2, col=(55, 55, 68)):
    cv2.line(frame, (x1, y1), (x2, y2), col, 1, cv2.LINE_AA)


def draw_shadow(frame, cx, ry, car_w, pitch):
    ew = max(12, int(car_w*.50 - abs(pitch)*1.5))
    eh = max(3,  int(9 - abs(pitch)*.3))
    y0 = max(0, ry);  y1 = min(frame.shape[0], ry + eh*3 + 4)
    x0 = max(0, cx-ew-6); x1 = min(frame.shape[1], cx+ew+6)
    sub = frame[y0:y1, x0:x1]
    if sub.size == 0:
        return
    mask = np.zeros(sub.shape[:2], dtype=np.float32)
    cv2.ellipse(mask, (sub.shape[1]//2, sub.shape[0]//2),
                (ew, eh), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
    mask = cv2.GaussianBlur(mask, (7, 7), 0)[..., None]
    subf = sub.astype(np.float32)
    subf *= (1.0 - mask * 0.65)
    np.clip(subf, 0.0, 255.0, out=subf)
    np.copyto(frame[y0:y1, x0:x1], subf, casting='unsafe')


def add_car_lighting(frame, car_x, car_cy, car_w, car_h, pitch):
    hx = car_x + car_w//2; hy = car_cy - int(car_h*.48)
    hw = int(car_w*.38);    hh = max(4, int(car_h*.12))
    y0 = max(0, hy-hh); y1 = min(frame.shape[0], hy+hh)
    x0 = max(0, hx-hw); x1 = min(frame.shape[1], hx+hw)
    sub = frame[y0:y1, x0:x1]
    if sub.size == 0:
        return
    cv2.addWeighted(np.full_like(sub, (235, 245, 255)),
                    0.07, sub, 0.93, 0, dst=sub)


def draw_hand_skeleton(frame, hand_lms, fw, fh):
    for conn in mp_hands.HAND_CONNECTIONS:
        p0 = hand_lms.landmark[conn[0]]
        p1 = hand_lms.landmark[conn[1]]
        cv2.line(frame,
                 (int(p0.x*fw), int(p0.y*fh)),
                 (int(p1.x*fw), int(p1.y*fh)),
                 (0, 185, 165), 1, cv2.LINE_AA)
    for lm in hand_lms.landmark:
        cv2.circle(frame, (int(lm.x*fw), int(lm.y*fh)),
                   3, (0, 240, 205), -1, cv2.LINE_AA)

# ══════════════════════════════════════════════════════════
# REPORTE MATPLOTLIB
# Usamos Agg (sin ventana) para que funcione desde hilos secundarios
# en Windows sin el error "main thread is not in main loop" de Tkinter.
# ══════════════════════════════════════════════════════════
import matplotlib
matplotlib.use("Agg")   # backend no-interactivo: solo guarda a disco
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import warnings; warnings.filterwarnings("ignore")

DARK_BG    = "#0a0a1a"; C_ANA = "#00ff88"; C_EULER = "#ff6644"
C_HEUN     = "#44aaff"; C_LAPLACE = "#ffdd44"
C_REAL     = "#ff44ff"; C_DERIV   = "#ff9900"
_report_running = False


def _ax_style(ax, title="", xlabel="Tiempo (s)", ylabel=""):
    ax.set_facecolor("#080818")
    ax.tick_params(colors="lightgray", labelsize=8.5)
    for sp in ax.spines.values():
        sp.set_color("#333355")
    ax.grid(alpha=0.15, color="gray")
    ax.set_title(title, color="white", fontsize=11)
    ax.set_xlabel(xlabel, color="lightgray")
    ax.set_ylabel(ylabel, color="lightgray")


def _run_report(snap_kk, snap_cc, snap_xf, snap_xb, snap_pitch,
                hxf, hvf, hroad, hkk, hcc, hpitch, nf):
    global _report_running
    try:
        n = len(hxf)
        if n < 10:
            print("[REPORTE] Sin datos suficientes."); return
        t       = np.arange(n) * DT
        x_num   = np.array(hxf)
        road_n  = np.array(hroad)
        kk_m    = float(np.mean(hkk)); cc_m = float(np.mean(hcc))
        F0      = float(np.mean(np.abs(road_n)*53*175))
        masa_r  = slider_vals[0]
        N_ana   = analytic_solution(t, masa_r, cc_m, kk_m, F0)
        N_euler = euler_method(0.0, 0.0, F0, DT, masa_r, cc_m, kk_m, n)
        N_heun  = heun_method(0.0, 0.0, F0, DT, masa_r, cc_m, kk_m, n)
        N_lap   = laplace_linearized(t, 0.0, masa_r, cc_m, kk_m, F0)
        err_e   = relative_error(N_euler, N_ana)
        err_h   = relative_error(N_heun,  N_ana)
        dN      = np.gradient(N_euler, DT)
        wn      = _math.sqrt(kk_m/masa_r)
        z       = cc_m / (2*_math.sqrt(kk_m*masa_r))
        regime  = ("Subamortiguado" if z < 0.999 else
                   ("Criticamente amortiguado" if z < 1.001 else "Sobreamortiguado"))

        plt.style.use("dark_background")
        fig = plt.figure(figsize=(16, 10), facecolor=DARK_BG)
        fig.suptitle(
            f"Análisis Matemático — Suspensión  "
            f"(k={int(kk_m)}, c={int(cc_m)}, m={int(masa_r)}kg)",
            fontsize=14, color="white", fontweight="bold", y=0.98)
        gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.45, wspace=0.35,
                               left=0.07, right=0.97, top=0.93, bottom=0.07)

        ax1 = fig.add_subplot(gs[0, :2])
        ax1.plot(t, N_ana,   color=C_ANA,     lw=2.5, label="Analítica exacta", zorder=5)
        ax1.plot(t, N_euler, color=C_EULER,   lw=1.8, label="Euler",   ls="--")
        ax1.plot(t, N_heun,  color=C_HEUN,    lw=1.8, label="Heun",    ls="-.")
        ax1.plot(t, N_lap,   color=C_LAPLACE, lw=1.5, label="Laplace", ls=":", alpha=0.8)
        ax1.legend(fontsize=8, loc="lower right",
                   facecolor="#111122", edgecolor="#333355")
        _ax_style(ax1, "Comparación de Soluciones", "Tiempo (s)", "Desplazamiento [m]")

        ax2 = fig.add_subplot(gs[0, 2])
        ax2.plot(t, x_num, color=C_REAL, lw=1.8, label="Simulación")
        ax2.plot(t, N_ana, color=C_ANA,  lw=1.5, ls="--", alpha=0.6, label="Modelo")
        ax2.legend(fontsize=7, facecolor="#111122")
        _ax_style(ax2, "Simulación vs Modelo")

        ax3 = fig.add_subplot(gs[1, 0])
        ax3.fill_between(t, err_e, alpha=0.3, color=C_EULER)
        ax3.plot(t, err_e, color=C_EULER, lw=1.8)
        _ax_style(ax3, "Error Euler", "Tiempo (s)", "Error %")

        ax4 = fig.add_subplot(gs[1, 1])
        ax4.fill_between(t, err_h, alpha=0.3, color=C_HEUN)
        ax4.plot(t, err_h, color=C_HEUN, lw=1.8)
        _ax_style(ax4, "Error Heun", "Tiempo (s)", "Error %")

        ax5 = fig.add_subplot(gs[1, 2])
        ax5.plot(t, dN, color=C_DERIV, lw=2.0)
        ax5.fill_between(t, dN, alpha=0.2, color=C_DERIV)
        ax5.axhline(0, color="gray", lw=0.8, ls="--")
        _ax_style(ax5, "dN/dt", "Tiempo (s)", "m/s²")

        ax6 = fig.add_subplot(gs[2, :]); ax6.set_facecolor("#05050f"); ax6.axis("off")
        em = float(err_e.mean()); hm = float(err_h.mean())
        ax6.text(0.01, 0.95,
            f"  MÉTRICAS\n  Euler max={err_e.max():.3f}%  med={em:.3f}%\n"
            f"  Heun  max={err_h.max():.3f}%  med={hm:.3f}%\n"
            f"  Mejora Heun: {max(0,em-hm):.3f}%\n  N∞≈{float(N_ana[-1]):.4f}m",
            transform=ax6.transAxes, color="#44ffaa", fontsize=9,
            va="top", fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor="#0a1a0a", edgecolor="#224422", alpha=0.8))
        ax6.text(0.38, 0.95,
            "  ECUACIONES\n  m·x''+ c·x'+ k·x = F(t)\n"
            "  Analítica: N(t) → solución exacta\n"
            "  Euler: N_{n+1}=Nₙ+h·f(Nₙ)  O(h)\n"
            "  Heun:  N_{n+1}=Nₙ+h/2·[f+f*]  O(h²)",
            transform=ax6.transAxes, color="#aaddff", fontsize=9,
            va="top", fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor="#0a0a1a", edgecolor="#222244", alpha=0.8))
        ax6.text(0.75, 0.95,
            f"  CONDICIONES\n  m={int(masa_r)}kg  k={int(kk_m):,}  "
            f"c={int(cc_m):,}\n"
            f"  wn={wn:.3f}r/s  z={z:.5f}\n"
            f"  Régimen: {regime}\n  Pitch: {snap_pitch:+.2f}°",
            transform=ax6.transAxes, color="#ffdd88", fontsize=9,
            va="top", fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor="#1a1500", edgecolor="#443300", alpha=0.8))

        os.makedirs("data", exist_ok=True)
        ts    = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = os.path.join("data", f"analisis_{ts}.png")
        plt.savefig(fname, dpi=120, bbox_inches="tight", facecolor=DARK_BG)
        plt.close()
        print(f"[REPORTE] Guardado: {fname}")
        try:
            import sys, subprocess; ap = os.path.abspath(fname)
            if sys.platform == 'win32':   os.startfile(ap)
            elif sys.platform == 'darwin': subprocess.Popen(['open', ap])
            else:                          subprocess.Popen(['xdg-open', ap])
        except Exception:
            pass
    finally:
        _report_running = False


def generate_matplotlib_report(snap_kk, snap_cc, snap_xf, snap_xb, snap_pitch):
    global _report_running
    if _report_running:
        print("[REPORTE] Ya generándose."); return
    _report_running = True
    th = threading.Thread(
        target=_run_report,
        args=(snap_kk, snap_cc, snap_xf, snap_xb, snap_pitch,
              list(hist_xf), list(hist_vf), list(hist_road),
              list(hist_kk),  list(hist_cc), list(hist_pitch), frame_count),
        daemon=True)
    th.start()

# ══════════════════════════════════════════════════════════
# PANTALLA DE CARGA
# ══════════════════════════════════════════════════════════
def _rounded_rect(img, x1, y1, x2, y2, r, color, thickness=-1):
    cv2.rectangle(img, (x1 + r, y1), (x2 - r, y2), color, thickness)
    cv2.rectangle(img, (x1, y1 + r), (x2, y2 - r), color, thickness)
    for cx, cy in [(x1+r, y1+r), (x2-r, y1+r), (x1+r, y2-r), (x2-r, y2-r)]:
        cv2.circle(img, (cx, cy), r, color, thickness)


def draw_splash(progress: float, msg: str, fw: int, fh: int) -> np.ndarray:
    img = np.zeros((fh, fw, 3), dtype=np.uint8)   # fondo negro puro

    CW, CH = min(440, fw - 40), min(260, fh - 40)
    CX     = (fw - CW) // 2
    CY     = (fh - CH) // 2

    t_now  = time.time()
    pulse  = int(4 * abs(_math.sin(t_now * 3)))
    ICX    = fw // 2
    ICY    = CY + 58
    ICON_R = 26 + pulse

    cv2.circle(img, (ICX, ICY), ICON_R + 4, (40, 36, 60), -1)
    total_angle = int(360 * progress)
    for deg in range(0, total_angle, 3):
        rad = _math.radians(deg - 90)
        x   = int(ICX + ICON_R * _math.cos(rad))
        y   = int(ICY + ICON_R * _math.sin(rad))
        cv2.circle(img, (x, y), 3, (0, 210, 100), -1)
    cv2.circle(img, (ICX, ICY), ICON_R - 7, (30, 26, 46), -1)

    pct_str     = f"{int(progress*100)}%"
    (pw, ph), _ = cv2.getTextSize(pct_str, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    cv2.putText(img, pct_str, (ICX - pw//2, ICY + ph//2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1, cv2.LINE_AA)

    title = "Iniciando simulacion..."
    (tw, _), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.72, 2)
    cv2.putText(img, title, (fw//2 - tw//2, CY + 118),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, (240, 240, 255), 2, cv2.LINE_AA)

    (sw2, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.42, 1)
    cv2.putText(img, msg, (fw//2 - sw2//2, CY + 148),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (120, 200, 140), 1, cv2.LINE_AA)

    BX, BY = CX + 30, CY + 175
    BW, BH = CW - 60, 6
    _rounded_rect(img, BX, BY, BX+BW, BY+BH, 3, (50, 46, 70))
    fill = max(0, int(BW * progress))
    if fill > 0:
        _rounded_rect(img, BX, BY, BX+fill, BY+BH, 3, (0, 210, 100))

    return img

    CW, CH = min(480, fw - 40), min(280, fh - 40)
    CX     = (fw - CW) // 2
    CY     = (fh - CH) // 2

    # Card con borde
    _rounded_rect(img, CX, CY, CX+CW, CY+CH, 14, (18, 16, 36))
    _rounded_rect(img, CX, CY, CX+CW, CY+CH, 14, (50, 44, 100), 2)

    # Ícono animado
    t_now  = time.time()
    pulse  = int(4 * abs(_math.sin(t_now * 3)))
    ICX    = fw // 2
    ICY    = CY + 72
    ICON_R = 28 + pulse

    cv2.circle(img, (ICX, ICY), ICON_R + 5, (30, 26, 52), -1)
    total_angle = int(360 * progress)
    for deg in range(0, total_angle, 3):
        rad = _math.radians(deg - 90)
        x   = int(ICX + ICON_R * _math.cos(rad))
        y   = int(ICY + ICON_R * _math.sin(rad))
        cv2.circle(img, (x, y), 3, (0, 210, 100), -1)
    cv2.circle(img, (ICX, ICY), ICON_R - 8, (20, 18, 36), -1)

    pct_str     = f"{int(progress*100)}%"
    (pw, ph), _ = cv2.getTextSize(pct_str, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
    cv2.putText(img, pct_str, (ICX - pw//2, ICY + ph//2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (200, 200, 210), 1, cv2.LINE_AA)

    # Título
    title = "Iniciando simulacion..."
    (tw, _), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.80, 2)
    cv2.putText(img, title, (fw//2 - tw//2, CY + 138),
                cv2.FONT_HERSHEY_SIMPLEX, 0.80, (240, 240, 255), 2, cv2.LINE_AA)

    # Subtítulo
    (sw2, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.44, 1)
    cv2.putText(img, msg, (fw//2 - sw2//2, CY + 168),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (100, 200, 140), 1, cv2.LINE_AA)

    # Barra de progreso
    BX = CX + 36; BY = CY + 196
    BW = CW - 72; BH = 8
    _rounded_rect(img, BX, BY, BX+BW, BY+BH, 4, (40, 36, 68))
    fill = max(0, int(BW * progress))
    if fill > 6:
        _rounded_rect(img, BX, BY, BX+fill, BY+BH, 4, (0, 210, 100))

    return img

# ══════════════════════════════════════════════════════════
# VENTANA Y CÁMARA
# ══════════════════════════════════════════════════════════
cv2.namedWindow("Simulacion de Suspension", cv2.WINDOW_NORMAL)
cv2.resizeWindow("Simulacion de Suspension", WIN_W, WIN_H)
cv2.moveWindow("Simulacion de Suspension", 0, 30)
cv2.setMouseCallback("Simulacion de Suspension", mouse_callback)

# ── Mostrar splash mientras abre la cámara ─────────────────
cap = None

def _open_camera():
    global cap
    c = cv2.VideoCapture(0)
    c.set(cv2.CAP_PROP_FRAME_WIDTH,  WIN_W)
    c.set(cv2.CAP_PROP_FRAME_HEIGHT, WIN_H)
    c.set(cv2.CAP_PROP_FPS, 30)
    c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    cap = c

cam_thread = threading.Thread(target=_open_camera, daemon=True)
cam_thread.start()

# Splash animado mientras la cámara y mediapipe cargan
_splash_t0 = time.time()
while cam_thread.is_alive() or cap is None:
    elapsed  = time.time() - _splash_t0
    progress = min(0.90, elapsed / 2.5)          # simula carga hasta 90%
    msg      = "Abriendo camara..."
    frame_s  = draw_splash(progress, msg, WIN_W, WIN_H)
    cv2.imshow("Simulacion de Suspension", frame_s)
    if cv2.waitKey(30) == 27:
        cv2.destroyAllWindows()
        import sys; sys.exit(0)

# Breve destello al 100%
cv2.imshow("Simulacion de Suspension",
           draw_splash(1.0, "Todo listo!", WIN_W, WIN_H))
cv2.waitKey(500)

car_w   = 280
ratio   = car_w / car_img.shape[1]
offset  = 0.0

# Buffer RGB para MediaPipe
_mp_rgb_buf = np.empty((WIN_H, WIN_W, 3), dtype=np.uint8)

# Cache rotación del coche
_car_rot_cache_pitch = None
_car_rot_cache_img   = None
_car_h_orig  = car_img.shape[0]
_car_w_orig  = car_img.shape[1]
_car_cx      = _car_w_orig // 2
_car_cy_orig = _car_h_orig // 2

# ══════════════════════════════════════════════════════════
# LOOP PRINCIPAL
# ══════════════════════════════════════════════════════════
while True:
    ret, raw = cap.read()

    if ret and isinstance(raw, np.ndarray) and raw.dtype == np.uint8:
        if not raw.flags['C_CONTIGUOUS']:
            raw = np.ascontiguousarray(raw)
        frame = cv2.flip(raw, 1)
        if not frame.flags['C_CONTIGUOUS']:
            frame = np.ascontiguousarray(frame)
    else:
        frame = np.zeros((WIN_H, WIN_W, 3), dtype=np.uint8)

    if frame.shape[:2] != (WIN_H, WIN_W):
        frame = cv2.resize(frame, (WIN_W, WIN_H))
        if not frame.flags['C_CONTIGUOUS']:
            frame = np.ascontiguousarray(frame)

    fh, fw = frame.shape[:2]
    frame_count += 1

    # Leer sliders
    masa            = float(slider_vals[0])
    kk              = float(slider_vals[1])
    cc_val          = float(slider_vals[2])
    mu              = float(slider_vals[3])
    kt              = float(slider_vals[4])
    road_speed      = float(slider_vals[5])
    car_draw_offset = int(slider_vals[6])
    road_amp        = float(slider_vals[7]) / 35.0

    _update_knob_cache()

    road_y    = int(fh * ROAD_Y_RATIO)
    horizon_y = road_y - 6

    # MediaPipe
    cv2.cvtColor(frame, cv2.COLOR_BGR2RGB, dst=_mp_rgb_buf)
    result = hands_sol.process(_mp_rgb_buf)

    apertura = 0.0
    if result.multi_hand_landmarks:
        hl       = result.multi_hand_landmarks[0]
        apertura = float(hl.landmark[5].y - hl.landmark[8].y) * 3.5
        apertura = max(0.0, min(1.0, apertura))
        draw_hand_skeleton(frame, hl, fw, fh)

    kk_eff   = kk     * (1.0 - apertura * 0.80)
    cc_eff   = cc_val * (1.0 - apertura * 0.80)
    masa_eff = masa + mu * 0.15

    offset += road_speed
    road_f  = road_profile(offset + 55.0, road_amp)
    road_b  = road_profile(offset - 55.0, road_amp)

    # Física delantera
    x_f  = st_f[0]; v_f_ = st_f[1]
    a_f  = (road_f * 175.0 - cc_eff*v_f_ - kk_eff*x_f) / masa_eff
    v_f2 = v_f_ + a_f*DT; x_f2 = x_f + v_f2*DT
    st_f[0] = x_f2; st_f[1] = v_f2
    x_f = x_f2; v_f = v_f2

    # Física trasera
    x_b  = st_b[0]; v_b_ = st_b[1]
    a_b  = (road_b * 175.0 - cc_eff*v_b_ - kk_eff*x_b) / masa_eff
    v_b2 = v_b_ + a_b*DT; x_b2 = x_b + v_b2*DT
    st_b[0] = x_b2; st_b[1] = v_b2
    x_b = x_b2; v_b = v_b2

    hist_xf.append(x_f);  hist_xb.append(x_b)
    hist_vf.append(v_f);  hist_vb.append(v_b)
    hist_road.append(road_f / 53.0)
    hist_kk.append(kk_eff); hist_cc.append(cc_eff)

    # Render
    draw_sun_and_clouds(frame, fw, fh, horizon_y)
    pts_y = draw_road_wavy(frame, fw, fh, road_y, offset, road_amp)
    # Garantizar frame uint8 C-contiguo tras operaciones numpy (Windows/OpenCV 4.11)
    if frame.dtype != np.uint8 or not frame.flags['C_CONTIGUOUS']:
        frame = np.ascontiguousarray(frame, dtype=np.uint8)

    # ── Posición llantas
    # Delantera movida hacia atrás: 0.62 → 0.56
    wx_f_base = int(fw * .56); wx_b_base = int(fw * .38)
    wheel_y_f = int(pts_y[min(wx_f_base, fw-1)]) + wheel_y_offset
    wheel_y_b = int(pts_y[min(wx_b_base, fw-1)]) + wheel_y_offset

    kt_factor = 1.0 - (kt - 100000) / 400000 * 0.3
    raw_f_pos = wheel_y_f - 78.0 + x_f * escala_susp * kt_factor
    raw_b_pos = wheel_y_b - 78.0 + x_b * escala_susp * kt_factor

    sm  = 0.80 if apertura < 0.5 else 0.93
    sm1 = 1.0 - sm
    car_y_front_s = sm * car_y_front_s + sm1 * raw_f_pos
    car_y_back_s  = sm * car_y_back_s  + sm1 * raw_b_pos
    car_y_f = int(car_y_front_s); car_y_b = int(car_y_back_s)

    if apertura < 0.5:
        pitch = _math.degrees(_math.atan2(car_y_f - car_y_b, 140)) * .5
        extra = float(x_f - x_b) * 32
        extra = max(-8.0, min(8.0, extra))
        pitch = max(-14.0, min(14.0, pitch + extra))
    else:
        sp2     = max(-6.0, min(6.0, float(wheel_y_f - wheel_y_b) * .13))
        car_y_f = int(wheel_y_f - 78 + sp2*.4)
        car_y_b = int(wheel_y_b - 78 - sp2*.4)
        pitch   = 0.0

    hist_pitch.append(pitch)

    max_yf = wheel_y_f - 110; max_yb = wheel_y_b - 110
    if car_y_f < max_yf: car_y_f = max_yf
    if car_y_b < max_yb: car_y_b = max_yb
    car_center_y = (car_y_f + car_y_b) >> 1

    # Shake por baches
    bump = abs(road_f - road_b)   # simplificado: diferencia delantera-trasera
    shake_x = shake_ys = 0
    if apertura < 0.5 and bump > 14:
        shake_x  = random.randint(-2, 2)
        shake_ys = random.randint(-2, 2)

    car_x = int(fw * .38) - 45
    sc_x  = int(car_x + _car_w_orig * ratio / 2 + shake_x)
    sc_y  = int(car_center_y + car_draw_offset + _car_h_orig * ratio / 2 + shake_ys)

    ct_  = _math.cos(_math.radians(pitch))
    st_v = _math.sin(_math.radians(pitch))

    def rmount(ddx, ddy):
        return (int(sc_x + (ddx*ct_ - ddy*st_v)*ratio),
                int(sc_y + (ddx*st_v + ddy*ct_)*ratio))

    rear_top  = rmount(rear_mount_dx,  rear_mount_dy)
    front_top = rmount(front_mount_dx, front_mount_dy)
    wx_f = wx_f_base + shake_x; wx_b = wx_b_base + shake_x
    wy_f = wheel_y_f + shake_ys; wy_b = wheel_y_b + shake_ys

    shad_cx = (wx_f + wx_b) >> 1
    draw_shadow(frame, shad_cx,
                int(pts_y[min(shad_cx, fw-1)]) + 2, car_w, pitch)

    cf = min(1.0, abs(x_f) / .12)
    cb = min(1.0, abs(x_b) / .12)
    draw_spring(frame, wx_f, wy_f, rear_top[0],  rear_top[1],
                (int(25+70*cf), int(100-50*cf), 25))
    draw_spring(frame, wx_b, wy_b, front_top[0], front_top[1],
                (int(25+70*cb), int(100-50*cb), 25))
    draw_shock(frame, wx_f, wy_f, rear_top[0], rear_top[1])
    draw_shock(frame, wx_b, wy_b, front_top[0], front_top[1])

    # Rotación coche — cache si pitch no cambió > 0.05°
    if (_car_rot_cache_pitch is None or
            abs(pitch - _car_rot_cache_pitch) > 0.05):
        M_rot   = cv2.getRotationMatrix2D((_car_cx, _car_cy_orig), pitch, 1.0)
        rot_car = cv2.warpAffine(car_img, M_rot, (_car_w_orig, _car_h_orig),
                                 flags=cv2.INTER_LINEAR,
                                 borderValue=(0, 0, 0, 0))
        _car_rot_cache_pitch = pitch
        _car_rot_cache_img   = rot_car
    else:
        rot_car = _car_rot_cache_img

    overlay_image_alpha(frame, rot_car,
                        car_x + shake_x,
                        car_center_y + car_draw_offset + shake_ys,
                        scale=ratio)
    add_car_lighting(frame, car_x+shake_x, car_center_y+shake_ys,
                     car_w, int(_car_h_orig*ratio), pitch)

    # Llantas
    wheel_angle = (wheel_angle + WHEEL_SPEED) % 360.0
    fidx = int(wheel_angle / 360.0 * WHEEL_FRAMES) % WHEEL_FRAMES
    wimg = wheel_blur_cache[fidx]
    overlay_alpha_fast(frame, wimg, wx_f - WHEEL_SIZE//2, wy_f - WHEEL_SIZE//2)
    overlay_alpha_fast(frame, wimg, wx_b - WHEEL_SIZE//2, wy_b - WHEEL_SIZE//2)

    draw_graph_overlay(frame, road_y, fw, fh)
    draw_sliders(frame)

    # HUD modo
    is_soft  = apertura > 0.5
    modo_txt = "SUSPENSION SUAVE" if is_soft else "SUSPENSION RIGIDA"
    modo_col = (50, 215, 110) if is_soft else (50, 90, 255)
    hud_cx   = fw // 2 + 80
    hx0 = max(0, hud_cx-215); hx1 = min(fw, hud_cx+215)
    sub = frame[8:50, hx0:hx1]
    if sub.size > 0:
        cv2.addWeighted(np.full_like(sub, (2, 5, 16)), 0.70,
                        sub, 0.30, 0, dst=sub)
    cv2.rectangle(frame, (hud_cx-215, 8), (hud_cx-210, 50), modo_col, -1)
    cv2.putText(frame, modo_txt, (hud_cx-202, 34),
                cv2.FONT_HERSHEY_DUPLEX, 0.78, modo_col, 2, cv2.LINE_AA)

    sub2 = frame[8:50, max(0, fw-130):fw-6]
    if sub2.size > 0:
        cv2.addWeighted(np.full_like(sub2, (2, 5, 16)), 0.68,
                        sub2, 0.32, 0, dst=sub2)
    cv2.putText(frame, f"Mano {int(apertura*100)}%", (fw-124, 33),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (185, 205, 255), 1, cv2.LINE_AA)

    wn_d = _math.sqrt(max(kk_eff / masa_eff, 1e-6))
    z_d  = cc_eff / (2 * _math.sqrt(max(kk_eff * masa_eff, 1e-6)))
    for li, txt in enumerate([
        f"m={int(masa)}kg  mu={int(mu)}kg",
        f"k={int(kk_eff):,}  c={int(cc_eff):,}",
        f"wn={wn_d:.2f}r/s  z={z_d:.3f}",
        f"kt={int(kt/1000)}kN/m  v={road_speed:.0f}",
    ]):
        cv2.putText(frame, txt, (fw-195, 58+li*18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32,
                    (160, 200, 255), 1, cv2.LINE_AA)

    sub3 = frame[max(0, fh-28):fh, 0:fw]
    if sub3.size > 0:
        cv2.addWeighted(np.full_like(sub3, (1, 2, 10)), 0.72,
                        sub3, 0.28, 0, dst=sub3)
    cv2.putText(frame,
        "ESC=salir  |  M=reporte  |  A/S=altura  |  "
        "R/E=tras  |  V/C=del  |  MOUSE=sliders",
        (8, fh-9), cv2.FONT_HERSHEY_SIMPLEX, 0.33,
        (105, 150, 200), 1, cv2.LINE_AA)

    cv2.imshow("Simulacion de Suspension", frame)

    key = cv2.waitKey(1) & 0xFF
    if   key == 27: break
    elif key in (ord('m'), ord('M')):
        generate_matplotlib_report(kk_eff, cc_eff, x_f, x_b, pitch)
    elif key == ord('a'): slider_vals[6] = max(-60, slider_vals[6] - 5)
    elif key == ord('s'): slider_vals[6] = min( 60, slider_vals[6] + 5)
    elif key == ord('r'): rear_mount_dy  += 5
    elif key == ord('e'): rear_mount_dy  -= 5
    elif key == ord('v'): front_mount_dy += 5
    elif key == ord('c'): front_mount_dy -= 5

cap.release()
cv2.destroyAllWindows()