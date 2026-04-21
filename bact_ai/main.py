# ========================
# MAIN.PY - GestBact AI con 5 Factores (Temp, Humedad, pH, Luz, Nutrientes)
# ========================

import pygame
import sys
import numpy as np
import cv2
import random
from collections import deque

# Importamos módulos
from config import *
from microbes import get_all_microbes, get_microbe_data
from simulation import Particle, create_explosion, handle_collisions, update_bacteria_growth
from gestures import GestureController
from ui import Slider, PopulationGraph, draw_ui, CustomMicrobeForm

# ========================
# INICIALIZACIÓN
# ========================
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("GestBact AI - Simulador con 5 Factores")
clock = pygame.time.Clock()

# === VARIABLES PRIMERO, partículas después ===
temp            = 25.0
humidity        = 50.0
ph              = 7.0
light           = 30.0
nutrients       = INITIAL_NUTRIENTS   # viene de config.py
current_microbe = "E. coli"
simulated_days  = 0
paused          = False
show_trails     = True
enable_collisions = True

# Partículas — todas nacen como bacterias
particles = [
    Particle(
        random.randint(80, WIDTH - 80),
        random.randint(80, HEIGHT - 150),
        is_bacteria=True,
        microbe_key=current_microbe
    )
    for _ in range(INITIAL_PARTICLES)
]

# Componentes UI
temp_slider     = Slider(450,  65, 280,  0,    60,  "Temperatura (°C)",   YELLOW)
hum_slider      = Slider(450, 115, 280,  5,   100,  "Humedad (%)",         CYAN)
ph_slider       = Slider(450, 165, 280,  4.0,   9.0, "pH",                PURPLE)
light_slider    = Slider(450, 215, 280,  0,   100,  "Iluminación UV (%)", ORANGE)
nutrient_slider = Slider(450, 265, 280,  0,   100,  "Nutrientes (%)",     GREEN)

population_graph   = PopulationGraph(780, 65, 460, 180)
gesture_controller = GestureController()
custom_form        = CustomMicrobeForm()

# Variables auxiliares
running       = True
gesture_text  = "Esperando manos..."
last_day_time = 0
DAY_COOLDOWN  = 800

print("GestBact AI iniciado con 5 factores científicos!")

# ========================
# BUCLE PRINCIPAL
# ========================
while running:
    dt = clock.tick(FPS) / 1000.0
    current_w, current_h = screen.get_size()

    # ------------------- Eventos -------------------
    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

        # Sliders arrastrables con mouse
        for slider in (temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider):
            if slider.handle_event(event):
                temp      = temp_slider.value
                humidity  = hum_slider.value
                ph        = ph_slider.value
                light     = light_slider.value
                nutrients = nutrient_slider.value

        # Teclado
        if event.type == pygame.KEYDOWN:

            # Formulario tiene prioridad sobre cualquier tecla
            if custom_form.active:
                result_form = custom_form.handle_event(event)
                if result_form:
                    key, data = result_form
                    current_microbe = key
                continue

            if event.key == pygame.K_SPACE:
                paused = not paused

            elif event.key == pygame.K_r:
                particles.clear()
                particles = [
                    Particle(
                        random.randint(80, current_w - 80),
                        random.randint(80, current_h - 150),
                        is_bacteria=True,
                        microbe_key=current_microbe
                    )
                    for _ in range(INITIAL_PARTICLES)
                ]
                simulated_days = 0
                population_graph.history.clear()

            elif event.key == pygame.K_b:
                # Antibiótico
                for p in particles:
                    if p.is_bacteria:
                        p.state = "stressed"
                        p.stress_timer = 120
                gesture_text = "¡Antibiótico aplicado!"

            elif event.key == pygame.K_f:
                # Reponer nutrientes
                nutrients = MAX_NUTRIENTS
                nutrient_slider.update(nutrients)
                gesture_text = "¡Nutrientes repuestos al 100%!"

            elif event.key == pygame.K_t:
                show_trails = not show_trails

            elif event.key == pygame.K_c:
                enable_collisions = not enable_collisions

            elif event.key == pygame.K_n:
                custom_form.toggle()

            elif event.key == pygame.K_RIGHT:
                keys = get_all_microbes()
                idx = keys.index(current_microbe)
                current_microbe = keys[(idx + 1) % len(keys)]
                gesture_text = f"Microbio: {current_microbe}"

            elif event.key == pygame.K_LEFT:
                keys = get_all_microbes()
                idx = keys.index(current_microbe)
                current_microbe = keys[(idx - 1) % len(keys)]
                gesture_text = f"Microbio: {current_microbe}"

    # ------------------- Procesar gestos -------------------
    frame, result = gesture_controller.get_frame()
    if frame is None:
        break

    hand_forces    = []
    vortex_centers = []

    if result and not custom_form.active:
        frame = gesture_controller.draw_landmarks(frame, result)
        hand_forces, vortex_centers, temp, humidity, ph, light, current_microbe, gesture_text = \
            gesture_controller.process_gestures(
                result, current_w, current_h,
                temp, humidity, ph, light, current_microbe
            )

    # Sincronizar sliders con valores de gestos
    temp_slider.update(temp)
    hum_slider.update(humidity)
    ph_slider.update(ph)
    light_slider.update(light)
    # nutrient_slider NO se sincroniza desde gestos, solo desde consumo real y tecla F

    # ------------------- Actualizar simulación -------------------
    if not paused:

        for p in particles:
            total_force = np.zeros(2)

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

            for v_pos in vortex_centers:
                direction = v_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 10:
                    perpendicular = np.array([-direction[1], direction[0]])
                    p.vel += perpendicular * (780 / (dist + 30)) * dt

            p.update(total_force, dt)

            if p.pos[0] < 0 or p.pos[0] > current_w:
                p.vel[0] *= -0.82
                p.pos[0] = np.clip(p.pos[0], 5, current_w - 5)
            if p.pos[1] < 0 or p.pos[1] > current_h:
                p.vel[1] *= -0.82
                p.pos[1] = np.clip(p.pos[1], 5, current_h - 5)

        # FIX: una sola llamada con firma correcta de 5 factores
        nutrients = update_bacteria_growth(
            particles, temp, humidity, ph, light, nutrients,
            current_microbe, MAX_PARTICLES
        )
        # Reflejar el consumo real en el slider
        nutrient_slider.update(nutrients)

        if enable_collisions and len(particles) < 950:
            handle_collisions(particles)

        population_graph.update(len(particles))

    # ------------------- +1 Día con gesto -------------------
    current_time = pygame.time.get_ticks()
    if "¡+1 Día" in gesture_text and current_time - last_day_time > DAY_COOLDOWN:
        simulated_days = min(simulated_days + 1, 30)
        last_day_time = current_time
        if particles:
            create_explosion(particles, current_w // 2, current_h // 2, count=25, intensity=0.7)

    # ========================
    # DIBUJAR
    # ========================
    screen.fill(BLACK)

    # Trails
    if show_trails and len(particles) < 900:
        for p in particles:
            speed = np.linalg.norm(p.vel)
            if speed > 15:
                alpha = min(40, int(25 * (speed / 200)))
                trail_surf = pygame.Surface((6, 6), pygame.SRCALPHA)
                pygame.draw.circle(trail_surf, (*p.color[:3], alpha), (3, 3), 3)
                screen.blit(trail_surf, (int(p.pos[0]) - 3, int(p.pos[1]) - 3))

    for p in particles:
        p.draw(screen)

    draw_ui(screen, temp, humidity, ph, light, nutrients, current_microbe, simulated_days,
            particles, population_graph,
            temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider)

    # Texto de gesto grande
    if any(w in gesture_text for w in ["Temp", "Humedad", "pH", "Luz", "Microbio", "Antibiótico", "Nutrientes"]):
        gesture_font = pygame.font.SysFont("Arial", 28)
        gesture_surf = gesture_font.render(gesture_text, True, PURPLE)
        screen.blit(gesture_surf, (current_w // 2 - gesture_surf.get_width() // 2, 25))

    custom_form.draw(screen)

    # if custom_form.success_msg:
    #     success_surf = big_font.render(custom_form.success_msg, True, GREEN)
    #     screen.blit(success_surf, (current_w // 2 - success_surf.get_width() // 2, current_h // 2))
    #     # Iniciar timer la primera vez
    #     if custom_form.success_timer == 0:
    #         custom_form.success_timer = pygame.time.get_ticks()
    #     # Borrar después de 3 segundos
    #     elif pygame.time.get_ticks() - custom_form.success_timer > 3000:
    #         custom_form.success_msg = ""
    #         custom_form.success_timer = 0

    pygame.display.flip()

    if frame is not None:
        cv2.putText(frame, gesture_text, (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 255, 255), 3)
        cv2.imshow("Camara - GestBact AI", frame)

    if cv2.waitKey(1) == 27:
        running = False

# ========================
# FINALIZACIÓN
# ========================
gesture_controller.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()