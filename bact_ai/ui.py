# ========================
# UI.PY - Interfaz visual avanzada para GestBact AI
# ========================

import pygame
import numpy as np
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
        """Actualiza el valor del slider (0 a 1)"""
        self.value = np.clip(value, self.min_val, self.max_val)

    def draw(self, surface):
        # Fondo del slider
        pygame.draw.rect(surface, GRAY, (self.x, self.y, self.width, self.height), border_radius=8)
        
        # Barra de progreso
        fill_width = int((self.value - self.min_val) / (self.max_val - self.min_val) * self.width)
        pygame.draw.rect(surface, self.color, (self.x, self.y, fill_width, self.height), border_radius=8)
        
        # Mango (handle)
        handle_x = self.x + fill_width
        pygame.draw.circle(surface, WHITE, (handle_x, self.y + self.height//2), 10)
        pygame.draw.circle(surface, self.color, (handle_x, self.y + self.height//2), 8)

        # Texto
        label_text = font.render(f"{self.label}: {self.value:.1f}", True, WHITE)
        surface.blit(label_text, (self.x, self.y - 28))

    def get_value(self):
        return self.value


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
        self.max_population = max(self.max_population, max(self.history) * 1.1)

    def draw(self, surface):
        if len(self.history) < 2:
            return

        pygame.draw.rect(surface, (20, 20, 30), (self.x, self.y, self.width, self.height), border_radius=10)
        pygame.draw.rect(surface, LIGHT_GRAY, (self.x, self.y, self.width, self.height), 2, border_radius=10)

        # Título
        title = font.render("Población de Microorganismos", True, WHITE)
        surface.blit(title, (self.x + 10, self.y - 30))

        # Línea de la gráfica
        points = []
        for i, pop in enumerate(self.history):
            x = self.x + int(i / (len(self.history)-1) * (self.width - 20))
            y = self.y + self.height - int((pop / self.max_population) * (self.height - 20))
            points.append((x, y))

        if len(points) > 1:
            pygame.draw.lines(surface, GREEN, False, points, 3)

        # Etiquetas
        max_text = font.render(f"Max: {int(self.max_population)}", True, GREEN)
        surface.blit(max_text, (self.x + self.width - 90, self.y + 8))

        current_text = font.render(f"Actual: {self.history[-1]}", True, WHITE)
        surface.blit(current_text, (self.x + 10, self.y + self.height - 28))


# ========================
# FUNCIONES DE DIBUJO
# ========================

def draw_info_panel(surface, temp, humidity, current_microbe, simulated_days, is_bacteria_mode, particles_count):
    microbe_data = get_microbe_data(current_microbe)
    color = microbe_data["color"] if microbe_data else GREEN

    panel_x = 20
    panel_y = 20
    panel_width = 380
    panel_height = 260

    # Fondo semi-transparente
    s = pygame.Surface((panel_width, panel_height), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, 160), (0, 0, panel_width, panel_height), border_radius=15)
    surface.blit(s, (panel_x, panel_y))

    # Borde
    pygame.draw.rect(surface, color, (panel_x, panel_y, panel_width, panel_height), 3, border_radius=15)

    lines = [
        ("GestBact AI", big_font, WHITE),
        (f"Microorganismo: {microbe_data['name'] if microbe_data else current_microbe}", font, color),
        (f"Temperatura: {temp:.1f} °C", font, YELLOW),
        (f"Humedad: {humidity:.0f} %", font, CYAN),
        (f"Días simulados: {simulated_days}", font, ORANGE),
        (f"Partículas: {particles_count}", font, WHITE),
        (f"Modo: {'BACTERIAS ACTIVAS' if is_bacteria_mode else 'Física'}", 
         font, GREEN if is_bacteria_mode else CYAN),
    ]

    y_offset = 25
    for text, fnt, col in lines:
        surface.blit(fnt.render(text, True, col), (panel_x + 20, panel_y + y_offset))
        y_offset += 38


def draw_controls_help(surface, current_h):
    help_text = [
        "Controles con Mano:",
        "• 1 dedo Izq → Temperatura",
        "• 1 dedo Der → Humedad",
        "• Mano + Pulgar ↑ → Cambiar microbio",
        "• Pulgar arriba → +1 Día",
        "• 3 dedos → Activar/Desactivar bacterias",
        "Teclado: ESPACIO = Pausa | R = Reiniciar | B = Bacterias",
    ]

    y = current_h - 190
    for line in help_text:
        txt = font.render(line, True, LIGHT_GRAY)
        surface.blit(txt, (25, y))
        y += 22


# ========================
# FUNCIÓN PRINCIPAL DE DIBUJO (se llamará desde main)
# ========================

def draw_ui(surface, temp, humidity, current_microbe, simulated_days, 
            is_bacteria_mode, particles, population_graph, temp_slider, hum_slider):
    
    current_w, current_h = surface.get_size()

    # Panel de información
    draw_info_panel(surface, temp, humidity, current_microbe, simulated_days, 
                   is_bacteria_mode, len(particles))

    # Sliders
    temp_slider.draw(surface)
    hum_slider.draw(surface)

    # Gráfica de población
    population_graph.draw(surface)

    # Ayuda de controles
    draw_controls_help(surface, current_h)