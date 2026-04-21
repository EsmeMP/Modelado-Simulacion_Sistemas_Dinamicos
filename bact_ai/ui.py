# ========================
# UI.PY - Versión con 5 factores y validación al final del formulario
# ========================

import pygame
from config import *
from microbes import get_microbe_data


class Slider:
    def __init__(self, x, y, width, min_val, max_val, label, color):
        self.x = x
        self.y = y
        self.width = width
        self.height = 18
        self.min_val = min_val
        self.max_val = max_val
        self.label = label
        self.color = color
        self.value = (min_val + max_val) / 2
        self.dragging = False

    def update(self, value):
        if not self.dragging:
            self.value = max(self.min_val, min(self.max_val, value))

    def handle_event(self, event):
        handle_x = self.x + int((self.value - self.min_val) / (self.max_val - self.min_val) * self.width)
        handle_y = self.y + self.height // 2

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if abs(mx - handle_x) < 14 and abs(my - handle_y) < 14:
                self.dragging = True
                return True

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.dragging = False

        elif event.type == pygame.MOUSEMOTION and self.dragging:
            mx = event.pos[0]
            ratio = (mx - self.x) / self.width
            self.value = self.min_val + ratio * (self.max_val - self.min_val)
            self.value = max(self.min_val, min(self.max_val, self.value))
            return True

        return False

    def draw(self, surface):
        pygame.draw.rect(surface, GRAY, (self.x, self.y, self.width, self.height), border_radius=8)
        fill_width = int((self.value - self.min_val) / (self.max_val - self.min_val) * self.width)
        pygame.draw.rect(surface, self.color, (self.x, self.y, fill_width, self.height), border_radius=8)
        handle_x = self.x + fill_width
        radius = 13 if self.dragging else 11
        pygame.draw.circle(surface, WHITE, (handle_x, self.y + self.height//2), radius)
        pygame.draw.circle(surface, self.color, (handle_x, self.y + self.height//2), radius - 2)
        label_text = font.render(f"{self.label}: {self.value:.1f}", True, WHITE)
        surface.blit(label_text, (self.x, self.y - 28))


# ========================
# ESTADOS DEL FORMULARIO
# ========================
FORM_FILLING   = "filling"    # usuario llenando campos
FORM_ERRORS    = "errors"     # panel de errores detectados
FORM_DONE      = "done"       # guardado exitoso


class CustomMicrobeForm:
    """
    Formulario para agregar bacterias custom.
    - Tecla N         → abrir
    - Enter / Tab     → siguiente campo (sin bloquear por errores)
    - Escape          → cancelar
    - Al llegar al último campo → valida todo junto
      - Si hay errores → muestra panel con 3 opciones
      - Si no hay errores → guarda directamente
    """

    FIELDS = [
        ("clave",            "Nombre clave (ej: MiBact)",       str),
        ("name",             "Nombre científico",               str),
        ("optimal_temp",     "Temp óptima °C  [0-100]",         float),
        ("temp_min",         "Temp mínima °C",                  float),
        ("temp_max",         "Temp máxima °C",                  float),
        ("optimal_ph",       "pH óptimo  [4.0-9.0]",            float),
        ("ph_min",           "pH mínimo  [>=4.0]",              float),
        ("ph_max",           "pH máximo  [<=9.0]",              float),
        ("optimal_humidity", "Humedad óptima %  [0-100]",       float),
        ("light_sensitivity","Sensibilidad luz  [0.0-1.0]",     float),
        ("base_rate",        "Tasa base  [0.001-0.1]",          float),
        ("color_r",          "Color R  [0-255]",                int),
        ("color_g",          "Color G  [0-255]",                int),
        ("color_b",          "Color B  [0-255]",                int),
        ("description",      "Descripción corta",               str),
    ]

    # Opciones del panel de error
    OPT_AUTO   = 0
    OPT_EDIT   = 1
    OPT_CANCEL = 2

    def __init__(self):
        self.active        = False
        self.form_state    = FORM_FILLING
        self.current_field = 0
        self.inputs        = {f[0]: "" for f in self.FIELDS}
        self.error_msg     = ""        # error de tipo (campo no numérico)
        self.detected_errors = []      # lista de errores de rango detectados
        self.error_option  = self.OPT_AUTO   # opción seleccionada en el panel
        self.success_msg   = ""
        self.success_timer = 0

    def toggle(self):
        self.active = not self.active
        if self.active:
            self._reset()

    def _reset(self):
        self.form_state    = FORM_FILLING
        self.current_field = 0
        self.inputs        = {f[0]: "" for f in self.FIELDS}
        self.error_msg     = ""
        self.detected_errors = []
        self.error_option  = self.OPT_AUTO

    # ── Validación de tipo (solo números donde se espera número) ──
    def _validate_type(self, field_key, field_type, val):
        if field_type in (float, int):
            try:
                field_type(val)
                return True
            except ValueError:
                return False
        return True

    # ── Detecta todos los errores de rango sin bloquear ──
    def _detect_range_errors(self):
        errors = []
        i = self.inputs
        try:
            optimal_temp     = float(i["optimal_temp"])
            temp_min         = float(i["temp_min"])
            temp_max         = float(i["temp_max"])
            optimal_ph       = float(i["optimal_ph"])
            ph_min           = float(i["ph_min"])
            ph_max           = float(i["ph_max"])
            optimal_humidity = float(i["optimal_humidity"])
            light_s          = float(i["light_sensitivity"])
            base_rate        = float(i["base_rate"])
            cr, cg, cb       = int(i["color_r"]), int(i["color_g"]), int(i["color_b"])

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

    # ── Corrección automática ──
    def _auto_fix(self):
        i = self.inputs

        def clamp(key, lo, hi):
            try:
                v = float(i[key])
                i[key] = str(max(lo, min(hi, v)))
            except Exception:
                i[key] = str((lo + hi) / 2)

        def clamp_int(key, lo, hi):
            try:
                v = int(i[key])
                i[key] = str(max(lo, min(hi, v)))
            except Exception:
                i[key] = str((lo + hi) // 2)

        clamp("optimal_temp",     0,    100)
        clamp("temp_min",         -10,  80)
        clamp("temp_max",         0,    100)
        clamp("optimal_ph",       4.0,  9.0)
        clamp("ph_min",           4.0,  9.0)
        clamp("ph_max",           4.0,  9.0)
        clamp("optimal_humidity", 0,    100)
        clamp("light_sensitivity",0.0,  1.0)
        clamp("base_rate",        0.001,0.1)
        clamp_int("color_r",      0,    255)
        clamp_int("color_g",      0,    255)
        clamp_int("color_b",      0,    255)

        # Corregir rangos invertidos
        try:
            tmin = float(i["temp_min"])
            tmax = float(i["temp_max"])
            if tmin >= tmax:
                i["temp_min"] = str(tmax - 5)
        except Exception:
            pass

        try:
            pmin = float(i["ph_min"])
            pmax = float(i["ph_max"])
            if pmin >= pmax:
                i["ph_min"] = str(pmax - 0.5)
        except Exception:
            pass

    # ── Construir dict y guardar ──
    def _build_and_save(self):
        from microbes import save_custom_microbe
        try:
            i   = self.inputs
            key = i["clave"].strip()
            data = {
                "name":                i["name"].strip(),
                "type":                "bacteria",
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
            self.error_msg = f"Error al guardar: {e}"
            self.form_state = FORM_FILLING
            return None

    # ── Manejo de eventos ──
    def handle_event(self, event):
        if not self.active:
            return None

        if event.type != pygame.KEYDOWN:
            return None

        # ── Panel de errores ──
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
                    # Regresar al primer campo con error
                    self.form_state = FORM_FILLING
                    self.current_field = 0
                    self.error_msg = "Revisa y corrige los campos marcados"
                elif self.error_option == self.OPT_CANCEL:
                    self.active = False
                    self._reset()
            elif event.key == pygame.K_ESCAPE:
                self.active = False
                self._reset()
            return None

        # ── Llenado de campos ──
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
                # Avanzar al siguiente campo
                self.current_field += 1
            else:
                # Último campo → validar todo
                errors = self._detect_range_errors()
                if errors:
                    self.detected_errors = errors
                    self.form_state      = FORM_ERRORS
                    self.error_option    = self.OPT_AUTO
                else:
                    return self._build_and_save()

        elif event.key == pygame.K_BACKSPACE:
            field_key = self.FIELDS[self.current_field][0]
            self.inputs[field_key] = self.inputs[field_key][:-1]

        else:
            if event.unicode:
                field_key = self.FIELDS[self.current_field][0]
                if len(self.inputs[field_key]) < 40:
                    self.inputs[field_key] += event.unicode

        return None

    # ── Dibujo ──
    def draw(self, surface):
        # Timer del mensaje de éxito
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

        pygame.draw.rect(surface, (15, 15, 30), (px, py, pw, ph_panel), border_radius=16)
        pygame.draw.rect(surface, PURPLE, (px, py, pw, ph_panel), 2, border_radius=16)

        # Título
        title = big_font.render("Nueva Bacteria Custom  [Esc = cancelar]", True, PURPLE)
        surface.blit(title, (px + 20, py + 18))

        # Progreso
        prog = font.render(f"Campo {self.current_field + 1} / {len(self.FIELDS)}", True, LIGHT_GRAY)
        surface.blit(prog, (px + 20, py + 55))

        # Campo actual
        field_key, field_label, _ = self.FIELDS[self.current_field]
        surface.blit(font.render(field_label + ":", True, CYAN), (px + 20, py + 100))

        # Caja de texto
        input_val  = self.inputs[field_key]
        input_rect = pygame.Rect(px + 20, py + 130, pw - 40, 42)
        pygame.draw.rect(surface, (30, 30, 55), input_rect, border_radius=8)
        pygame.draw.rect(surface, CYAN, input_rect, 2, border_radius=8)
        surface.blit(big_font.render(input_val + "|", True, WHITE),
                     (input_rect.x + 10, input_rect.y + 8))

        # Preview campos completados
        surface.blit(font.render("Completados:", True, GRAY), (px + 20, py + 200))
        y_prev = py + 228
        for idx, (fk, fl, _) in enumerate(self.FIELDS):
            if idx >= self.current_field:
                break
            surface.blit(font.render(f"  {fl}: {self.inputs[fk]}", True, GREEN),
                         (px + 20, y_prev))
            y_prev += 22
            if y_prev > py + ph_panel - 70:
                break

        # Error de tipo
        if self.error_msg:
            surface.blit(font.render(self.error_msg, True, RED), (px + 20, py + ph_panel - 55))

        surface.blit(font.render("Enter o Tab → siguiente campo", True, GRAY),
                     (px + 20, py + ph_panel - 30))

    def _draw_error_panel(self, surface, sw, sh):
        pw, ph_panel = 620, 480
        px = (sw - pw) // 2
        py = (sh - ph_panel) // 2

        pygame.draw.rect(surface, (20, 10, 10), (px, py, pw, ph_panel), border_radius=16)
        pygame.draw.rect(surface, RED, (px, py, pw, ph_panel), 2, border_radius=16)

        # Título
        surface.blit(big_font.render("⚠ Errores detectados en el microbio", True, RED),
                     (px + 20, py + 18))

        # Lista de errores
        y_e = py + 60
        for err in self.detected_errors[:6]:   # máximo 6 visibles
            surface.blit(font.render(f"  • {err}", True, YELLOW), (px + 20, y_e))
            y_e += 26

        # Separador
        pygame.draw.line(surface, GRAY, (px + 20, y_e + 10), (px + pw - 20, y_e + 10), 1)

        # Opciones
        options = [
            (self.OPT_AUTO,   "✔  Ajustar valores automáticamente",  GREEN),
            (self.OPT_EDIT,   "✏  Editar manualmente",               CYAN),
            (self.OPT_CANCEL, "✗  Cancelar",                         RED),
        ]

        y_opt = y_e + 30
        for opt_id, label, col in options:
            selected = self.error_option == opt_id
            bg_color = (40, 40, 60) if selected else (15, 15, 30)
            opt_rect = pygame.Rect(px + 20, y_opt, pw - 40, 40)
            pygame.draw.rect(surface, bg_color, opt_rect, border_radius=8)
            if selected:
                pygame.draw.rect(surface, col, opt_rect, 2, border_radius=8)
            surface.blit(font.render(label, True, col if selected else LIGHT_GRAY),
                         (opt_rect.x + 16, opt_rect.y + 10))
            y_opt += 52

        # Hint navegación
        surface.blit(font.render("↑ ↓ para navegar   Enter para confirmar", True, GRAY),
                     (px + 20, py + ph_panel - 30))


class PopulationGraph:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.max_population = 2000
        self.history = []

    def update(self, population):
        self.history.append(population)
        if len(self.history) > 300:
            self.history.pop(0)
        if self.history:
            self.max_population = max(self.max_population, max(self.history) * 1.15)

    def draw(self, surface):
        if len(self.history) < 2:
            return
        pygame.draw.rect(surface, (20, 20, 35), (self.x, self.y, self.width, self.height), border_radius=12)
        pygame.draw.rect(surface, LIGHT_GRAY, (self.x, self.y, self.width, self.height), 2, border_radius=12)
        surface.blit(font.render("Población a lo largo del tiempo", True, WHITE),
                     (self.x + 15, self.y - 32))
        points = []
        for i, pop in enumerate(self.history):
            x_pos = self.x + 15 + int(i / (len(self.history) - 1) * (self.width - 30))
            y_pos = self.y + self.height - 15 - int((pop / self.max_population) * (self.height - 30))
            points.append((x_pos, y_pos))
        if len(points) > 1:
            pygame.draw.lines(surface, GREEN, False, points, 3)
        surface.blit(font.render(f"Actual: {self.history[-1]}", True, GREEN),
                     (self.x + 20, self.y + self.height - 28))


# ========================
# FUNCIONES DE DIBUJO
# ========================

def draw_nutrient_background(surface, nutrients, current_w, current_h):
    ratio = max(0.0, min(1.0, nutrients / 100.0))
    g = int(5 + (25 - 5) * ratio)
    if g > 6:
        surface.fill((5, g, 5))


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

    panel_x, panel_y   = 20, 20
    panel_width        = 390
    panel_height       = 320

    s = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, 170), (0, 0, panel_width, panel_height), border_radius=15)
    surface.blit(s, (panel_x, panel_y))
    pygame.draw.rect(surface, color, (panel_x, panel_y, panel_width, panel_height), 3, border_radius=15)

    nutrient_color = GREEN if nutrients > 30 else RED

    lines = [
        ("GestBact AI - Simulación Científica",                             big_font, WHITE),
        (f"Microorganismo: {microbe_data['name'] if microbe_data else current_microbe}", font, color),
        (f"Temperatura:     {temp:.1f} °C",                                 font, YELLOW),
        (f"Humedad:         {humidity:.0f} %",                              font, CYAN),
        (f"pH:              {ph:.2f}",                                       font, PURPLE),
        (f"Iluminación UV:  {light:.0f} %",                                 font, ORANGE),
        (f"Nutrientes:      {nutrients:.1f} %",                             font, nutrient_color),
        (f"Días simulados:  {simulated_days}",                              font, ORANGE),
        (f"Total: {total}   ✔ Sanas: {healthy}   ⚠ Estrés: {stressed}",   font, WHITE),
    ]

    y_offset = 28
    for text, fnt, col in lines:
        surface.blit(fnt.render(text, True, col), (panel_x + 22, panel_y + y_offset))
        y_offset += 33


def draw_controls_help(surface, current_h):
    help_texts = [
        "Controles:",
        "• 1 dedo (Izq)  → Temperatura",
        "• 1 dedo (Der)  → Humedad",
        "• 3 dedos       → pH  (sube/baja mano)",
        "• 4 dedos       → Luz UV  (sube/baja mano)",
        "• Flechas ← →   → Cambiar microbio",
        "• Pulgar arriba  → +1 Día",
        "• Tecla B        → Aplicar antibiótico",
        "• Tecla N        → Nueva bacteria custom",
        "• Tecla F        → Reponer nutrientes 100%",
        "• Espacio        → Pausar | R → Reiniciar",
    ]
    y = current_h - 258
    for line in help_texts:
        surface.blit(font.render(line, True, LIGHT_GRAY), (25, y))
        y += 23


def draw_ui(surface, temp, humidity, ph, light, nutrients, current_microbe, simulated_days,
            particles, population_graph,
            temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider):

    current_w, current_h = surface.get_size()
    draw_nutrient_background(surface, nutrients, current_w, current_h)
    draw_info_panel(surface, temp, humidity, ph, light, nutrients,
                    current_microbe, simulated_days, particles)
    temp_slider.draw(surface)
    hum_slider.draw(surface)
    ph_slider.draw(surface)
    light_slider.draw(surface)
    nutrient_slider.draw(surface)
    population_graph.draw(surface)
    draw_controls_help(surface, current_h)