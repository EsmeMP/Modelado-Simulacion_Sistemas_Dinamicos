"""
AR Sandbox — Simulación interactiva de realidad aumentada
=========================================================
Requisitos:
    pip install pygame opencv-python mediapipe numpy

Controles:
    MANO IZQUIERDA  → Crear cubos
                      · Mantén pellizco 0.3s para FIJAR posición (ghost se vuelve amarillo)
                      · Suelta para colocar
    MANO DERECHA    → Dos modos (alterna con puño cerrado 1s):
                      [MODO ROTAR]   Pellizco + arrastra → rotar mundo
                      [MODO MOVER]   Toca cubo → selecciona
                                     Pellizco sobre seleccionado → arrastra
                                     Doble pellizco rápido (<0.4s) → elimina cubo
    Tecla C         → Limpiar escena
    Tecla ESC       → Salir
"""

import pygame
import cv2
import mediapipe as mp
import numpy as np
import math
import time
from collections import deque

# ══════════════════════════════════════════════
#  CONFIGURACIÓN GLOBAL
# ══════════════════════════════════════════════
WIDTH, HEIGHT = 1280, 720
FOV           = 700
GRID_UNIT     = 80
CUBE_SIZE     = 80
SNAP_RADIUS   = 55          # más generoso que antes (40 → 55)
PINCH_HOLD    = 0.30        # segundos que hay que sostener el pellizco para fijar

PALETTE = {
    "cyan"     : (0,   220, 255),
    "cyan_dim" : (0,   130, 160),
    "orange"   : (255, 160,  30),
    "green"    : (40,  255, 130),
    "yellow"   : (255, 240,  60),
    "red"      : (255,  60,  60),
    "white"    : (220, 230, 240),
    "grid"     : (0,   200, 255),
    "bg_dark"  : (0,     8,  18),
    "select"   : (255, 200,   0),
}

CX, CY = WIDTH // 2, HEIGHT // 2

# ══════════════════════════════════════════════
#  PROYECCIÓN 3D → 2D
# ══════════════════════════════════════════════
def project(x3, y3, z3):
    z3 = max(z3, 0.01)
    s  = FOV / (FOV + z3)
    return int(CX + x3 * s), int(CY + y3 * s), s

def rot_x(v, a):
    c, s = math.cos(a), math.sin(a)
    return (v[0], v[1]*c - v[2]*s, v[1]*s + v[2]*c)

def rot_y(v, a):
    c, s = math.cos(a), math.sin(a)
    return (v[0]*c + v[2]*s, v[1], -v[0]*s + v[2]*c)

def transform_vertex(v, rx, ry):
    v = rot_y(v, ry)
    v = rot_x(v, rx)
    return v

CUBE_FACES = [
    ((0,1,2,3), ( 0, 0,-1), 0),
    ((4,5,6,7), ( 0, 0, 1), 1),
    ((0,1,5,4), ( 0,-1, 0), 2),
    ((3,2,6,7), ( 0, 1, 0), 3),
    ((0,3,7,4), (-1, 0, 0), 4),
    ((1,2,6,5), ( 1, 0, 0), 5),
]

def cube_local_verts(size):
    h = size / 2
    return [
        (-h,-h,-h),(h,-h,-h),(h,h,-h),(-h,h,-h),
        (-h,-h, h),(h,-h, h),(h,h, h),(-h,h, h),
    ]

# ══════════════════════════════════════════════
#  CUBO 3D
# ══════════════════════════════════════════════
class Cube:
    _id_counter = 0

    def __init__(self, wx, wy, wz, size=CUBE_SIZE):
        self.id   = Cube._id_counter; Cube._id_counter += 1
        self.wx, self.wy, self.wz = wx, wy, wz
        self.size = size
        self.born = time.time()
        self.selected   = False
        self.scale_anim = 0.0
        hue = (self.id * 47) % 360
        self.face_colors = self._gen_colors(hue)

    def _gen_colors(self, hue):
        import colorsys
        faces = []
        for b in [0.95, 0.55, 0.75, 0.45, 0.65, 0.85]:
            r, g, bl = colorsys.hsv_to_rgb(hue/360, 0.85, b)
            faces.append((int(r*255), int(g*255), int(bl*255)))
        return faces

    def update(self, dt):
        self.scale_anim = min(1.0, self.scale_anim + dt * 6)

    def get_world_verts(self, rx, ry):
        local = cube_local_verts(self.size * self.scale_anim)
        out = []
        for lv in local:
            wv = (lv[0]+self.wx, lv[1]+self.wy, lv[2]+self.wz)
            wv = transform_vertex(wv, rx, ry)
            out.append(wv)
        return out

    def draw(self, surface, rx, ry, overlay_surf):
        verts  = self.get_world_verts(rx, ry)
        proj   = [project(*v) for v in verts]
        pts2d  = [(p[0], p[1]) for p in proj]

        light = np.array([0.4, -0.8, -0.5])
        light = light / np.linalg.norm(light)

        face_data = []
        for (fi, normal_local, ci) in CUBE_FACES:
            pts = [pts2d[i] for i in fi]
            nv  = transform_vertex(normal_local, rx, ry)
            nv_arr = np.array(nv)
            if np.linalg.norm(nv_arr) > 0:
                nv_arr = nv_arr / np.linalg.norm(nv_arr)
            if nv_arr[2] > 0.05:
                continue
            diffuse = max(0.0, float(np.dot(-nv_arr, light)))
            bright  = 0.25 + 0.75 * diffuse
            base = self.face_colors[ci]
            if self.selected:
                # Mezclar con amarillo si está seleccionado
                col = tuple(min(255, int(c*bright*0.6 + s*0.4))
                            for c, s in zip(base, PALETTE["select"]))
            else:
                col = tuple(min(255, int(c * bright)) for c in base)
            face_z = sum(verts[i][2] for i in fi) / 4
            face_data.append((face_z, pts, col, ci))

        face_data.sort(key=lambda x: -x[0])
        avg_z = sum(v[2] for v in verts) / 8

        for face_z, pts, col, ci in face_data:
            alpha = 255 if self.selected else 210
            s = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(s, (*col, alpha), pts)
            overlay_surf.blit(s, (0, 0))
            edge_w = 3 if self.selected else 1
            edge = PALETTE["select"] if self.selected else tuple(min(255, c+55) for c in col)
            pygame.draw.polygon(overlay_surf, (*edge, 230), pts, edge_w)

        # Sombra
        shadow_pts = [project(v[0], 200, v[2])[:2] for v in verts]
        try:
            sh = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            pygame.draw.polygon(sh, (0,0,0,35), shadow_pts)
            overlay_surf.blit(sh, (0,0))
        except Exception:
            pass

        return avg_z

    def screen_center(self, rx, ry):
        v = transform_vertex((self.wx, self.wy, self.wz), rx, ry)
        sx, sy, _ = project(*v)
        return sx, sy

    def screen_dist(self, sx, sy, rx, ry):
        cx, cy = self.screen_center(rx, ry)
        return math.hypot(sx - cx, sy - cy)

# ══════════════════════════════════════════════
#  PARTÍCULAS
# ══════════════════════════════════════════════
class Particle:
    def __init__(self, x, y, color):
        self.x, self.y = float(x), float(y)
        a   = np.random.uniform(0, 2*math.pi)
        spd = np.random.uniform(2, 6)
        self.vx   = math.cos(a) * spd
        self.vy   = math.sin(a) * spd - 2
        self.life = 1.0
        self.size = np.random.randint(2, 7)
        self.color = color

    def update(self, dt):
        self.x   += self.vx
        self.y   += self.vy
        self.vy  += 0.15
        self.life -= dt * 2.0

    def draw(self, surf):
        if self.life <= 0: return
        a = int(self.life * 255)
        s = pygame.Surface((self.size*2+2, self.size*2+2), pygame.SRCALPHA)
        pygame.draw.circle(s, (*self.color, a), (self.size+1, self.size+1), self.size)
        surf.blit(s, (int(self.x-self.size), int(self.y-self.size)))

# ══════════════════════════════════════════════
#  SNAP — ahora con feedback de distancia
# ══════════════════════════════════════════════
def snap_position(wx, wy, wz, cubes):
    sx = round(wx / GRID_UNIT) * GRID_UNIT
    sy = round(wy / GRID_UNIT) * GRID_UNIT
    sz = round(wz / GRID_UNIT) * GRID_UNIT

    best_d   = SNAP_RADIUS
    best_pos = (sx, sy, sz)
    snapped  = False

    offsets = [
        (CUBE_SIZE,0,0),(-CUBE_SIZE,0,0),
        (0,CUBE_SIZE,0),(0,-CUBE_SIZE,0),
        (0,0,CUBE_SIZE),(0,0,-CUBE_SIZE),
    ]
    for c in cubes:
        for ox, oy, oz in offsets:
            tx, ty, tz = c.wx+ox, c.wy+oy, c.wz+oz
            d = math.sqrt((wx-tx)**2+(wy-ty)**2+(wz-tz)**2)
            if d < best_d:
                best_d, best_pos, snapped = d, (tx,ty,tz), True

    return best_pos, snapped

# ══════════════════════════════════════════════
#  UTILIDADES MEDIAPIPE
# ══════════════════════════════════════════════
def pinch_dist(lm):
    t, i = lm[4], lm[8]
    return math.hypot(t.x-i.x, t.y-i.y)

def fist_closed(lm):
    tips  = [8,12,16,20]
    bases = [6,10,14,18]
    return sum(1 for t,b in zip(tips,bases) if lm[t].y > lm[b].y) >= 3

def lm_to_screen(lm, idx):
    return int(lm[idx].x*WIDTH), int(lm[idx].y*HEIGHT)

def screen_to_world(sx, sy, z_world, rx, ry):
    z3 = z_world
    s  = FOV / (FOV + z3)
    wx = (sx-CX) / s
    wy = (sy-CY) / s
    v  = (wx, wy, z3)
    v  = rot_y(v, -ry)
    v  = rot_x(v, -rx)
    return v[0], v[1], v[2]

# ══════════════════════════════════════════════
#  HUD MEJORADO
# ══════════════════════════════════════════════
def draw_hud(surf, font_b, font_s, cubes, left_state, right_state, fps,
             right_mode, selected_cube, pinch_charge):
    pad = 14

    # Panel izquierdo
    panel = pygame.Surface((310, 160), pygame.SRCALPHA)
    panel.fill((0,8,20,170))
    pygame.draw.rect(panel, (0,200,255,60), (0,0,310,160), 1)
    surf.blit(panel, (pad, pad))

    lines = [
        ("✦ MANO IZQ", PALETTE["cyan"],   left_state),
        ("✦ MANO DER", PALETTE["orange"], right_state),
    ]
    y0 = pad + 12
    for header, hcol, detail in lines:
        surf.blit(font_b.render(header, True, hcol),   (pad+10, y0))
        surf.blit(font_s.render(detail, True, PALETTE["white"]), (pad+10, y0+22))
        y0 += 56

    # Indicador de modo mano derecha
    mode_col  = PALETTE["green"] if right_mode == "MOVER" else PALETTE["orange"]
    mode_surf = font_b.render(f"MODO: {right_mode}", True, mode_col)
    surf.blit(mode_surf, (pad+10, y0))

    # Barra de carga del pellizco izquierdo
    if pinch_charge > 0:
        bar_w = int(200 * min(pinch_charge / PINCH_HOLD, 1.0))
        pygame.draw.rect(surf, (40,40,40), (pad+10, HEIGHT-70, 200, 14), border_radius=4)
        col = PALETTE["yellow"] if pinch_charge < PINCH_HOLD else PALETTE["green"]
        pygame.draw.rect(surf, col, (pad+10, HEIGHT-70, bar_w, 14), border_radius=4)
        lbl = font_s.render("Mantén para fijar posición" if pinch_charge < PINCH_HOLD
                            else "✓ LISTO — suelta para colocar", True, col)
        surf.blit(lbl, (pad+10, HEIGHT-90))

    # Contador de cubos + seleccionado
    c_txt = font_b.render(f"CUBOS: {len(cubes)}", True, PALETTE["cyan"])
    surf.blit(c_txt, (WIDTH-170, pad))
    if selected_cube is not None:
        sel_txt = font_s.render("● SELECCIONADO", True, PALETTE["select"])
        surf.blit(sel_txt, (WIDTH-170, pad+28))

    # FPS
    fps_txt = font_s.render(f"{fps:.0f} fps", True, (100,140,160))
    surf.blit(fps_txt, (WIDTH-80, pad+52))

    # Ayuda
    for i, h in enumerate(["[C] limpiar", "[ESC] salir"]):
        surf.blit(font_s.render(h, True, (80,110,130)), (pad+10, HEIGHT-36+i*18))

def draw_cursor(surf, x, y, pinching, label, color, charge=0):
    r = 12 if pinching else 18
    pygame.draw.circle(surf, color, (x,y), r, 2)
    t = time.time()
    pulse_r = r + 6 + int(4*math.sin(t*6))
    s = pygame.Surface((pulse_r*2+4, pulse_r*2+4), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color, 80), (pulse_r+2, pulse_r+2), pulse_r, 1)
    surf.blit(s, (x-pulse_r-2, y-pulse_r-2))

    # Arco de carga de pellizco
    if charge > 0 and charge < PINCH_HOLD:
        ratio = charge / PINCH_HOLD
        arc_r = r + 14
        arc_surf = pygame.Surface((arc_r*2+4, arc_r*2+4), pygame.SRCALPHA)
        rect = pygame.Rect(2, 2, arc_r*2, arc_r*2)
        end_angle = -math.pi/2 + ratio * 2 * math.pi
        pygame.draw.arc(arc_surf, (*PALETTE["yellow"], 200), rect,
                        -math.pi/2, end_angle, 3)
        surf.blit(arc_surf, (x-arc_r-2, y-arc_r-2))

    font_tiny = pygame.font.SysFont("consolas", 13)
    surf.blit(font_tiny.render(label, True, color), (x+r+4, y-8))

def draw_ar_grid(surf, rx, ry):
    lines_surf = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    step = GRID_UNIT
    half = 5
    for i in range(-half, half+1):
        for j in range(-half, half+1):
            p1 = transform_vertex((i*step, 180, j*step),       rx, ry)
            p2 = transform_vertex((i*step, 180, (j+1)*step),   rx, ry)
            p3 = transform_vertex(((i+1)*step, 180, j*step),   rx, ry)
            pp1 = project(*p1); pp2 = project(*p2); pp3 = project(*p3)
            d = math.sqrt(i**2+j**2)/half
            alpha = max(10, int(50*(1-d)))
            pygame.draw.line(lines_surf, (*PALETTE["grid"], alpha), pp1[:2], pp2[:2], 1)
            pygame.draw.line(lines_surf, (*PALETTE["grid"], alpha), pp1[:2], pp3[:2], 1)
    surf.blit(lines_surf, (0,0))

def draw_scanlines(surf):
    sc = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for y in range(0, HEIGHT, 3):
        pygame.draw.line(sc, (0,0,0,18), (0,y), (WIDTH,y))
    surf.blit(sc, (0,0))

def draw_vignette(surf):
    vig = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    for r in range(120, 0, -6):
        a = int((120-r)*1.5)
        pygame.draw.rect(vig, (0,0,0,a), (CX-r*6, CY-r*3, r*12, r*6), 2)
    surf.blit(vig, (0,0))

def draw_preview_cube(surf, sx, sy, world_rx, world_ry, z_depth, cubes,
                      locked, snap_active):
    """
    Ghost del cubo a colocar.
    locked=False → translúcido cyan
    locked=True  → amarillo/verde más sólido (posición fijada, listo para soltar)
    snap_active  → borde extra para indicar snap a cara de cubo existente
    """
    wx, wy, wz = screen_to_world(sx, sy, z_depth, world_rx, world_ry)
    (wx, wy, wz), snapped = snap_position(wx, wy, wz, cubes)

    local  = cube_local_verts(CUBE_SIZE)
    proj_pts = []
    for lv in local:
        wv = (lv[0]+wx, lv[1]+wy, lv[2]+wz)
        wv = transform_vertex(wv, world_rx, world_ry)
        proj_pts.append(project(*wv)[:2])

    ghost = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    t     = time.time()
    pulse = int(40 + 30*math.sin(t*4))

    if locked:
        fill_col  = (180, 255, 100, 80)
        edge_col  = (180, 255, 100, 200 + int(55*math.sin(t*8)))
        edge_w    = 3
    else:
        fill_col  = (0, 220, 255, pulse)
        edge_col  = (0, 220, 255, 160)
        edge_w    = 2

    for (fi, _, _ci) in CUBE_FACES:
        pts = [proj_pts[i] for i in fi]
        pygame.draw.polygon(ghost, fill_col, pts)
        pygame.draw.polygon(ghost, edge_col, pts, edge_w)

    # Indicador de snap a cubo existente
    if snapped:
        for (fi, _, _ci) in CUBE_FACES:
            pts = [proj_pts[i] for i in fi]
            pygame.draw.polygon(ghost, (255, 200, 0, 50), pts)

    surf.blit(ghost, (0,0))

    # Etiqueta de estado
    font_tiny = pygame.font.SysFont("consolas", 13)
    state_lbl = "✓ SNAP" if snapped else "LIBRE"
    lbl_col   = PALETTE["yellow"] if snapped else PALETTE["cyan"]
    if locked:
        state_lbl = "⬛ FIJADO"
        lbl_col   = PALETTE["green"]
    surf.blit(font_tiny.render(state_lbl, True, lbl_col), (sx+22, sy-32))

    return wx, wy, wz   # devuelve posición calculada

# ══════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("AR Sandbox — Hand Tracking 3D")
    clock  = pygame.time.Clock()

    font_b = pygame.font.SysFont("consolas", 20, bold=True)
    font_s = pygame.font.SysFont("consolas", 14)

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    mp_hands_sol = mp.solutions.hands
    hands_det    = mp_hands_sol.Hands(
        max_num_hands=2,
        min_detection_confidence=0.72,
        min_tracking_confidence=0.72,
    )

    # ── Estado del mundo ──────────────────────
    cubes     : list[Cube]     = []
    particles : list[Particle] = []
    world_rx   = 0.18
    world_ry   = 0.0
    target_rx  = 0.18
    target_ry  = 0.0

    # ── Estado mano izquierda ─────────────────
    pinch_was_L      = False
    pinch_start_L    = None        # timestamp cuando empezó el pellizco
    pinch_locked     = False       # True cuando se sostuvo >= PINCH_HOLD
    locked_world_pos = None        # posición 3D fijada
    left_pos_smooth  = deque(maxlen=6)
    z_placement      = 0
    left_action      = "Pellizco → colocar cubo"

    # ── Estado mano derecha ───────────────────
    right_mode       = "ROTAR"     # "ROTAR" | "MOVER"
    fist_start_R     = None        # para detectar puño sostenido → cambio de modo
    pinch_was_R      = False
    prev_pos_R       = None
    selected_cube    = None        # cubo actualmente seleccionado
    drag_offset      = None        # offset 3D al arrastrar cubo
    last_pinch_time  = 0           # para detectar doble pellizco → eliminar
    right_action     = "Pellizco + arrastra → rotar"

    running = True

    while running:
        dt = clock.tick(60) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE: running = False
                if event.key == pygame.K_c:
                    cubes.clear()
                    selected_cube = None

        # ── Cámara ────────────────────────────
        ret, frame = cap.read()
        if not ret: break
        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (WIDTH, HEIGHT))
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        surf  = pygame.surfarray.make_surface(np.transpose(rgb, (1,0,2)))

        dark = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dark.fill((0,5,15,55))
        surf.blit(dark, (0,0))
        screen.blit(surf, (0,0))

        # ── MediaPipe ─────────────────────────
        results  = hands_det.process(rgb)
        world_rx += (target_rx - world_rx) * 0.12
        world_ry += (target_ry - world_ry) * 0.12

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        draw_ar_grid(overlay, world_rx, world_ry)

        for c in cubes:
            c.update(dt)
            c.draw(screen, world_rx, world_ry, overlay)

        screen.blit(overlay, (0,0))

        # ── Variables de frame ────────────────
        preview_screen_pos = None
        pinch_charge       = pinch_start_L and (time.time()-pinch_start_L) or 0

        if results.multi_hand_landmarks and results.multi_handedness:
            for hlm, hinfo in zip(results.multi_hand_landmarks,
                                  results.multi_handedness):
                lm    = hlm.landmark
                label = hinfo.classification[0].label
                short = "L" if label == "Left" else "R"

                ix, iy = lm_to_screen(lm, 8)
                pinching = pinch_dist(lm) < 0.05
                fist     = fist_closed(lm)

                # ══ MANO IZQUIERDA: crear cubos ══════════
                if short == "L":
                    left_pos_smooth.append((ix, iy))
                    six = int(sum(p[0] for p in left_pos_smooth)/len(left_pos_smooth))
                    siy = int(sum(p[1] for p in left_pos_smooth)/len(left_pos_smooth))
                    preview_screen_pos = (six, siy)

                    if pinching:
                        if pinch_start_L is None:
                            pinch_start_L = time.time()
                        held = time.time() - pinch_start_L

                        if held >= PINCH_HOLD and not pinch_locked:
                            # Fijar posición objetivo
                            pinch_locked = True
                            wx, wy, wz = screen_to_world(six, siy, z_placement,
                                                          world_rx, world_ry)
                            (wx,wy,wz), _ = snap_position(wx, wy, wz, cubes)
                            locked_world_pos = (wx, wy, wz)

                        if pinch_locked:
                            left_action = "⬛ FIJADO — suelta para colocar"
                        else:
                            left_action = f"Mantén pellizco… {held:.1f}s"
                    else:
                        # Al soltar el pellizco
                        if pinch_was_L:
                            if pinch_locked and locked_world_pos:
                                wx, wy, wz = locked_world_pos
                                too_close = any(
                                    abs(c.wx-wx)<5 and abs(c.wy-wy)<5 and abs(c.wz-wz)<5
                                    for c in cubes
                                )
                                if not too_close:
                                    new_cube = Cube(wx, wy, wz)
                                    cubes.append(new_cube)
                                    for _ in range(18):
                                        particles.append(
                                            Particle(six, siy, new_cube.face_colors[0])
                                        )
                        # Reset
                        pinch_start_L = None
                        pinch_locked  = False
                        locked_world_pos = None
                        left_action   = "Pellizco → colocar cubo"

                    pinch_was_L = pinching
                    charge_val  = (time.time()-pinch_start_L) if pinch_start_L else 0
                    draw_cursor(screen, six, siy, pinching, "IZQ",
                                PALETTE["cyan"], charge_val if not pinch_locked else PINCH_HOLD)

                # ══ MANO DERECHA: rotar o mover ══════════
                elif short == "R":
                    # Detectar puño sostenido 1s → cambiar modo
                    if fist and not pinching:
                        if fist_start_R is None:
                            fist_start_R = time.time()
                        elif time.time() - fist_start_R > 1.0:
                            right_mode  = "MOVER" if right_mode == "ROTAR" else "ROTAR"
                            fist_start_R = None
                            # Feedback de partículas en posición de palma
                            px, py = lm_to_screen(lm, 0)
                            col = PALETTE["green"] if right_mode=="MOVER" else PALETTE["orange"]
                            for _ in range(20):
                                particles.append(Particle(px, py, col))
                    else:
                        fist_start_R = None

                    # ── Modo ROTAR ─────────────────
                    if right_mode == "ROTAR":
                        if pinching:
                            right_action = "◉ ROTANDO mundo"
                            if prev_pos_R:
                                dx = ix - prev_pos_R[0]
                                dy = iy - prev_pos_R[1]
                                target_ry += dx * 0.012
                                target_rx += dy * 0.012
                                target_rx  = max(-0.8, min(0.8, target_rx))
                        elif fist:
                            right_action = "◉ PUÑO — ajustar Z"
                            if prev_pos_R:
                                dy = iy - prev_pos_R[1]
                                z_placement = max(-300, min(300, z_placement+dy*2))
                        else:
                            right_action = "Pellizco → rotar | Puño 1s → Modo MOVER"

                    # ── Modo MOVER ─────────────────
                    elif right_mode == "MOVER":
                        if not pinching and not fist:
                            # Hover: resaltar cubo más cercano al dedo índice
                            right_action = "Toca cubo → seleccionar"
                            best_d, best_c = 999, None
                            for c in cubes:
                                d = c.screen_dist(ix, iy, world_rx, world_ry)
                                if d < best_d:
                                    best_d, best_c = d, c
                            # Seleccionar si el dedo está suficientemente cerca
                            for c in cubes:
                                c.selected = False
                            if best_c and best_d < 55:
                                best_c.selected = True
                                selected_cube   = best_c
                            else:
                                if not pinching:
                                    selected_cube = None

                        elif pinching:
                            # Arrastrar cubo seleccionado
                            if selected_cube is not None:
                                right_action = "◉ MOVIENDO cubo"
                                if drag_offset is None and prev_pos_R:
                                    # Calcular offset inicial
                                    wx, wy, wz = screen_to_world(
                                        ix, iy, selected_cube.wz,
                                        world_rx, world_ry
                                    )
                                    drag_offset = (
                                        selected_cube.wx - wx,
                                        selected_cube.wy - wy,
                                        selected_cube.wz - wz,
                                    )
                                if drag_offset:
                                    wx, wy, wz = screen_to_world(
                                        ix, iy, selected_cube.wz,
                                        world_rx, world_ry
                                    )
                                    nx = wx + drag_offset[0]
                                    ny = wy + drag_offset[1]
                                    nz = wz + drag_offset[2]
                                    (nx,ny,nz), _ = snap_position(nx,ny,nz,
                                        [c for c in cubes if c is not selected_cube])
                                    selected_cube.wx = nx
                                    selected_cube.wy = ny
                                    selected_cube.wz = nz

                                # Detectar doble pellizco → eliminar
                                now = time.time()
                                if not pinch_was_R:   # flanco de subida
                                    if now - last_pinch_time < 0.4:
                                        # Doble pellizco → eliminar
                                        col = selected_cube.face_colors[0]
                                        scx, scy = selected_cube.screen_center(
                                            world_rx, world_ry)
                                        for _ in range(25):
                                            particles.append(Particle(scx,scy,col))
                                        cubes.remove(selected_cube)
                                        selected_cube = None
                                        drag_offset   = None
                                        right_action  = "Cubo eliminado"
                                    last_pinch_time = now
                            else:
                                right_action = "Sin selección — acerca el dedo a un cubo"
                        else:
                            right_action = "Puño 1s → Modo ROTAR"

                        if not pinching:
                            drag_offset = None

                    pinch_was_R  = pinching
                    prev_pos_R   = (ix, iy)
                    draw_cursor(screen, ix, iy, pinching, "DER", PALETTE["orange"])

        # ── Preview del cubo (solo modo ROTAR izq) ──
        if preview_screen_pos:
            locked_pos = draw_preview_cube(
                screen,
                *preview_screen_pos,
                world_rx, world_ry, z_placement,
                cubes,
                locked=pinch_locked,
                snap_active=True,
            )
            z_txt = font_s.render(f"Z: {z_placement:+.0f}", True, PALETTE["cyan"])
            screen.blit(z_txt, (preview_screen_pos[0]+22,
                                preview_screen_pos[1]-18))

        # ── Partículas ────────────────────────
        particles[:] = [p for p in particles if p.life > 0]
        for p in particles:
            p.update(dt)
            p.draw(screen)

        # ── Post-proceso ──────────────────────
        draw_scanlines(screen)
        draw_vignette(screen)

        # ── HUD ───────────────────────────────
        pinch_charge_hud = (time.time()-pinch_start_L) if pinch_start_L else 0
        draw_hud(screen, font_b, font_s, cubes,
                 left_action, right_action,
                 clock.get_fps(), right_mode,
                 selected_cube, pinch_charge_hud if not pinch_locked else PINCH_HOLD)

        pygame.display.flip()

    cap.release()
    pygame.quit()

if __name__ == "__main__":
    main()