import pygame
import sys
import math
import random
import cv2
import mediapipe as mp
import numpy as np

# ========================
# CONFIGURACIÓN PYGAME
# ========================
pygame.init()
WIDTH, HEIGHT = 1280, 820
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Partículas con DOS MANOS - Control Gestual Avanzado")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 22)
big_font = pygame.font.SysFont("Arial", 32)
small_font = pygame.font.SysFont("Arial", 18)

# Colores
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
RED = (255, 60, 60)
GREEN = (60, 255, 60)
YELLOW = (255, 255, 80)
PURPLE = (180, 80, 255)

# ========================
# CLASE PARTÍCULA
# ========================
class Particle:
    def __init__(self, x, y, is_bacteria=False):
        self.pos = np.array([float(x), float(y)])
        self.vel = np.array([random.uniform(-100, 100), random.uniform(-100, 100)])
        self.state = "healthy" if is_bacteria else "normal"
        self.age = 0
        self.color = GREEN if is_bacteria else CYAN
        self.size = 4.5

    def update(self, force, dt, damping=0.965):
        self.vel += force * dt
        self.vel *= damping
        self.pos += self.vel * dt
        self.age += 1

    def draw(self, surface):
        color = RED if self.state == "infected" else self.color
        pygame.draw.circle(surface, color, (int(self.pos[0]), int(self.pos[1])), self.size)

# ========================
# VARIABLES
# ========================
particles = [Particle(random.randint(80, WIDTH-80), random.randint(80, HEIGHT-150)) for _ in range(500)]

damping = 0.965
max_particles = 1600
energy_history = []
show_trails = False
paused = False
is_bacteria_mode = False

# ========================
# MEDIAPIPE - Soporte para DOS MANOS
# ========================
mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(static_image_mode=False, 
                                max_num_hands=2,           # ← Importante: 2 manos
                                min_detection_confidence=0.75, 
                                min_tracking_confidence=0.75)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

gesture_text = "Esperando manos..."
running = True
dt = 0.016

while running:
    # Eventos Pygame
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                paused = not paused
            elif event.key == pygame.K_r:
                particles.clear()
                particles = [Particle(random.randint(80, WIDTH-80), random.randint(80, HEIGHT-150)) for _ in range(500)]
                energy_history.clear()
            elif event.key == pygame.K_t:
                show_trails = not show_trails

    current_w, current_h = screen.get_size()

    # ========================
    # PROCESAR CÁMARA Y DOS MANOS
    # ========================
    ret, frame = cap.read()
    if not ret:
        break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands_detector.process(rgb)

    hand_forces = []        # Lista de (posición, es_atractor)
    gesture_text = "Sin manos"

    if result.multi_hand_landmarks:
        for idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # Posición de la palma
            palm = hand_landmarks.landmark[0]
            hand_x = int(palm.x * current_w)
            hand_y = int(palm.y * current_h)
            hand_pos = np.array([hand_x, hand_y], dtype=float)

            # Conteo de dedos
            dedos = sum(1 for i in [8,12,16,20] if hand_landmarks.landmark[i].y < hand_landmarks.landmark[i-2].y)
            thumb_up = hand_landmarks.landmark[4].y < hand_landmarks.landmark[2].y - 0.05
            fist = dedos <= 1 and not thumb_up
            dist_thumb_index = abs(hand_landmarks.landmark[4].x - hand_landmarks.landmark[8].x)

            # Determinar si atrae o repele
            is_attract = not fist

            hand_forces.append((hand_pos, is_attract))

            # Gestos globales (se activan si cualquier mano hace el gesto)
            if dedos == 1:                                 # Crear partículas
                if len(particles) < max_particles:
                    particles.append(Particle(hand_x, hand_y, is_bacteria_mode))
                gesture_text = "Creando partículas"

            elif thumb_up:                                 # Añadir muchas
                for _ in range(30):
                    if len(particles) < max_particles:
                        particles.append(Particle(random.randint(50, current_w-50), 
                                                random.randint(50, current_h-150), is_bacteria_mode))
                gesture_text = "Añadiendo partículas (Thumb Up)"

            elif dedos == 3:                               # Toggle bacterias
                is_bacteria_mode = not is_bacteria_mode
                gesture_text = f"Modo Bacterias {'ON' if is_bacteria_mode else 'OFF'}"

    else:
        gesture_text = "Sin manos detectadas"

    # ========================
    # ACTUALIZAR PARTÍCULAS
    # ========================
    if not paused:
        total_ke = 0.0

        for p in particles[:]:
            total_force = np.zeros(2)

            # Aplicar fuerza de cada mano
            for hand_pos, is_attract in hand_forces:
                direction = hand_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 10:
                    direction /= dist
                    force_magnitude = 14000 / (dist * dist + 50)
                    force = direction * force_magnitude
                    if not is_attract:
                        force = -force
                    total_force += force

            p.update(total_force, dt, damping)

            # Rebote en bordes
            if p.pos[0] < 0 or p.pos[0] > current_w:
                p.vel[0] *= -0.82
                p.pos[0] = np.clip(p.pos[0], 0, current_w)
            if p.pos[1] < 0 or p.pos[1] > current_h:
                p.vel[1] *= -0.82
                p.pos[1] = np.clip(p.pos[1], 0, current_h)

            # === MODO BACTERIAS ===
            if is_bacteria_mode:
                if p.state == "healthy":
                    if random.random() < 0.022 and len(particles) < max_particles:
                        particles.append(Particle(p.pos[0]+random.uniform(-15,15), 
                                                p.pos[1]+random.uniform(-15,15), True))
                else:
                    if p.age > 150 and random.random() < 0.035:
                        particles.remove(p)
                        continue

                if random.random() < 0.009:
                    p.state = "infected"

            # Energía cinética
            total_ke += 0.5 * np.dot(p.vel, p.vel)

        energy_history.append(total_ke)
        if len(energy_history) > 400:
            energy_history.pop(0)

    # ========================
    # DIBUJAR
    # ========================
    screen.fill(BLACK)

    if show_trails:
        for p in particles:
            pygame.draw.circle(screen, (*p.color[:3], 35), (int(p.pos[0]), int(p.pos[1])), 2)

    for p in particles:
        p.draw(screen)

    # Mini-gráfica de energía
    gx, gy = 25, current_h - 170
    gw, gh = 420, 140
    pygame.draw.rect(screen, (70,70,70), (gx, gy, gw, gh), 2)
    if len(energy_history) > 1:
        max_e = max(energy_history) * 1.1
        for i in range(1, len(energy_history)):
            x1 = gx + (i-1) * gw / len(energy_history)
            y1 = gy + gh - (energy_history[i-1] / max_e * gh)
            x2 = gx + i * gw / len(energy_history)
            y2 = gy + gh - (energy_history[i] / max_e * gh)
            pygame.draw.line(screen, YELLOW, (x1, y1), (x2, y2), 3)

    # Panel de información
    screen.blit(big_font.render("PARTÍCULAS CON DOS MANOS", True, WHITE), (current_w//2 - 260, 15))
    
    screen.blit(font.render(f"Partículas: {len(particles)} / {max_particles}", True, WHITE), (25, 80))
    screen.blit(font.render(f"Energía cinética: {energy_history[-1]:.0f}" if energy_history else "Energía: 0", True, YELLOW), (25, 115))
    screen.blit(font.render(f"Modo: {'BACTERIAS' if is_bacteria_mode else 'FÍSICA'}", True, GREEN if is_bacteria_mode else CYAN), (25, 150))
    screen.blit(font.render(f"Gestos: {gesture_text}", True, PURPLE), (25, 185))

    if paused:
        screen.blit(big_font.render("PAUSADO - Presiona ESPACIO", True, RED), (current_w//2 - 220, current_h//2))

    # Instrucciones rápidas
    help_text = small_font.render("SPACE: Pausa | R: Reset | T: Trails", True, WHITE)
    screen.blit(help_text, (current_w - 380, 15))

    pygame.display.flip()
    clock.tick(60)

    # Mostrar cámara
    cv2.putText(frame, gesture_text, (15, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 255), 3)
    cv2.imshow("Camara - Dos Manos", frame)

    if cv2.waitKey(1) == 27:
        running = False

cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()