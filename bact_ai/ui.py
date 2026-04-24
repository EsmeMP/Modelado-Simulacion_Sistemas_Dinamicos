# ========================
# UI.PY - Rediseño completo de layout
# ========================

import pygame
from config import *
from microbes import get_microbe_data

# ── Constantes de layout ──────────────────────────────────────────────────────
PANEL_ALPHA   = 150       # transparencia de paneles
SIDEBAR_W     = 320       # ancho de la barra lateral izquierda
TOPBAR_H      = 260       # altura de la barra superior derecha (sliders + gráfica)


class Slider:
    def __init__(self, x, y, width, min_val, max_val, label, color):
        self.x       = x
        self.y       = y
        self.width   = width
        self.height  = 14
        self.min_val = min_val
        self.max_val = max_val
        self.label   = label
        self.color   = color
        self.value   = (min_val + max_val) / 2
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
            mx    = event.pos[0]
            ratio = (mx - self.x) / self.width
            self.value = self.min_val + ratio * (self.max_val - self.min_val)
            self.value = max(self.min_val, min(self.max_val, self.value))
            return True
        return False

    def draw(self, surface):
        # Track
        pygame.draw.rect(surface, (50, 50, 60),
                         (self.x, self.y, self.width, self.height),
                         border_radius=7)
        # Fill
        fill_w = int((self.value - self.min_val) /
                     (self.max_val - self.min_val) * self.width)
        pygame.draw.rect(surface, self.color,
                         (self.x, self.y, fill_w, self.height),
                         border_radius=7)
        # Handle
        hx     = self.x + fill_w
        radius = 12 if self.dragging else 9
        pygame.draw.circle(surface, WHITE, (hx, self.y + self.height // 2), radius)
        pygame.draw.circle(surface, self.color,
                           (hx, self.y + self.height // 2), radius - 2)
        # Label — compacto
        label_surf = font.render(
            f"{self.label}: {self.value:.1f}", True, WHITE)
        surface.blit(label_surf, (self.x, self.y - 20))


# ========================
# FORM ESTADOS
# ========================
FORM_FILLING = "filling"
FORM_ERRORS  = "errors"


class CustomMicrobeForm:
    FIELDS = [
        ("clave",            "Nombre clave (ej: MiBact)",                   str),
        ("name",             "Nombre científico",                           str),
        ("shape",            "Forma: bacilo_peritrico/bacilo_polar/coco/virus", str),
        ("optimal_temp",     "Temp óptima °C  [0-100]",                    float),
        ("temp_min",         "Temp mínima °C",                             float),
        ("temp_max",         "Temp máxima °C",                             float),
        ("optimal_ph",       "pH óptimo  [4.0-9.0]",                       float),
        ("ph_min",           "pH mínimo  [>=4.0]",                         float),
        ("ph_max",           "pH máximo  [<=9.0]",                         float),
        ("optimal_humidity", "Humedad óptima %  [0-100]",                  float),
        ("light_sensitivity","Sensibilidad luz  [0.0-1.0]",                float),
        ("base_rate",        "Tasa base  [0.001-0.1]",                     float),
        ("color_r",          "Color R  [0-255]",                           int),
        ("color_g",          "Color G  [0-255]",                           int),
        ("color_b",          "Color B  [0-255]",                           int),
        ("description",      "Descripción corta",                          str),
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
            cr = int(i["color_r"])
            cg = int(i["color_g"])
            cb = int(i["color_b"])

            if not (0 <= optimal_temp <= 100):
                errors.append("Temp óptima fuera de 0-100°C")
            if temp_min >= temp_max:
                errors.append("Rangos invertidos: Temp mínima >= máxima")
            if not (0 <= optimal_humidity <= 100):
                errors.append("Humedad óptima fuera de 0-100%")
            if not (4.0 <= optimal_ph <= 9.0):
                errors.append("pH óptimo fuera de 4.0-9.0")
            if ph_min >= ph_max:
                errors.append("Rangos invertidos: pH mínimo >= máximo")
            if not (0.0 <= light_s <= 1.0):
                errors.append("Sensibilidad luz fuera de 0.0-1.0")
            if not (0.001 <= base_rate <= 0.1):
                errors.append("Tasa base fuera de 0.001-0.1")
            if not (0 <= cr <= 255):
                errors.append(f"Color R={cr} fuera de 0-255")
            if not (0 <= cg <= 255):
                errors.append(f"Color G={cg} fuera de 0-255")
            if not (0 <= cb <= 255):
                errors.append(f"Color B={cb} fuera de 0-255")
        except Exception as e:
            errors.append(f"Error de conversión: {e}")
        return errors

    def _auto_fix(self):
        i = self.inputs

        shapes_validos = ["bacilo_peritrico", "bacilo_polar", "coco", "virus"]
        if i["shape"].strip().lower() not in shapes_validos:
            i["shape"] = "bacilo_peritrico"

        def clamp(key, lo, hi):
            try:
                i[key] = str(max(lo, min(hi, float(i[key]))))
            except Exception:
                i[key] = str((lo + hi) / 2)

        def clamp_int(key, lo, hi):
            try:
                i[key] = str(max(lo, min(hi, int(i[key]))))
            except Exception:
                i[key] = str((lo + hi) // 2)

        clamp("optimal_temp",      0,     100)
        clamp("temp_min",         -10,     80)
        clamp("temp_max",          0,     100)
        clamp("optimal_ph",        4.0,    9.0)
        clamp("ph_min",            4.0,    9.0)
        clamp("ph_max",            4.0,    9.0)
        clamp("optimal_humidity",  0,     100)
        clamp("light_sensitivity", 0.0,    1.0)
        clamp("base_rate",         0.001,  0.1)
        clamp_int("color_r",       0,     255)
        clamp_int("color_g",       0,     255)
        clamp_int("color_b",       0,     255)

        try:
            if float(i["temp_min"]) >= float(i["temp_max"]):
                i["temp_min"] = str(float(i["temp_max"]) - 5)
        except Exception:
            pass
        try:
            if float(i["ph_min"]) >= float(i["ph_max"]):
                i["ph_min"] = str(float(i["ph_max"]) - 0.5)
        except Exception:
            pass

    def _build_and_save(self):
        from microbes import save_custom_microbe
        try:
            i   = self.inputs
            key = i["clave"].strip()
            data = {
                "name":                i["name"].strip(),
                "type":                "bacteria",
                "shape":               i["shape"].strip().lower(),
                "optimal_temp":        float(i["optimal_temp"]),
                "temp_range":          (float(i["temp_min"]), float(i["temp_max"])),
                "optimal_humidity":    float(i["optimal_humidity"]),
                "optimal_ph":          float(i["optimal_ph"]),
                "ph_range":            (float(i["ph_min"]), float(i["ph_max"])),
                "light_sensitivity":   float(i["light_sensitivity"]),
                "nutrient_consumption": 0.005,
                "base_rate":           float(i["base_rate"]),
                "color":               (int(i["color_r"]), int(i["color_g"]), int(i["color_b"])),
                "description":         i["description"].strip(),
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
        if not self.active:
            return None
        if event.type != pygame.KEYDOWN:
            return None

        if self.form_state == FORM_ERRORS:
            if event.key == pygame.K_UP:
                self.error_option = (self.error_option - 1) % 3
            elif event.key == pygame.K_DOWN:
                self.error_option = (self.error_option + 1) % 3
            elif event.key == pygame.K_RETURN:
                if self.error_option == self.OPT_AUTO:
                    self._auto_fix()
                    return self._build_and_save()
                elif self.error_option == self.OPT_EDIT:
                    self.form_state  = FORM_FILLING
                    self.current_field = 0
                    self.error_msg   = "Revisa y corrige los campos"
                elif self.error_option == self.OPT_CANCEL:
                    self.active = False
                    self._reset()
            elif event.key == pygame.K_ESCAPE:
                self.active = False
                self._reset()
            return None

        if event.key == pygame.K_ESCAPE:
            self.active = False
            self._reset()
            return None

        elif event.key in (pygame.K_RETURN, pygame.K_TAB):
            field_key, _, field_type = self.FIELDS[self.current_field]
            val = self.inputs[field_key].strip()
            if not val:
                self.error_msg = "El campo no puede estar vacío"
                return None
            if not self._validate_type(field_key, field_type, val):
                self.error_msg = "Se esperaba un número"
                return None
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
        # Timer éxito
        if self.success_msg:
            if self.success_timer == 0:
                self.success_timer = pygame.time.get_ticks()
            elif pygame.time.get_ticks() - self.success_timer > 3000:
                self.success_msg   = ""
                self.success_timer = 0

        if not self.active:
            if self.success_msg:
                sw, sh = surface.get_size()
                s = big_font.render(self.success_msg, True, GREEN)
                surface.blit(s, (sw // 2 - s.get_width() // 2, sh // 2))
            return

        sw, sh = surface.get_size()
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))

        if self.form_state == FORM_ERRORS:
            self._draw_error_panel(surface, sw, sh)
        else:
            self._draw_form(surface, sw, sh)

    def _draw_form(self, surface, sw, sh):
        pw, ph_panel = 600, 520
        px = (sw - pw) // 2
        py = (sh - ph_panel) // 2

        pygame.draw.rect(surface, (15, 15, 30),
                         (px, py, pw, ph_panel), border_radius=16)
        pygame.draw.rect(surface, PURPLE,
                         (px, py, pw, ph_panel), 2, border_radius=16)

        surface.blit(big_font.render(
            "Nueva Bacteria Custom  [Esc = cancelar]", True, PURPLE),
            (px + 20, py + 18))
        surface.blit(font.render(
            f"Campo {self.current_field + 1} / {len(self.FIELDS)}", True, LIGHT_GRAY),
            (px + 20, py + 55))

        field_key, field_label, _ = self.FIELDS[self.current_field]
        surface.blit(font.render(field_label + ":", True, CYAN),
                     (px + 20, py + 100))

        input_val  = self.inputs[field_key]
        input_rect = pygame.Rect(px + 20, py + 130, pw - 40, 42)
        pygame.draw.rect(surface, (30, 30, 55), input_rect, border_radius=8)
        pygame.draw.rect(surface, CYAN, input_rect, 2, border_radius=8)
        surface.blit(big_font.render(input_val + "|", True, WHITE),
                     (input_rect.x + 10, input_rect.y + 8))

        surface.blit(font.render("Completados:", True, GRAY),
                     (px + 20, py + 200))
        y_prev = py + 228
        for idx, (fk, fl, _) in enumerate(self.FIELDS):
            if idx >= self.current_field:
                break
            surface.blit(font.render(f"  {fl}: {self.inputs[fk]}", True, GREEN),
                         (px + 20, y_prev))
            y_prev += 22
            if y_prev > py + ph_panel - 70:
                break

        if self.error_msg:
            surface.blit(font.render(self.error_msg, True, RED),
                         (px + 20, py + ph_panel - 55))
        surface.blit(font.render("Enter o Tab → siguiente campo", True, GRAY),
                     (px + 20, py + ph_panel - 30))

    def _draw_error_panel(self, surface, sw, sh):
        pw, ph_panel = 620, 480
        px = (sw - pw) // 2
        py = (sh - ph_panel) // 2

        pygame.draw.rect(surface, (20, 10, 10),
                         (px, py, pw, ph_panel), border_radius=16)
        pygame.draw.rect(surface, RED,
                         (px, py, pw, ph_panel), 2, border_radius=16)

        surface.blit(big_font.render(
            "⚠ Errores detectados", True, RED), (px + 20, py + 18))

        y_e = py + 60
        for err in self.detected_errors[:6]:
            surface.blit(font.render(f"  • {err}", True, YELLOW), (px + 20, y_e))
            y_e += 26

        pygame.draw.line(surface, GRAY,
                         (px + 20, y_e + 10), (px + pw - 20, y_e + 10), 1)

        options = [
            (self.OPT_AUTO,   "✔  Ajustar automáticamente", GREEN),
            (self.OPT_EDIT,   "✏  Editar manualmente",       CYAN),
            (self.OPT_CANCEL, "✗  Cancelar",                  RED),
        ]
        y_opt = y_e + 30
        for opt_id, label, col in options:
            selected = self.error_option == opt_id
            opt_rect = pygame.Rect(px + 20, y_opt, pw - 40, 40)
            pygame.draw.rect(surface,
                             (40, 40, 60) if selected else (15, 15, 30),
                             opt_rect, border_radius=8)
            if selected:
                pygame.draw.rect(surface, col, opt_rect, 2, border_radius=8)
            surface.blit(font.render(label, True, col if selected else LIGHT_GRAY),
                         (opt_rect.x + 16, opt_rect.y + 10))
            y_opt += 52

        surface.blit(font.render(
            "↑ ↓ navegar   Enter confirmar", True, GRAY),
            (px + 20, py + ph_panel - 30))


class PopulationGraph:
    def __init__(self, x, y, width, height):
        self.x            = x
        self.y            = y
        self.width        = width
        self.height       = height
        self.max_population = 2000
        self.history      = []

    def update(self, population):
        self.history.append(population)
        if len(self.history) > 300:
            self.history.pop(0)
        if self.history:
            self.max_population = max(self.max_population, max(self.history) * 1.15)

    def draw(self, surface):
        if len(self.history) < 2:
            return

        # Fondo
        bg = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        pygame.draw.rect(bg, (10, 10, 25, 200),
                         (0, 0, self.width, self.height), border_radius=10)
        surface.blit(bg, (self.x, self.y))
        pygame.draw.rect(surface, (60, 60, 90),
                         (self.x, self.y, self.width, self.height),
                         2, border_radius=10)

        surface.blit(font.render("Población", True, WHITE),
                     (self.x + 10, self.y + 8))

        # Línea
        points = []
        for i, pop in enumerate(self.history):
            xp = self.x + 10 + int(i / (len(self.history) - 1) * (self.width - 20))
            yp = self.y + self.height - 20 - int(
                (pop / self.max_population) * (self.height - 35))
            points.append((xp, yp))

        if len(points) > 1:
            pygame.draw.lines(surface, GREEN, False, points, 2)

        # Valor actual
        surface.blit(font.render(f"{self.history[-1]}", True, GREEN),
                     (self.x + 10, self.y + self.height - 22))


# ========================
# FUNCIONES DE DIBUJO
# ========================

def _draw_panel_bg(surface, x, y, w, h, border_color,
                   alpha=PANEL_ALPHA, radius=14):
    """Panel semitransparente reutilizable."""
    bg = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(bg, (8, 8, 18, alpha), (0, 0, w, h), border_radius=radius)
    surface.blit(bg, (x, y))
    pygame.draw.rect(surface, border_color, (x, y, w, h), 2, border_radius=radius)


def draw_nutrient_background(surface, nutrients, current_w, current_h):
    """Fondo negro. Barra de nutrientes en la parte inferior."""
    surface.fill((0, 0, 0))

    bar_h = 5
    bar_y = current_h - bar_h
    bar_w = int((nutrients / 100.0) * current_w)

    if nutrients > 60:
        bar_color = (50, 220, 80)
    elif nutrients > 30:
        bar_color = (220, 180, 50)
    else:
        bar_color = (220, 60, 60)

    pygame.draw.rect(surface, (20, 20, 20), (0, bar_y, current_w, bar_h))
    pygame.draw.rect(surface, bar_color,   (0, bar_y, bar_w, bar_h))

    if nutrients < 20:
        warn = font.render("⚠ NUTRIENTES CRÍTICOS", True, (255, 80, 80))
        surface.blit(warn,
                     (current_w // 2 - warn.get_width() // 2, bar_y - 26))


def draw_info_panel(surface, temp, humidity, ph, light, nutrients,
                    current_microbe, simulated_days, particles):
    """Panel lateral izquierdo — info del microbio y factores."""
    microbe_data = get_microbe_data(current_microbe)

    if microbe_data and "color" in microbe_data:
        color = tuple(max(0, min(255, int(v))) for v in microbe_data["color"])
    else:
        color = (70, 255, 70)

    healthy  = sum(1 for p in particles if p.state == "healthy")
    stressed = sum(1 for p in particles if p.state == "stressed")
    total    = len(particles)

    pw, ph_p = SIDEBAR_W - 10, 290
    px, py   = 8, 8

    _draw_panel_bg(surface, px, py, pw, ph_p, color)

    # Título
    surface.blit(big_font.render("GestBact AI", True, WHITE),
                 (px + 12, py + 10))

    # Nombre microbio
    name_txt = microbe_data["name"] if microbe_data else current_microbe
    surface.blit(font.render(name_txt, True, color),
                 (px + 12, py + 42))

    # Separador
    pygame.draw.line(surface, color,
                     (px + 10, py + 65), (px + pw - 10, py + 65), 1)

    # Factores
    rows = [
        ("Temperatura",  f"{temp:.1f} °C",      YELLOW),
        ("Humedad",      f"{humidity:.0f} %",   CYAN),
        ("pH",           f"{ph:.2f}",            PURPLE),
        ("Luz UV",       f"{light:.0f} %",      ORANGE),
        ("Nutrientes",   f"{nutrients:.1f} %",
         GREEN if nutrients > 30 else RED),
        ("Días",         f"{simulated_days}",    ORANGE),
    ]

    y_row = py + 75
    for label, value, col in rows:
        surface.blit(font.render(label, True, LIGHT_GRAY),
                     (px + 14, y_row))
        surface.blit(font.render(value, True, col),
                     (px + pw - 90, y_row))
        y_row += 28

    # Separador
    pygame.draw.line(surface, (60, 60, 80),
                     (px + 10, y_row), (px + pw - 10, y_row), 1)
    y_row += 8

    # Estadísticas población
    surface.blit(font.render(f"Total: {total}", True, WHITE),
                 (px + 14, y_row))
    surface.blit(font.render(f"✔ {healthy}", True, GREEN),
                 (px + 110, y_row))
    surface.blit(font.render(f"⚠ {stressed}", True, ORANGE),
                 (px + 185, y_row))


def draw_sliders_panel(surface, temp_slider, hum_slider,
                        ph_slider, light_slider, nutrient_slider,
                        panel_x, panel_y, panel_w):
    """Panel de sliders reubicado sin solaparse con info."""
    ph_p = 175
    _draw_panel_bg(surface, panel_x, panel_y, panel_w, ph_p, (60, 60, 90))

    # Reubicar sliders dentro del panel
    sx    = panel_x + 90
    sw    = panel_w - 110
    base_y = panel_y + 30

    sliders = [temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider]
    for idx, sl in enumerate(sliders):
        sl.x     = sx
        sl.width = sw
        sl.y     = base_y + idx * 30
        sl.draw(surface)


def draw_controls_help(surface, current_w, current_h):
    """Panel de controles — esquina inferior derecha."""
    lines = [
        "1 dedo Izq → Temp   |  1 dedo Der → Humedad",
        "3 dedos → pH        |  4 dedos → Luz UV",
        "← → Microbio  |  Pulgar ↑ → +1 Día",
        "B Antibiótico  |  N Custom  |  F Nutrientes",
        "M Análisis  |  Espacio Pausa  |  R Reiniciar",
    ]
    pw    = 420
    ph_p  = len(lines) * 22 + 16
    px    = current_w - pw - 8
    py    = current_h - ph_p - 12

    _draw_panel_bg(surface, px, py, pw, ph_p, (50, 50, 70), alpha=130)

    for idx, line in enumerate(lines):
        surface.blit(font.render(line, True, LIGHT_GRAY),
                     (px + 10, py + 8 + idx * 22))


# ========================
# FUNCIÓN PRINCIPAL DE DIBUJO
# ========================

def draw_ui(surface, temp, humidity, ph, light, nutrients, current_microbe,
            simulated_days, particles, population_graph,
            temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider):

    current_w, current_h = surface.get_size()

    # 1. Fondo + barra nutrientes
    draw_nutrient_background(surface, nutrients, current_w, current_h)

    # 2. Panel info — lateral izquierdo
    draw_info_panel(surface, temp, humidity, ph, light, nutrients,
                    current_microbe, simulated_days, particles)

    # 3. Sliders — parte superior, a la derecha del panel info
    slider_panel_x = SIDEBAR_W + 5
    slider_panel_w = min(380, current_w - slider_panel_x - 10)
    draw_sliders_panel(surface, temp_slider, hum_slider,
                       ph_slider, light_slider, nutrient_slider,
                       slider_panel_x, 8, slider_panel_w)

    # 4. Gráfica — a la derecha de los sliders
    graph_x = slider_panel_x + slider_panel_w + 8
    graph_w = current_w - graph_x - 8
    if graph_w > 150:
        population_graph.x      = graph_x
        population_graph.y      = 8
        population_graph.width  = graph_w
        population_graph.height = 185
        population_graph.draw(surface)

    # 5. Controles — esquina inferior derecha
    draw_controls_help(surface, current_w, current_h)