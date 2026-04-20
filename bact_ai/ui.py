# ========================
# UI.PY - Interfaz actualizada con 4 factores
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
        """Actualiza el valor del slider"""
        self.value = max(self.min_val, min(self.max_val, value))

    def draw(self, surface):
        # Fondo del slider
        pygame.draw.rect(surface, GRAY, (self.x, self.y, self.width, self.height), border_radius=8)
        
        # Barra de progreso
        fill_width = int((self.value - self.min_val) / (self.max_val - self.min_val) * self.width)
        pygame.draw.rect(surface, self.color, (self.x, self.y, fill_width, self.height), border_radius=8)
        
        # Mango (handle)
        handle_x = self.x + fill_width
        pygame.draw.circle(surface, WHITE, (handle_x, self.y + self.height//2), 11)
        pygame.draw.circle(surface, self.color, (handle_x, self.y + self.height//2), 9)

        # Texto del label + valor
        label_text = font.render(f"{self.label}: {self.value:.1f}", True, WHITE)
        surface.blit(label_text, (self.x, self.y - 28))


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

        # Dibujar la línea de la gráfica
        points = []
        for i, pop in enumerate(self.history):
            x_pos = self.x + 15 + int(i / (len(self.history) - 1) * (self.width - 30))
            y_pos = self.y + self.height - 15 - int((pop / self.max_population) * (self.height - 30))
            points.append((x_pos, y_pos))

        if len(points) > 1:
            pygame.draw.lines(surface, GREEN, False, points, 3)

        # Etiquetas
        current = font.render(f"Actual: {self.history[-1]}", True, GREEN)
        surface.blit(current, (self.x + 20, self.y + self.height - 28))


# ========================
# FUNCIONES DE DIBUJO
# ========================

def draw_info_panel(surface, temp, humidity, ph, light, current_microbe, simulated_days, is_bacteria_mode, particles_count):
    microbe_data = get_microbe_data(current_microbe)
    color = microbe_data["color"] if microbe_data else GREEN

    panel_x = 20
    panel_y = 20
    panel_width = 380
    panel_height = 280

    # Fondo semi-transparente
    s = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, 170), (0, 0, panel_width, panel_height), border_radius=15)
    surface.blit(s, (panel_x, panel_y))

    # Borde
    pygame.draw.rect(surface, color, (panel_x, panel_y, panel_width, panel_height), 3, border_radius=15)

    lines = [
        ("GestBact AI - Simulación Científica", big_font, WHITE),
        (f"Microorganismo: {microbe_data['name'] if microbe_data else current_microbe}", font, color),
        (f"Temperatura: {temp:.1f} °C", font, YELLOW),
        (f"Humedad: {humidity:.0f} %", font, CYAN),
        (f"pH: {ph:.1f}", font, PURPLE),
        (f"Iluminación UV: {light:.0f} %", font, ORANGE),
        (f"Días simulados: {simulated_days}", font, ORANGE),
        (f"Partículas: {particles_count}", font, WHITE),
        (f"Modo: {'BACTERIAS ACTIVAS' if is_bacteria_mode else 'Física'}", 
         font, GREEN if is_bacteria_mode else CYAN),
    ]

    y_offset = 28
    for text, fnt, col in lines:
        surface.blit(fnt.render(text, True, col), (panel_x + 22, panel_y + y_offset))
        y_offset += 37


def draw_controls_help(surface, current_h):
    help_texts = [
        "Controles:",
        "• 1 dedo (Izq) → Temperatura",
        "• 1 dedo (Der) → Humedad",
        "• Flecha ← → → Cambiar microbio",
        "• Pulgar arriba → +1 Día",
        "• Tecla B → Activar/Desactivar bacterias",
        "• Espacio → Pausar | R → Reiniciar",
    ]

    y = current_h - 185
    for line in help_texts:
        txt = font.render(line, True, LIGHT_GRAY)
        surface.blit(txt, (25, y))
        y += 23


# ========================
# FUNCIÓN PRINCIPAL DE DIBUJO
# ========================

def draw_ui(surface, temp, humidity, ph, light, current_microbe, simulated_days, 
            is_bacteria_mode, particles, population_graph, 
            temp_slider, hum_slider, ph_slider, light_slider):
    
    current_w, current_h = surface.get_size()

    # Panel de información
    draw_info_panel(surface, temp, humidity, ph, light, current_microbe, 
                   simulated_days, is_bacteria_mode, len(particles))

    # Sliders (4 factores)
    temp_slider.draw(surface)
    hum_slider.draw(surface)
    ph_slider.draw(surface)
    light_slider.draw(surface)

    # Gráfica de población
    population_graph.draw(surface)

    # Ayuda de controles
    draw_controls_help(surface, current_h)