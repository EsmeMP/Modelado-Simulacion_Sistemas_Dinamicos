# ========================
# MAIN.PY - GestBact AI (Versión Completa y Corregida)
# ========================

import pygame
import sys
import numpy as np
import cv2
from collections import deque
import random

# Importamos nuestros módulos
from config import *
from microbes import get_all_microbes
from simulation import Particle, create_explosion, handle_collisions, update_bacteria_growth
from gestures import GestureController
from ui import Slider, PopulationGraph, draw_ui

# ========================
# INICIALIZACIÓN
# ========================
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("GestBact AI - Simulador de Bacterias y Virus con Gestos")
clock = pygame.time.Clock()

# Partículas iniciales
particles = [Particle(random.randint(80, WIDTH-80), 
                     random.randint(80, HEIGHT-150)) 
             for _ in range(INITIAL_PARTICLES)]

# Parámetros de simulación
temp = 25.0
humidity = 50.0
current_microbe = "E. coli"
simulated_days = 0
is_bacteria_mode = False
paused = False
show_trails = True
enable_collisions = True

# Componentes de UI
temp_slider = Slider(450, 65, 280, 0, 55, "Temperatura (°C)", YELLOW)
hum_slider = Slider(450, 115, 280, 10, 100, "Humedad (%)", CYAN)
population_graph = PopulationGraph(780, 65, 460, 180)

# Controlador de gestos
gesture_controller = GestureController()

# Variables auxiliares
running = True
gesture_text = "Esperando manos..."
last_day_time = 0
DAY_COOLDOWN = 800  # milisegundos entre +1 día

print("GestBact AI iniciado correctamente!")
print("Usa tus manos para controlar temperatura, humedad y microorganismos.")

# ========================
# BUCLE PRINCIPAL
# ========================
while running:
    dt = clock.tick(FPS) / 1000.0
    current_w, current_h = screen.get_size()

        # ------------------- Eventos de teclado -------------------
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                paused = not paused

            if event.key == pygame.K_r:
                particles.clear()
                particles = [Particle(random.randint(80, current_w-80),
                                    random.randint(80, current_h-150))
                            for _ in range(INITIAL_PARTICLES)]
                simulated_days = 0
                population_graph.history.clear()

            if event.key == pygame.K_b:
                is_bacteria_mode = not is_bacteria_mode

            if event.key == pygame.K_t:
                show_trails = not show_trails

            if event.key == pygame.K_c:
                enable_collisions = not enable_collisions

            # === CAMBIO DE MICROBIO CON TECLAS ===
            if event.key == pygame.K_RIGHT:   # Flecha derecha → Siguiente microbio
                keys = get_all_microbes() 
                idx = keys.index(current_microbe)
                current_microbe = keys[(idx + 1) % len(keys)]
                gesture_text = f"Microbio: {current_microbe}"

            elif event.key == pygame.K_LEFT:  # Flecha izquierda → Microbio anterior
                keys = get_all_microbes()    
                idx = keys.index(current_microbe)
                current_microbe = keys[(idx - 1) % len(keys)]
                gesture_text = f"Microbio: {current_microbe}"

    # ------------------- Procesar gestos con la cámara -------------------
    frame, result = gesture_controller.get_frame()
    if frame is None:
        break

    hand_forces = []
    vortex_centers = []

    if result:
        frame = gesture_controller.draw_landmarks(frame, result)
        
        hand_forces, vortex_centers, temp, humidity, current_microbe, gesture_text = \
            gesture_controller.process_gestures(result, current_w, current_h, temp, humidity, current_microbe)

    # Actualizar sliders
    temp_slider.update(temp)
    hum_slider.update(humidity)

    # ------------------- Actualizar simulación -------------------
    if not paused:
        total_ke = 0.0

        for p in particles[:]:
            total_force = np.zeros(2)

            # Fuerzas generadas por las manos
            for hand_pos, is_attract, strength in hand_forces:
                direction = hand_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 15:
                    direction /= dist
                    force_mag = (12500 + strength * 19000) / (dist**2 + 80)
                    force = direction * force_mag
                    if not is_attract:
                        force = -force
                    total_force += force
                    p.glow = max(p.glow, 0.9)

            # Vórtices
            for v_pos in vortex_centers:
                direction = v_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 10:
                    perpendicular = np.array([-direction[1], direction[0]])
                    p.vel += perpendicular * (780 / (dist + 30))

            p.update(total_force, dt)

            # Rebote en los bordes
            if p.pos[0] < 0 or p.pos[0] > current_w:
                p.vel[0] *= -0.82
                p.pos[0] = np.clip(p.pos[0], 5, current_w - 5)
            if p.pos[1] < 0 or p.pos[1] > current_h:
                p.vel[1] *= -0.82
                p.pos[1] = np.clip(p.pos[1], 5, current_h - 5)

            total_ke += 0.5 * np.dot(p.vel, p.vel)

        # Crecimiento de bacterias (solo si el modo está activado)
        if is_bacteria_mode:
            update_bacteria_growth(particles, temp, humidity, current_microbe, MAX_PARTICLES)

        # Colisiones
        if enable_collisions and len(particles) < 950:
            handle_collisions(particles)

        # Actualizar gráfica
        population_graph.update(len(particles))

    # ------------------- +1 Día con gesto -------------------
    current_time = pygame.time.get_ticks()
    if "¡+1 Día" in gesture_text and current_time - last_day_time > DAY_COOLDOWN:
        simulated_days = min(simulated_days + 1, 30)
        last_day_time = current_time
        # Feedback visual
        if particles:
            cx = current_w // 2
            cy = current_h // 2
            create_explosion(particles, cx, cy, count=25, intensity=0.7)

    # ========================
    # DIBUJAR TODO
    # ========================
    screen.fill(BLACK)

    # Trails optimizados
    if show_trails and len(particles) < 900:   # Solo trails cuando no este muy cargado
        for p in particles:
            speed = np.linalg.norm(p.vel)
            if speed > 15:   # Solo partículas que se mueven
                alpha = min(40, int(25 * (speed / 200)))
                trail_color = (*p.color[:3], alpha)
                pygame.draw.circle(screen, trail_color, (int(p.pos[0]), int(p.pos[1])), 3)

    # Partículas principales
    for p in particles:
        p.draw(screen)

    # Interfaz completa
    draw_ui(screen, temp, humidity, current_microbe, simulated_days, 
            is_bacteria_mode, particles, population_graph, temp_slider, hum_slider)

    # Mostrar gesto actual más grande si es importante
    if "Microbio" in gesture_text or "Temperatura" in gesture_text or "Humedad" in gesture_text:
        temp_font = pygame.font.SysFont("Arial", 28)
        gesture_surf = temp_font.render(gesture_text, True, PURPLE)
        screen.blit(gesture_surf, (current_w//2 - gesture_surf.get_width()//2, 25))

    pygame.display.flip()

    # Ventana de cámara
    if frame is not None:
        cv2.putText(frame, gesture_text, (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 255, 255), 3)
        cv2.imshow("Camara - GestBact AI", frame)

    if cv2.waitKey(1) == 27:   # ESC para salir
        running = False

# ========================
# CERRAR TODO
# ========================
gesture_controller.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()