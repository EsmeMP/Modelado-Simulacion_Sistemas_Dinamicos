# ========================
# UI.PY - Versión corregida con 4 factores
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
        """Maneja eventos de mouse. Retorna True si el valor cambió."""
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
        """Dibuja el slider"""
        # Barra de fondo
        pygame.draw.rect(surface, GRAY, (self.x, self.y, self.width, self.height), border_radius=8)

        # Barra rellena
        fill_width = int((self.value - self.min_val) / (self.max_val - self.min_val) * self.width)
        pygame.draw.rect(surface, self.color, (self.x, self.y, fill_width, self.height), border_radius=8)

        # Handle (botón deslizante)
        handle_x = self.x + fill_width
        radius = 13 if self.dragging else 11
        pygame.draw.circle(surface, WHITE, (handle_x, self.y + self.height//2), radius)
        pygame.draw.circle(surface, self.color, (handle_x, self.y + self.height//2), radius - 2)

        # Etiqueta
        label_text = font.render(f"{self.label}: {self.value:.1f}", True, WHITE)
        surface.blit(label_text, (self.x, self.y - 28))


class CustomMicrobeForm:
    """
    Formulario para agregar bacterias custom.
    Se activa con tecla N. Confirma con Enter o Tab campo a campo, cancela con Escape.
    """
    FIELDS = [
        ("clave",            "Nombre clave (ej: MiBact)",  str),
        ("name",             "Nombre científico",          str),
        ("optimal_temp",     "Temperatura óptima (°C)",    float),
        ("temp_min",         "Temp mínima (°C)",           float),
        ("temp_max",         "Temp máxima (°C)",           float),
        ("optimal_ph",       "pH óptimo",                  float),
        ("ph_min",           "pH mínimo",                  float),
        ("ph_max",           "pH máximo",                  float),
        ("optimal_humidity", "Humedad óptima (%)",         float),
        ("light_sensitivity","Sensibilidad luz (0.0-1.0)", float),
        ("base_rate",        "Tasa base (0.01-0.05)",      float),
        ("color_r",          "Color R (0-255)",            int),
        ("color_g",          "Color G (0-255)",            int),
        ("color_b",          "Color B (0-255)",            int),
        ("description",      "Descripción corta",          str),
    ]

    def __init__(self):
        self.active = False
        self.current_field = 0
        self.inputs = {f[0]: "" for f in self.FIELDS}
        self.error_msg = ""
        self.success_msg = ""
        self.success_timer = 0

    def toggle(self):
        self.active = not self.active
        if self.active:
            self.current_field = 0
            self.inputs = {f[0]: "" for f in self.FIELDS}
            self.error_msg = ""

    def handle_event(self, event):
        """Retorna (key, data) si se completó el formulario, None en cualquier otro caso."""
        if not self.active:
            return None

        if event.type == pygame.KEYDOWN:

            if event.key == pygame.K_ESCAPE:
                self.active = False
                return None

            elif event.key in (pygame.K_RETURN, pygame.K_TAB):
                field_key, _, field_type = self.FIELDS[self.current_field]
                val = self.inputs[field_key].strip()

                # Validar campo vacío
                if not val:
                    self.error_msg = "El campo no puede estar vacío"
                    return None

                # Validar tipo numérico
                if field_type in (float, int):
                    try:
                        field_type(val)
                        self.error_msg = ""
                    except ValueError:
                        self.error_msg = "Se esperaba un número"
                        return None

                # Avanzar al siguiente campo o guardar si es el último
                if self.current_field < len(self.FIELDS) - 1:
                    self.current_field += 1
                    self.error_msg = ""
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

    def _build_and_save(self):
        """Construye el dict del microbio y lo persiste en JSON."""
        from microbes import save_custom_microbe
        try:
            i = self.inputs
            key = i["clave"].strip()
            data = {
                "name":               i["name"].strip(),
                "type":               "bacteria",
                "optimal_temp":       float(i["optimal_temp"]),
                "temp_range":         (float(i["temp_min"]), float(i["temp_max"])),
                "optimal_humidity":   float(i["optimal_humidity"]),
                "optimal_ph":         float(i["optimal_ph"]),
                "ph_range":           (float(i["ph_min"]), float(i["ph_max"])),
                "light_sensitivity":  float(i["light_sensitivity"]),
                "base_rate":          float(i["base_rate"]),
                "color":              (int(i["color_r"]), int(i["color_g"]), int(i["color_b"])),
                "description":        i["description"].strip(),
            }
            save_custom_microbe(key, data)
            self.success_msg = f"'{key}' guardado correctamente"
            self.active = False
            return (key, data)
        except Exception as e:
            self.error_msg = f"Error al guardar: {e}"
            return None

    def draw(self, surface):
        if not self.active:
            return

        sw, sh = surface.get_size()

        # Overlay oscuro
        overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))
        surface.blit(overlay, (0, 0))

        # Panel central
        pw, ph_panel = 560, 480
        px = (sw - pw) // 2
        py = (sh - ph_panel) // 2
        pygame.draw.rect(surface, (15, 15, 30), (px, py, pw, ph_panel), border_radius=16)
        pygame.draw.rect(surface, PURPLE, (px, py, pw, ph_panel), 2, border_radius=16)

        # Título
        title = big_font.render("Nueva Bacteria Custom  [Esc = cancelar]", True, PURPLE)
        surface.blit(title, (px + 20, py + 18))

        # Progreso
        progress = font.render(f"Campo {self.current_field + 1} / {len(self.FIELDS)}", True, LIGHT_GRAY)
        surface.blit(progress, (px + 20, py + 55))

        # Etiqueta del campo actual
        field_key, field_label, _ = self.FIELDS[self.current_field]
        label_surf = font.render(field_label + ":", True, CYAN)
        surface.blit(label_surf, (px + 20, py + 100))

        # Caja de texto activa
        input_val = self.inputs[field_key]
        input_rect = pygame.Rect(px + 20, py + 130, pw - 40, 42)
        pygame.draw.rect(surface, (30, 30, 55), input_rect, border_radius=8)
        pygame.draw.rect(surface, CYAN, input_rect, 2, border_radius=8)
        input_surf = big_font.render(input_val + "|", True, WHITE)
        surface.blit(input_surf, (input_rect.x + 10, input_rect.y + 8))

        # Preview de campos ya completados
        surface.blit(font.render("Completados:", True, GRAY), (px + 20, py + 200))
        y_prev = py + 228
        for idx, (fk, fl, _) in enumerate(self.FIELDS):
            if idx >= self.current_field:
                break
            preview = font.render(f"  {fl}: {self.inputs[fk]}", True, GREEN)
            surface.blit(preview, (px + 20, y_prev))
            y_prev += 22
            if y_prev > py + ph_panel - 70:
                break

        # Mensaje de error
        if self.error_msg:
            err_surf = font.render(self.error_msg, True, RED)
            surface.blit(err_surf, (px + 20, py + ph_panel - 55))

        # Hint
        hint = font.render("Enter o Tab → siguiente campo", True, GRAY)
        surface.blit(hint, (px + 20, py + ph_panel - 30))


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

        title = font.render("Población a lo largo del tiempo", True, WHITE)
        surface.blit(title, (self.x + 15, self.y - 32))

        points = []
        for i, pop in enumerate(self.history):
            x_pos = self.x + 15 + int(i / (len(self.history) - 1) * (self.width - 30))
            y_pos = self.y + self.height - 15 - int((pop / self.max_population) * (self.height - 30))
            points.append((x_pos, y_pos))

        if len(points) > 1:
            pygame.draw.lines(surface, GREEN, False, points, 3)

        current = font.render(f"Actual: {self.history[-1]}", True, GREEN)
        surface.blit(current, (self.x + 20, self.y + self.height - 28))


# ========================
# FUNCIONES DE DIBUJO
# ========================

def draw_info_panel(surface, temp, humidity, ph, light, current_microbe, simulated_days, particles):
    # --- FIX: recibe la lista completa de particles, no solo el conteo ---
    # Así puede calcular healthy y stressed directamente aquí
    microbe_data = get_microbe_data(current_microbe)
    color = microbe_data["color"] if microbe_data else GREEN

    # Conteo por estado
    healthy  = sum(1 for p in particles if p.state == "healthy")
    stressed = sum(1 for p in particles if p.state == "stressed")
    total    = len(particles)

    panel_x, panel_y = 20, 20
    panel_width, panel_height = 380, 290   # un poco más alto para la línea extra

    s = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, 170), (0, 0, panel_width, panel_height), border_radius=15)
    surface.blit(s, (panel_x, panel_y))
    pygame.draw.rect(surface, color, (panel_x, panel_y, panel_width, panel_height), 3, border_radius=15)

    lines = [
        ("GestBact AI - Simulación Científica",                    big_font, WHITE),
        (f"Microorganismo: {microbe_data['name'] if microbe_data else current_microbe}", font, color),
        (f"Temperatura: {temp:.1f} °C",                            font, YELLOW),
        (f"Humedad: {humidity:.0f} %",                             font, CYAN),
        (f"pH: {ph:.2f}",                                          font, PURPLE),
        (f"Iluminación UV: {light:.0f} %",                         font, ORANGE),
        (f"Días simulados: {simulated_days}",                      font, ORANGE),
        (f"Total: {total}   ✔ Sanas: {healthy}   ⚠ Estrés: {stressed}", font, WHITE),
    ]

    y_offset = 28
    for text, fnt, col in lines:
        surface.blit(fnt.render(text, True, col), (panel_x + 22, panel_y + y_offset))
        y_offset += 33


def draw_controls_help(surface, current_h):
    help_texts = [
        "Controles:",
        "• 1 dedo (Izq) → Temperatura",
        "• 1 dedo (Der) → Humedad",
        "• 3 dedos → pH  (izq ↓ / der ↑)",
        "• 4 dedos → Luz UV  (sube/baja mano)",
        "• Flecha ← → → Cambiar microbio",
        "• Pulgar arriba → +1 Día",
        "• Tecla B → Aplicar antibiótico",
        "• Tecla N → Nueva bacteria custom",
        "• Espacio → Pausar | R → Reiniciar",
    ]

    y = current_h - 235   # ajustado por la línea extra
    for line in help_texts:
        txt = font.render(line, True, LIGHT_GRAY)
        surface.blit(txt, (25, y))
        y += 23


# ========================
# FUNCIÓN PRINCIPAL DE DIBUJO
# ========================

def draw_ui(surface, temp, humidity, ph, light, current_microbe, simulated_days,
            particles, population_graph,
            temp_slider, hum_slider, ph_slider, light_slider):
    # --- FIX: eliminado is_bacteria_mode de la firma, ya no se usa ---
    # --- FIX: particles se pasa directo a draw_info_panel (no len()) ---

    current_w, current_h = surface.get_size()

    draw_info_panel(surface, temp, humidity, ph, light, current_microbe,
                    simulated_days, particles)       # ← lista completa

    temp_slider.draw(surface)
    hum_slider.draw(surface)
    ph_slider.draw(surface)
    light_slider.draw(surface)

    population_graph.draw(surface)

    draw_controls_help(surface, current_h)