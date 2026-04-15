# BACTERIAS CONTROLADAS POR GESTOS - SIMULACIÓN EN PYGAME CON MEDIAPIPE

import pygame
import sys
import math
import random
import cv2
import mediapipe as mp
import numpy as np

# ========================
# CONFIGURACIÓN PYGAME (ventana redimensionable)
# ========================
pygame.init()
WIDTH, HEIGHT = 1200, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Partículas / Bacterias - Control por Gestos")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 22)
big_font = pygame.font.SysFont("Arial", 30)

# Colores
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
RED = (255, 50, 50)
GREEN = (50, 255, 50)
YELLOW = (255, 255, 0)

# ========================
# CLASE PARTÍCULA
# ========================
class Particle:
    def __init__(self, x, y):
        self.pos = np.array([float(x), float(y)])
        self.vel = np.array([random.uniform(-80, 80), random.uniform(-80, 80)])
        self.color = CYAN
        self.size = 4

    def update(self, force, dt, damping=0.98):
        self.vel += force * dt
        self.vel *= damping
        self.pos += self.vel * dt

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.pos[0]), int(self.pos[1])), self.size)

# ========================
# VARIABLES
# ========================
particles = [Particle(random.randint(100, WIDTH-100), random.randint(100, HEIGHT-100)) for _ in range(400)]

hand_force_strength = 8000.0
damping = 0.97
is_attract = True
is_bacteria_mode = False

# ========================
# MEDIAPIPE
# ========================
mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(static_image_mode=False, max_num_hands=1,
                                min_detection_confidence=0.75, min_tracking_confidence=0.75)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

gesture_text = "Esperando mano..."
running = True
dt = 0.016

while running:
    # Eventos Pygame (redimensionar)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

    current_w, current_h = screen.get_size()

    # ========================
    # PROCESAR CÁMARA Y GESTOS
    # ========================
    ret, frame = cap.read()
    if not ret:
        break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands_detector.process(rgb)

    hand_pos = None
    gesture_text = "Sin mano"
    color_gesture = WHITE

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            # Posición de la palma (en coordenadas de la cámara)
            palm = hand_landmarks.landmark[0]
            hand_x = int(palm.x * current_w)
            hand_y = int(palm.y * current_h)
            hand_pos = np.array([hand_x, hand_y], dtype=float)

            # Conteo de dedos
            dedos = 0
            if hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y: dedos += 1
            if hand_landmarks.landmark[12].y < hand_landmarks.landmark[10].y: dedos += 1
            if hand_landmarks.landmark[16].y < hand_landmarks.landmark[14].y: dedos += 1
            if hand_landmarks.landmark[20].y < hand_landmarks.landmark[18].y: dedos += 1

            # Thumb Up
            thumb_up = hand_landmarks.landmark[4].y < hand_landmarks.landmark[2].y - 0.05
            # Fist
            fist = dedos <= 1 and not thumb_up

            # Distancia pulgar-índice (control de fuerza)
            dist_thumb_index = abs(hand_landmarks.landmark[4].x - hand_landmarks.landmark[8].x)

            # ========================
            # GESTOS
            # ========================
            if dedos >= 4:                              # Mano abierta
                is_attract = True
                gesture_text = "ATRAER (Mano abierta)"
                color_gesture = GREEN

            elif fist:                                  # Puño
                is_attract = False
                gesture_text = "REPELER (Puño)"
                color_gesture = RED

            elif dedos == 1:                            # Solo índice → Crear partículas
                particles.append(Particle(hand_x, hand_y))
                gesture_text = "Crear partícula"
                color_gesture = YELLOW

            elif dedos == 2:                            # Índice + medio → Más velocidad
                for p in particles:
                    p.vel *= 1.08
                gesture_text = "Acelerar partículas"

            elif thumb_up:                              # Pulgar arriba → Más partículas
                for _ in range(15):
                    particles.append(Particle(random.randint(0, current_w), random.randint(0, current_h)))
                gesture_text = "Más partículas (Thumb Up)"

            elif dedos == 3:                            # 3 dedos → Modo bacterias
                is_bacteria_mode = not is_bacteria_mode
                gesture_text = "Modo Bacterias ON/OFF"
                color_gesture = (255, 180, 0)

            else:
                hand_force_strength = 8000 + dist_thumb_index * 25000

    # ========================
    # ACTUALIZAR PARTÍCULAS
    # ========================
    for p in particles[:]:  # copia para poder borrar
        force = np.array([0.0, 0.0])

        if hand_pos is not None:
            direction = hand_pos - p.pos
            dist = np.linalg.norm(direction)
            if dist > 5:
                direction /= dist
                force = direction * (hand_force_strength / (dist * dist + 1))
                if not is_attract:
                    force = -force

        p.update(force, dt, damping)

        # Mantener partículas dentro de la ventana
        if p.pos[0] < 0 or p.pos[0] > current_w:
            p.vel[0] *= -0.8
            p.pos[0] = np.clip(p.pos[0], 0, current_w)
        if p.pos[1] < 0 or p.pos[1] > current_h:
            p.vel[1] *= -0.8
            p.pos[1] = np.clip(p.pos[1], 0, current_h)

        # Modo bacterias (cambio de color y pequeño crecimiento)
        if is_bacteria_mode:
            p.color = GREEN if random.random() < 0.98 else RED
            if random.random() < 0.02 and len(particles) < 800:
                particles.append(Particle(p.pos[0], p.pos[1]))

    # ========================
    # DIBUJAR EN PYGAME
    # ========================
    screen.fill(BLACK)

    for p in particles:
        p.draw(screen)

    # Info en pantalla
    title = big_font.render("Simulación de Partículas / Bacterias - Gestos", True, WHITE)
    info = font.render(gesture_text, True, color_gesture)
    count = font.render(f"Partículas: {len(particles)}", True, WHITE)
    
    screen.blit(title, (current_w//2 - 280, 15))
    screen.blit(info, (20, 20))
    screen.blit(count, (20, 60))

    pygame.display.flip()
    clock.tick(60)

    # Ventana de cámara
    cv2.putText(frame, gesture_text, (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 255, 255), 3)
    cv2.imshow("Camara - Gestos", frame)

    if cv2.waitKey(1) == 27:  # ESC
        running = False

cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()