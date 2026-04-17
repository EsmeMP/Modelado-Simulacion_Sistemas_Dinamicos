# Archivo principal (solo inicia el juego y el loop)

# ========================
# MAIN.PY - GestBact AI - Simulador de Bacterias con Gestos
# ========================

import pygame
import sys
import numpy as np
import random
import cv2
from collections import deque

# Importamos nuestros módulos
from config import *
from microbes import get_microbe_data, get_all_microbes
from simulation import Particle, create_explosion, handle_collisions, update_bacteria_growth
from gestures import GestureController


# ========================
# inicializacion
# ========================
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("GestBact AI - Simulador de Bacterias y Virus con Gestos")
clock = pygame.time.Clock()

# variables de simulacion
particles = [Particle(random.randint(80, WIDTH-80), 
                     random.randint(80, HEIGHT-150)) 
             for _ in range(INITIAL_PARTICLES)]

temp = 25.0
humidity = 50.0
current_microbe = "E. coli"
simulated_days = 0
is_bacteria_mode = False
paused = False
show_trails = True
enable_collisions = True

# historia para grafica
population_history = deque(maxlen=400)
energy_history = deque(maxlen=400)

# controlador de gestos
gesture_controller = GestureController()

running = True
gesture_text = "Esperando manos..."

print("GestBact AI iniciado - Usa tus manos para controlar la simulación!")

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
                population_history.clear()
            if event.key == pygame.K_t:
                show_trails = not show_trails
            if event.key == pygame.K_c:
                enable_collisions = not enable_collisions
            if event.key == pygame.K_b:
                is_bacteria_mode = not is_bacteria_mode

    # ------------------- Captura de gestos -------------------
    frame, result = gesture_controller.get_frame()
    if frame is None:
        break

    hand_forces = []
    vortex_centers = []

    if result:
        frame = gesture_controller.draw_landmarks(frame, result)
        
        hand_forces, vortex_centers, temp, humidity, current_microbe, gesture_text = \
            gesture_controller.process_gestures(result, current_w, current_h, temp, humidity, current_microbe)

    # ------------------- Actualizar simulación -------------------
    if not paused:
        total_ke = 0.0

        for p in particles[:]:
            total_force = np.zeros(2)

            # fuerza de las manos
            for hand_pos, is_attract, strength in hand_forces:
                direction = hand_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 15:
                    direction /= dist
                    force_mag = (12000 + strength * 18000) / (dist**2 + 80)
                    force = direction * force_mag
                    if not is_attract:
                        force = -force
                    total_force += force
                    p.glow = max(p.glow, 0.85)

            # vortices
            for v_pos in vortex_centers:
                direction = v_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 10:
                    perpendicular = np.array([-direction[1], direction[0]])
                    p.vel += perpendicular * (750 / (dist + 35))

            p.update(total_force, dt)

            # rebote en bordes
            if p.pos[0] < 0 or p.pos[0] > current_w:
                p.vel[0] *= -0.82
                p.pos[0] = np.clip(p.pos[0], 5, current_w - 5)
            if p.pos[1] < 0 or p.pos[1] > current_h:
                p.vel[1] *= -0.82
                p.pos[1] = np.clip(p.pos[1], 5, current_h - 5)

            total_ke += 0.5 * np.dot(p.vel, p.vel)

        # actualizar crecimiento bacteriano
        if is_bacteria_mode:
            update_bacteria_growth(particles, temp, humidity, current_microbe, MAX_PARTICLES)

        # colisiones
        if enable_collisions and len(particles) < 950:
            handle_collisions(particles)

        # guarda datos para grafica
        population_history.append(len(particles))
        energy_history.append(total_ke)

    # ------------------- Dibujar -------------------
    screen.fill(BLACK)

    # Trails
    if show_trails:
        for p in particles:
            alpha = min(45, int(30 * (np.linalg.norm(p.vel) / 220)))
            trail_color = (*p.color[:3], alpha)
            pygame.draw.circle(screen, trail_color, (int(p.pos[0]), int(p.pos[1])), 4)

    # Dibujar particulas
    for p in particles:
        p.draw(screen)

    # informacion en pantalla
    microbe_data = get_microbe_data(current_microbe)
    microbe_name = microbe_data["name"] if microbe_data else current_microbe

    texts = [
        ("GestBact AI - Simulador de Microorganismos", big_font, WHITE, (current_w//2 - 280, 15)),
        (f"Gestos: {gesture_text}", font, PURPLE, (INFO_X, INFO_Y_START)),
        (f"Microorganismo: {microbe_name}", font, microbe_data["color"] if microbe_data else GREEN, (INFO_X, INFO_Y_START + LINE_SPACING)),
        (f"Temperatura: {temp:.1f}°C", font, YELLOW, (INFO_X, INFO_Y_START + LINE_SPACING*2)),
        (f"Humedad: {humidity:.0f}%", font, CYAN, (INFO_X, INFO_Y_START + LINE_SPACING*3)),
        (f"Días simulados: {simulated_days}", font, ORANGE, (INFO_X, INFO_Y_START + LINE_SPACING*4)),
        (f"Partículas: {len(particles)}", font, WHITE, (INFO_X, INFO_Y_START + LINE_SPACING*5)),
        (f"Modo: {'BACTERIAS ACTIVAS' if is_bacteria_mode else 'Física normal'}", 
         font, GREEN if is_bacteria_mode else CYAN, (INFO_X, INFO_Y_START + LINE_SPACING*6)),
    ]

    for text, fnt, color, pos in texts:
        screen.blit(fnt.render(text, True, color), pos)

    # Instrucciones rapidas
    controls = [
        "Controles:",
        "• 1 dedo (izq) = Temperatura   |   1 dedo (der) = Humedad",
        "• Mano abierta + Pulgar = Cambiar microbio",
        "• Pulgar arriba = +1 Día",
        "• 3 dedos = Activar/Desactivar bacterias",
        "• Espacio = Pausar   |   R = Reiniciar",
    ]

    for i, line in enumerate(controls):
        screen.blit(font.render(line, True, LIGHT_GRAY), (INFO_X, current_h - 140 + i*22))

    pygame.display.flip()

    # Mostrar camara (opcional)
    if frame is not None:
        cv2.putText(frame, gesture_text, (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 3)
        cv2.imshow("Camara - GestBact AI", frame)

    if cv2.waitKey(1) == 27:  # ESC para salir
        running = False

# ========================
# finalizacion
# ========================
gesture_controller.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()