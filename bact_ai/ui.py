# ========================
# UI.PY - Layout reorganizado + fondo Petri Dish + overlay inanición
# ========================

import pygame
import math
import random
from config import *
from microbes import get_microbe_data

# ── Constantes de layout ──────────────────────────────────────────────────────
PANEL_ALPHA  = 130
SIDEBAR_W    = 320
GRAPH_H      = 200
GRAPH_MARGIN = 45

# ── Paleta HUD ────────────────────────────────────────────────────────────────
HUD_MUTED  = (80,  140, 170)
HUD_ACCENT = (0,   255, 180)
HUD_DANGER = (255, 60,  60)
HUD_WARN   = (255, 180, 0)

_frame_counter = 0


# ========================
# FONDO: PETRI DISH
# ========================

_petri_bg = None

def _build_petri_bg(w, h):
    global _petri_bg
    surf = pygame.Surface((w, h))
    surf.fill((0, 0, 0))

    for gx in range(0, w, 60):
        pygame.draw.line(surf, (220, 220, 220), (gx, 0), (gx, h), 1)
    for gy in range(0, h, 60):
        pygame.draw.line(surf, (220, 220, 220), (0, gy), (w, gy), 1)

    cx, cy = w // 2, h // 2
    max_r  = min(w, h) * 0.72
    steps  = 28
    for i in range(steps, 0, -1):
        r     = int(max_r * i / steps)
        alpha = int(22 * (1 - i / steps))
        s2    = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
        pygame.draw.circle(s2, (0, 120, 180, alpha), (r, r), r)
        surf.blit(s2, (cx - r, cy - r))

    rng = random.Random(42)
    for _ in range(18):
        bx = rng.randint(0, w)
        by = rng.randint(0, h)
        br = rng.randint(30, 120)
        bs = pygame.Surface((br*2, br*2), pygame.SRCALPHA)
        pygame.draw.ellipse(bs, (0, 50, 30, 12), (0, 0, br*2, int(br*1.3)))
        surf.blit(bs, (bx - br, by - int(br*0.65)))

    border_s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.circle(border_s, (0, 160, 220, 35), (cx, cy), min(cx, cy) - 10, 3)
    pygame.draw.circle(border_s, (0, 80,  110, 20), (cx, cy), min(cx, cy) - 5,  8)
    surf.blit(border_s, (0, 0))

    _petri_bg = surf


def draw_petri_background(surface, nutrients):
    global _petri_bg
    w, h = surface.get_size()
    if _petri_bg is None or _petri_bg.get_size() != (w, h):
        _build_petri_bg(w, h)
    surface.blit(_petri_bg, (0, 0))

    # Tinte verde suave según nutrientes
    ratio = max(0.0, min(1.0, nutrients / 100.0))
    if ratio > 0.05:
        tint = pygame.Surface((w, h), pygame.SRCALPHA)
        tint.fill((0,
                   min(255, int(40 * ratio)),
                   min(255, int(15 * ratio)),
                   min(255, int(46 * ratio))))
        surface.blit(tint, (0, 0))

    # Barra de nutrientes en la parte inferior
    bar_h = 5
    bar_y = h - bar_h
    bar_w = int(ratio * w)
    if nutrients > 60:
        bar_color = (50, 220, 80)
    elif nutrients > 30:
        bar_color = (220, 180, 50)
    else:
        bar_color = (220, 60, 60)
    pygame.draw.rect(surface, (10, 20, 15), (0, bar_y, w, bar_h))
    if bar_w > 0:
        pygame.draw.rect(surface, bar_color, (0, bar_y, bar_w, bar_h))
    dark_overlay = pygame.Surface((w, h), pygame.SRCALPHA)
    dark_overlay.fill((0, 0, 0, 190))  # ← ajusta este valor
    surface.blit(dark_overlay, (0, 0))

# ========================
# SLIDER
# ========================

class Slider:
    def __init__(self, x, y, width, min_val, max_val, label, color):
        self.x        = x
        self.y        = y
        self.width    = width
        self.height   = 14
        self.min_val  = min_val
        self.max_val  = max_val
        self.label    = label
        self.color    = color
        self.value    = (min_val + max_val) / 2
        self.dragging = False

    def update(self, value):
        if not self.dragging:
            self.value = max(self.min_val, min(self.max_val, value))

    def handle_event(self, event):
        handle_x = self.x + int((self.value - self.min_val) /
                                 (self.max_val - self.min_val) * self.width)
        handle_y = self.y + self.height // 2

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if abs(mx - handle_x) < 14 and abs(my - handle_y) < 14:
                self.dragging = True
                return True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            mx         = event.pos[0]
            ratio      = (mx - self.x) / self.width
            self.value = self.min_val + ratio * (self.max_val - self.min_val)
            self.value = max(self.min_val, min(self.max_val, self.value))
            return True
        return False

    def draw(self, surface):
        pygame.draw.rect(surface, (50, 50, 60),
                         (self.x, self.y, self.width, self.height),
                         border_radius=7)
        fill_w = int((self.value - self.min_val) /
                     (self.max_val - self.min_val) * self.width)
        pygame.draw.rect(surface, self.color,
                         (self.x, self.y, fill_w, self.height),
                         border_radius=7)
        hx     = self.x + fill_w
        radius = 12 if self.dragging else 9
        pygame.draw.circle(surface, WHITE, (hx, self.y + self.height // 2), radius)
        pygame.draw.circle(surface, self.color,
                           (hx, self.y + self.height // 2), radius - 2)
        surface.blit(font.render(f"{self.label}: {self.value:.1f}", True, WHITE),
                     (self.x, self.y - 20))


# ========================
# GRÁFICA CON EJES
# ========================

class PopulationGraph:
    def __init__(self, x, y, width, height):
        self.x              = x
        self.y              = y
        self.width          = width
        self.height         = height
        self.max_population = 2000
        self.history        = []

    def update(self, population):
        self.history.append(population)
        if len(self.history) > 400:
            self.history.pop(0)
        if self.history:
            self.max_population = max(self.max_population,
                                      max(self.history) * 1.15)

    def draw(self, surface):
        if len(self.history) < 2:
            return

        bg = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(bg, (5, 5, 12, 200),
                         (0, 0, self.width, self.height), border_radius=10)
        surface.blit(bg, (self.x, self.y))
        pygame.draw.rect(surface, (70, 70, 100),
                         (self.x, self.y, self.width, self.height),
                         2, border_radius=10)

        surface.blit(font.render("Población a lo largo del tiempo", True, WHITE),
                     (self.x + GRAPH_MARGIN + 5, self.y + 6))

        gx = self.x + GRAPH_MARGIN
        gy = self.y + 28
        gw = self.width  - GRAPH_MARGIN - 10
        gh = self.height - 28 - 28

        num_y_lines = 4
        for i in range(num_y_lines + 1):
            yp = gy + gh - int(i / num_y_lines * gh)
            pygame.draw.line(surface, (40, 40, 55), (gx, yp), (gx + gw, yp), 1)
            val_y = int(self.max_population * i / num_y_lines)
            lbl   = font.render(str(val_y), True, (120, 120, 140))
            surface.blit(lbl, (self.x + 2, yp - 8))

        surface.blit(font.render("N", True, LIGHT_GRAY), (self.x + 2, gy))

        num_x_lines = 5
        total_pts   = len(self.history)
        for i in range(num_x_lines + 1):
            xp = gx + int(i / num_x_lines * gw)
            pygame.draw.line(surface, (40, 40, 55), (xp, gy), (xp, gy + gh), 1)
            idx_sample = int(i / num_x_lines * (total_pts - 1))
            lbl = font.render(f"t{idx_sample}", True, (120, 120, 140))
            surface.blit(lbl, (xp - lbl.get_width() // 2, gy + gh + 4))

        x_title = font.render("Tiempo (frames)", True, LIGHT_GRAY)
        surface.blit(x_title,
                     (gx + gw // 2 - x_title.get_width() // 2, gy + gh + 18))

        pygame.draw.line(surface, (100, 100, 130), (gx, gy), (gx, gy + gh), 2)
        pygame.draw.line(surface, (100, 100, 130),
                         (gx, gy + gh), (gx + gw, gy + gh), 2)

        points = []
        for i, pop in enumerate(self.history):
            xp = gx + int(i / (total_pts - 1) * gw)
            yp = gy + gh - int((pop / self.max_population) * gh)
            yp = max(gy, min(gy + gh, yp))
            points.append((xp, yp))

        if len(points) > 1:
            pygame.draw.lines(surface, GREEN, False, points, 2)

        curr = self.history[-1]
        mx   = max(self.history)
        surface.blit(font.render(f"Actual: {curr}", True, GREEN),  (gx + 5, gy + 2))
        surface.blit(font.render(f"Máx: {mx}",      True, CYAN),   (gx + gw - 90, gy + 2))


# ========================
# FORM
# ========================

FORM_FILLING = "filling"
FORM_ERRORS  = "errors"


class CustomMicrobeForm:
    FIELDS = [
        ("clave",            "Nombre clave (ej: MiBact)",                      str),
        ("name",             "Nombre científico",                              str),
        ("shape",            "Forma: bacilo_peritrico/bacilo_polar/coco/virus", str),
        ("optimal_temp",     "Temp óptima °C  [0-100]",                       float),
        ("temp_min",         "Temp mínima °C",                                float),
        ("temp_max",         "Temp máxima °C",                                float),
        ("optimal_ph",       "pH óptimo  [4.0-9.0]",                          float),
        ("ph_min",           "pH mínimo  [>=4.0]",                            float),
        ("ph_max",           "pH máximo  [<=9.0]",                            float),
        ("optimal_humidity", "Humedad óptima %  [0-100]",                     float),
        ("light_sensitivity","Sensibilidad luz  [0.0-1.0]",                   float),
        ("base_rate",        "Tasa base  [0.001-0.1]",                        float),
        ("color_r",          "Color R  [0-255]",                              int),
        ("color_g",          "Color G  [0-255]",                              int),
        ("color_b",          "Color B  [0-255]",                              int),
        ("description",      "Descripción corta",                             str),
    ]

    OPT_AUTO   = 0
    OPT_EDIT   = 1
    OPT_CANCEL = 2

    def __init__(self):
        self.active          = False
        self.form_state      = FORM_FILLING
        self.current_field   = 0
        self.inputs          = {f[0]: "" for f in self.FIELDS}
        self.error_msg       = ""
        self.detected_errors = []
        self.error_option    = self.OPT_AUTO
        self.success_msg     = ""
        self.success_timer   = 0

    def toggle(self):
        self.active = not self.active
        if self.active:
            self._reset()

    def _reset(self):
        self.form_state      = FORM_FILLING
        self.current_field   = 0
        self.inputs          = {f[0]: "" for f in self.FIELDS}
        self.error_msg       = ""
        self.detected_errors = []
        self.error_option    = self.OPT_AUTO

    def _validate_type(self, field_key, field_type, val):
        if field_type in (float, int):
            try:
                field_type(val)
                return True
            except ValueError:
                return False
        return True

    def _detect_range_errors(self):
        errors = []
        i = self.inputs
        try:
            shapes_validos = ["bacilo_peritrico", "bacilo_polar", "coco", "virus"]
            if i["shape"].strip().lower() not in shapes_validos:
                errors.append(f"Forma inválida. Opciones: {', '.join(shapes_validos)}")
            optimal_temp     = float(i["optimal_temp"])
            temp_min         = float(i["temp_min"])
            temp_max         = float(i["temp_max"])
            optimal_ph       = float(i["optimal_ph"])
            ph_min           = float(i["ph_min"])
            ph_max           = float(i["ph_max"])
            optimal_humidity = float(i["optimal_humidity"])
            light_s          = float(i["light_sensitivity"])
            base_rate        = float(i["base_rate"])
            cr = int(i["color_r"]); cg = int(i["color_g"]); cb = int(i["color_b"])
            if not (0 <= optimal_temp <= 100):    errors.append("Temp óptima fuera de 0-100°C")
            if temp_min >= temp_max:               errors.append("Rangos invertidos: Temp mínima >= máxima")
            if not (0 <= optimal_humidity <= 100): errors.append("Humedad óptima fuera de 0-100%")
            if not (4.0 <= optimal_ph <= 9.0):    errors.append("pH óptimo fuera de 4.0-9.0")
            if ph_min >= ph_max:                   errors.append("Rangos invertidos: pH mínimo >= máximo")
            if not (0.0 <= light_s <= 1.0):        errors.append("Sensibilidad luz fuera de 0.0-1.0")
            if not (0.001 <= base_rate <= 0.1):    errors.append("Tasa base fuera de 0.001-0.1")
            if not (0 <= cr <= 255):               errors.append(f"Color R={cr} fuera de 0-255")
            if not (0 <= cg <= 255):               errors.append(f"Color G={cg} fuera de 0-255")
            if not (0 <= cb <= 255):               errors.append(f"Color B={cb} fuera de 0-255")
        except Exception as e:
            errors.append(f"Error de conversión: {e}")
        return errors

    def _auto_fix(self):
        i = self.inputs
        shapes_validos = ["bacilo_peritrico", "bacilo_polar", "coco", "virus"]
        if i["shape"].strip().lower() not in shapes_validos:
            i["shape"] = "bacilo_peritrico"

        def clamp(key, lo, hi):
            try:    i[key] = str(max(lo, min(hi, float(i[key]))))
            except: i[key] = str((lo + hi) / 2)

        def clamp_int(key, lo, hi):
            try:    i[key] = str(max(lo, min(hi, int(i[key]))))
            except: i[key] = str((lo + hi) // 2)

        clamp("optimal_temp", 0, 100);  clamp("temp_min", -10, 80); clamp("temp_max", 0, 100)
        clamp("optimal_ph", 4.0, 9.0); clamp("ph_min", 4.0, 9.0);  clamp("ph_max", 4.0, 9.0)
        clamp("optimal_humidity", 0, 100); clamp("light_sensitivity", 0.0, 1.0)
        clamp("base_rate", 0.001, 0.1)
        clamp_int("color_r", 0, 255); clamp_int("color_g", 0, 255); clamp_int("color_b", 0, 255)
        try:
            if float(i["temp_min"]) >= float(i["temp_max"]):
                i["temp_min"] = str(float(i["temp_max"]) - 5)
        except: pass
        try:
            if float(i["ph_min"]) >= float(i["ph_max"]):
                i["ph_min"] = str(float(i["ph_max"]) - 0.5)
        except: pass

    def _build_and_save(self):
        from microbes import save_custom_microbe
        try:
            i   = self.inputs
            key = i["clave"].strip()
            data = {
                "name":                 i["name"].strip(),
                "type":                 "bacteria",
                "shape":                i["shape"].strip().lower(),
                "optimal_temp":         float(i["optimal_temp"]),
                "temp_range":           (float(i["temp_min"]), float(i["temp_max"])),
                "optimal_humidity":     float(i["optimal_humidity"]),
                "optimal_ph":           float(i["optimal_ph"]),
                "ph_range":             (float(i["ph_min"]), float(i["ph_max"])),
                "light_sensitivity":    float(i["light_sensitivity"]),
                "nutrient_consumption": 0.005,
                "base_rate":            float(i["base_rate"]),
                "color":                (int(i["color_r"]), int(i["color_g"]), int(i["color_b"])),
                "description":          i["description"].strip(),
            }
            save_custom_microbe(key, data)
            self.success_msg   = f"'{key}' guardado correctamente"
            self.success_timer = 0
            self.active        = False
            return (key, data)
        except Exception as e:
            self.error_msg  = f"Error al guardar: {e}"
            self.form_state = FORM_FILLING
            return None

    def handle_event(self, event):
        if not self.active or event.type != pygame.KEYDOWN:
            return None

        if self.form_state == FORM_ERRORS:
            if event.key == pygame.K_UP:
                self.error_option = (self.error_option - 1) % 3
            elif event.key == pygame.K_DOWN:
                self.error_option = (self.error_option + 1) % 3
            elif event.key == pygame.K_RETURN:
                if self.error_option == self.OPT_AUTO:
                    self._auto_fix(); return self._build_and_save()
                elif self.error_option == self.OPT_EDIT:
                    self.form_state = FORM_FILLING; self.current_field = 0
                    self.error_msg  = "Revisa y corrige los campos"
                elif self.error_option == self.OPT_CANCEL:
                    self.active = False; self._reset()
            elif event.key == pygame.K_ESCAPE:
                self.active = False; self._reset()
            return None

        if event.key == pygame.K_ESCAPE:
            self.active = False; self._reset(); return None
        elif event.key in (pygame.K_RETURN, pygame.K_TAB):
            field_key, _, field_type = self.FIELDS[self.current_field]
            val = self.inputs[field_key].strip()
            if not val:
                self.error_msg = "El campo no puede estar vacío"; return None
            if not self._validate_type(field_key, field_type, val):
                self.error_msg = "Se esperaba un número"; return None
            self.error_msg = ""
            if self.current_field < len(self.FIELDS) - 1:
                self.current_field += 1
            else:
                errors = self._detect_range_errors()
                if errors:
                    self.detected_errors = errors
                    self.form_state      = FORM_ERRORS
                    self.error_option    = self.OPT_AUTO
                else:
                    return self._build_and_save()
        elif event.key == pygame.K_BACKSPACE:
            fk = self.FIELDS[self.current_field][0]
            self.inputs[fk] = self.inputs[fk][:-1]
        else:
            if event.unicode:
                fk = self.FIELDS[self.current_field][0]
                if len(self.inputs[fk]) < 40:
                    self.inputs[fk] += event.unicode
        return None

    def draw(self, surface):
        if self.success_msg:
            if self.success_timer == 0:
                self.success_timer = pygame.time.get_ticks()
            elif pygame.time.get_ticks() - self.success_timer > 3000:
                self.success_msg = ""; self.success_timer = 0

        if not self.active:
            if self.success_msg:
                sw, sh = surface.get_size()
                s = big_font.render(self.success_msg, True, GREEN)
                surface.blit(s, (sw // 2 - s.get_width() // 2, sh // 2))
            return

        sw, sh = surface.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 100))
        surface.blit(overlay, (0, 0))

        if self.form_state == FORM_ERRORS:
            self._draw_error_panel(surface, sw, sh)
        else:
            self._draw_form(surface, sw, sh)

    def _draw_form(self, surface, sw, sh):
        pw, ph_panel = 600, 520
        px = (sw - pw) // 2; py = (sh - ph_panel) // 2
        pygame.draw.rect(surface, (15, 15, 30), (px, py, pw, ph_panel), border_radius=16)
        pygame.draw.rect(surface, PURPLE,       (px, py, pw, ph_panel), 2, border_radius=16)
        surface.blit(big_font.render("Nueva Bacteria Custom  [Esc = cancelar]", True, PURPLE),
                     (px + 20, py + 18))
        surface.blit(font.render(f"Campo {self.current_field + 1} / {len(self.FIELDS)}",
                                  True, LIGHT_GRAY), (px + 20, py + 55))
        field_key, field_label, _ = self.FIELDS[self.current_field]
        surface.blit(font.render(field_label + ":", True, CYAN), (px + 20, py + 100))
        input_rect = pygame.Rect(px + 20, py + 130, pw - 40, 42)
        pygame.draw.rect(surface, (30, 30, 55), input_rect, border_radius=8)
        pygame.draw.rect(surface, CYAN, input_rect, 2, border_radius=8)
        surface.blit(big_font.render(self.inputs[field_key] + "|", True, WHITE),
                     (input_rect.x + 10, input_rect.y + 8))
        surface.blit(font.render("Completados:", True, GRAY), (px + 20, py + 200))
        y_prev = py + 228
        for idx, (fk, fl, _) in enumerate(self.FIELDS):
            if idx >= self.current_field: break
            surface.blit(font.render(f"  {fl}: {self.inputs[fk]}", True, GREEN),
                         (px + 20, y_prev))
            y_prev += 22
            if y_prev > py + ph_panel - 70: break
        if self.error_msg:
            surface.blit(font.render(self.error_msg, True, RED), (px + 20, py + ph_panel - 55))
        surface.blit(font.render("Enter o Tab → siguiente campo", True, GRAY),
                     (px + 20, py + ph_panel - 30))

    def _draw_error_panel(self, surface, sw, sh):
        pw, ph_panel = 620, 480
        px = (sw - pw) // 2; py = (sh - ph_panel) // 2
        pygame.draw.rect(surface, (20, 10, 10), (px, py, pw, ph_panel), border_radius=16)
        pygame.draw.rect(surface, RED,          (px, py, pw, ph_panel), 2, border_radius=16)
        surface.blit(big_font.render("⚠ Errores detectados", True, RED), (px + 20, py + 18))
        y_e = py + 60
        for err in self.detected_errors[:6]:
            surface.blit(font.render(f"  • {err}", True, YELLOW), (px + 20, y_e))
            y_e += 26
        pygame.draw.line(surface, GRAY, (px + 20, y_e + 10), (px + pw - 20, y_e + 10), 1)
        options = [(self.OPT_AUTO, "✔  Ajustar automáticamente", GREEN),
                   (self.OPT_EDIT, "✏  Editar manualmente", CYAN),
                   (self.OPT_CANCEL, "✗  Cancelar", RED)]
        y_opt = y_e + 30
        for opt_id, label, col in options:
            selected = self.error_option == opt_id
            opt_rect = pygame.Rect(px + 20, y_opt, pw - 40, 40)
            pygame.draw.rect(surface, (40, 40, 60) if selected else (15, 15, 30),
                             opt_rect, border_radius=8)
            if selected:
                pygame.draw.rect(surface, col, opt_rect, 2, border_radius=8)
            surface.blit(font.render(label, True, col if selected else LIGHT_GRAY),
                         (opt_rect.x + 16, opt_rect.y + 10))
            y_opt += 52
        surface.blit(font.render("↑ ↓ navegar   Enter confirmar", True, GRAY),
                     (px + 20, py + ph_panel - 30))


# ========================
# PANELES HUD
# ========================

def _draw_panel_bg(surface, x, y, w, h, border_color, alpha=PANEL_ALPHA, radius=14):
    bg = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(bg, (5, 5, 12, alpha), (0, 0, w, h), border_radius=radius)
    surface.blit(bg, (x, y))
    pygame.draw.rect(surface, border_color, (x, y, w, h), 2, border_radius=radius)


def draw_info_panel(surface, temp, humidity, ph, light, nutrients,
                    current_microbe, simulated_days, particles):
    microbe_data = get_microbe_data(current_microbe)
    if microbe_data and "color" in microbe_data:
        color = tuple(max(0, min(255, int(v))) for v in microbe_data["color"])
    else:
        color = (70, 255, 70)

    healthy  = sum(1 for p in particles if p.state == "healthy")
    stressed = sum(1 for p in particles if p.state == "stressed")
    total    = len(particles)

    pw   = SIDEBAR_W - 10
    ph_p = 295
    px, py = 8, 8

    _draw_panel_bg(surface, px, py, pw, ph_p, color, alpha=PANEL_ALPHA)

    surface.blit(big_font.render("GestBact AI", True, WHITE), (px + 12, py + 10))
    name_txt = microbe_data["name"] if microbe_data else current_microbe
    surface.blit(font.render(name_txt, True, color), (px + 12, py + 42))
    pygame.draw.line(surface, color, (px + 10, py + 65), (px + pw - 10, py + 65), 1)

    # Color de nutrientes progresivo
    if nutrients <= 0:
        nut_col = HUD_DANGER
    elif nutrients < 20:
        nut_col = RED
    elif nutrients < 50:
        nut_col = HUD_WARN
    else:
        nut_col = GREEN

    rows = [
        ("Temperatura", f"{temp:.1f} °C",      YELLOW),
        ("Humedad",     f"{humidity:.0f} %",    CYAN),
        ("pH",          f"{ph:.2f}",             PURPLE),
        ("Luz UV",      f"{light:.0f} %",       ORANGE),
        ("Nutrientes",  f"{nutrients:.1f} %",   nut_col),
        ("Días",        f"{simulated_days:.2f}", ORANGE),
    ]
    y_row = py + 75
    for label, value, col in rows:
        surface.blit(font.render(label, True, LIGHT_GRAY), (px + 14, y_row))
        surface.blit(font.render(value, True, col),        (px + pw - 90, y_row))
        y_row += 29

    pygame.draw.line(surface, (60, 60, 80),
                     (px + 10, y_row), (px + pw - 10, y_row), 1)
    y_row += 8
    surface.blit(font.render(f"Total: {total}", True, WHITE),  (px + 14, y_row))
    surface.blit(font.render(f"✔ {healthy}",   True, GREEN),   (px + 110, y_row))
    surface.blit(font.render(f"⚠ {stressed}",  True, ORANGE),  (px + 190, y_row))


def draw_sliders_panel(surface, temp_slider, hum_slider,
                        ph_slider, light_slider, nutrient_slider,
                        panel_x, panel_y, panel_w):
    ph_p = 182
    _draw_panel_bg(surface, panel_x, panel_y, panel_w, ph_p,
                   (70, 70, 100), alpha=PANEL_ALPHA)
    sx     = panel_x + 95
    sw     = panel_w - 110
    base_y = panel_y + 32
    for idx, sl in enumerate([temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider]):
        sl.x     = sx
        sl.width = sw
        sl.y     = base_y + idx * 31
        sl.draw(surface)


def draw_controls_help(surface, current_w, current_h):
    lines = [
        "1 dedo Izq → Temp   |  1 dedo Der → Humedad",
        "3 dedos → pH        |  4 dedos → Luz UV",
        "← → Microbio  |  Pulgar ↑ → +1 Día",
        "B Antibiótico  |  N Custom  |  F Nutrientes",
        "M Análisis  |  Espacio Pausa  |  R Reiniciar",
    ]
    pw   = 430
    ph_p = len(lines) * 22 + 18
    px   = current_w - pw - 8
    py   = current_h - ph_p - 18

    _draw_panel_bg(surface, px, py, pw, ph_p, (60, 60, 90), alpha=200)
    for idx, line in enumerate(lines):
        surface.blit(font.render(line, True, LIGHT_GRAY), (px + 10, py + 8 + idx * 22))


# ========================
# OVERLAY INANICIÓN / ESTRÉS MÁXIMO
# ========================

def _draw_starvation_overlay(surface, w, h, particles):
    """Viñeta roja pulsante + panel central cuando nutrientes = 0."""
    alive = len(particles)

    # Viñeta roja pulsante en los bordes
    pulse    = abs(math.sin(_frame_counter * 0.05))
    vignette = pygame.Surface((w, h), pygame.SRCALPHA)
    max_r    = min(w, h) // 2
    for r in range(max_r, 0, -15):
        alpha = int(pulse * 60 * (1 - r / max_r))
        pygame.draw.circle(vignette, (200, 0, 0, alpha), (w // 2, h // 2), r, 18)
    surface.blit(vignette, (0, 0))

    # Panel central de aviso
    pw_ov, ph_ov = 540, 195
    px_ov = (w - pw_ov) // 2
    py_ov = (h - ph_ov) // 2

    bg_ov = pygame.Surface((pw_ov, ph_ov), pygame.SRCALPHA)
    pygame.draw.rect(bg_ov, (30, 0, 0, 230), (0, 0, pw_ov, ph_ov), border_radius=16)
    surface.blit(bg_ov, (px_ov, py_ov))
    pygame.draw.rect(surface, HUD_DANGER,
                     (px_ov, py_ov, pw_ov, ph_ov), 2, border_radius=16)

    # Título parpadea entre rojo y ámbar
    warn_col = HUD_DANGER if int(_frame_counter * 0.1) % 2 == 0 else HUD_WARN
    surface.blit(big_font.render("⚠  ESTRÉS MÁXIMO — SIN NUTRIENTES", True, warn_col),
                 (px_ov + 20, py_ov + 18))
    surface.blit(font.render(
        f"Las bacterias entran en modo de inanición  |  Vivas: {alive}",
        True, HUD_WARN), (px_ov + 20, py_ov + 62))
    surface.blit(font.render(
        "F  →  Reponer nutrientes al 100%",
        True, LIGHT_GRAY), (px_ov + 20, py_ov + 96))
    surface.blit(font.render(
        "R  →  Reiniciar simulación",
        True, LIGHT_GRAY), (px_ov + 20, py_ov + 124))
    surface.blit(font.render(
        "E  →  Activar modo extinción para acelerar la muerte",
        True, (160, 80, 80)), (px_ov + 20, py_ov + 158))


# ========================
# FUNCIONES PRINCIPALES
# ========================

def draw_ui(surface, temp, humidity, ph, light, nutrients, current_microbe,
            simulated_days, particles, population_graph,
            temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider):
    """Solo el fondo petri dish — llamar ANTES de dibujar las bacterias."""
    global _frame_counter
    _frame_counter += 1
    draw_petri_background(surface, nutrients)


def draw_ui_overlay(surface, temp, humidity, ph, light, nutrients, current_microbe,
                    simulated_days, particles, population_graph,
                    temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider):
    """Todos los paneles HUD + overlay inanición — llamar DESPUÉS de las bacterias."""
    current_w, current_h = surface.get_size()

    draw_info_panel(surface, temp, humidity, ph, light, nutrients,
                    current_microbe, simulated_days, particles)

    slider_panel_w = 370
    slider_panel_x = current_w - slider_panel_w - 8
    draw_sliders_panel(surface, temp_slider, hum_slider,
                       ph_slider, light_slider, nutrient_slider,
                       slider_panel_x, 8, slider_panel_w)

    controls_w = 438
    graph_x    = SIDEBAR_W + 5
    graph_w    = current_w - graph_x - controls_w - 16
    graph_y    = current_h - GRAPH_H - 12
    if graph_w > 200:
        population_graph.x      = graph_x
        population_graph.y      = graph_y
        population_graph.width  = graph_w
        population_graph.height = GRAPH_H
        population_graph.draw(surface)

    draw_controls_help(surface, current_w, current_h)

    # ── Overlay de estrés máximo cuando nutrientes = 0 ──
    if nutrients <= 0:
        _draw_starvation_overlay(surface, current_w, current_h, particles)

    # Línea de escaneo CRT sutil
    scan_y = (_frame_counter * 2) % current_h
    scan_s = pygame.Surface((current_w, 2), pygame.SRCALPHA)
    scan_s.fill((0, 200, 255, 8))
    surface.blit(scan_s, (0, scan_y))