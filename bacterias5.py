import pygame
import sys
import math
import random
import cv2
import mediapipe as mp
import numpy as np
from collections import deque

pygame.init()
WIDTH, HEIGHT = 1280, 820
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Partículas - Gestos Avanzados + Efectos Visuales")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 22)
big_font = pygame.font.SysFont("Arial", 32)

# Colores
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
RED = (255, 70, 70)
GREEN = (70, 255, 70)
YELLOW = (255, 255, 100)
PURPLE = (200, 100, 255)
ORANGE = (255, 165, 0)

# ========================
# CLASE PARTÍCULA (mejorada con glow)
# ========================
class Particle:
    def __init__(self, x, y, is_bacteria=False):
        self.pos = np.array([float(x), float(y)])
        self.vel = np.array([random.uniform(-90, 90), random.uniform(-90, 90)])
        self.state = "healthy" if is_bacteria else "normal"
        self.age = 0
        self.color = GREEN if is_bacteria else CYAN
        self.size = 5.0
        self.collision_timer = 0
        self.glow = 0.0                    # Nuevo: intensidad de brillo

    def update(self, force, dt, damping=0.955):
        self.vel += force * dt
        self.vel *= damping
        self.pos += self.vel * dt
        self.age += 1
        if self.collision_timer > 0:
            self.collision_timer -= 1
        if self.glow > 0:
            self.glow *= 0.92

    def draw(self, surface):
        color = RED if self.state == "infected" else self.color
        if self.collision_timer > 0:
            color = YELLOW

        # Dibujar glow (círculo más grande y transparente)
        if self.glow > 0.1:
            glow_size = int(self.size * 2.2)
            glow_surf = pygame.Surface((glow_size*2, glow_size*2), pygame.SRCALPHA)
            pygame.draw.circle(glow_surf, (*color[:3], int(40 * self.glow)), (glow_size, glow_size), glow_size)
            surface.blit(glow_surf, (int(self.pos[0])-glow_size, int(self.pos[1])-glow_size))

        pygame.draw.circle(surface, color, (int(self.pos[0]), int(self.pos[1])), int(self.size))

# ========================
# VARIABLES
# ========================
particles = [Particle(random.randint(80, WIDTH-80), random.randint(80, HEIGHT-150)) for _ in range(480)]
damping = 0.955
max_particles = 1800
energy_history = []
show_trails = True
paused = False
is_bacteria_mode = False
enable_collisions = True
show_force_arrows = True

# Efectos especiales
explosion_particles = []   # Para efectos de explosión

mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(static_image_mode=False, max_num_hands=2,
                                min_detection_confidence=0.78, min_tracking_confidence=0.78)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

gesture_text = "Esperando manos..."
running = True
dt = 0.016

# ========================
# FUNCIONES AUXILIARES
# ========================
def create_explosion(x, y, count=35):
    for _ in range(count):
        p = Particle(x, y)
        p.vel = np.array([random.uniform(-300, 300), random.uniform(-300, 300)])
        p.glow = 1.0
        p.size = random.uniform(3, 7)
        explosion_particles.append(p)

def handle_collisions():
    for i in range(len(particles)):
        for j in range(i+1, len(particles)):
            p1, p2 = particles[i], particles[j]
            dx = p2.pos[0] - p1.pos[0]
            dy = p2.pos[1] - p1.pos[1]
            dist_sq = dx*dx + dy*dy
            if dist_sq < (p1.size + p2.size)**2 and dist_sq > 0.001:
                dist = math.sqrt(dist_sq)
                nx, ny = dx/dist, dy/dist
                rv = (p2.vel - p1.vel) @ np.array([nx, ny])
                if rv > 0: continue
                impulse = -1.7 * rv / 2
                p1.vel -= impulse * np.array([nx, ny])
                p2.vel += impulse * np.array([nx, ny])
                p1.collision_timer = p2.collision_timer = 6

# ========================
# BUCLE PRINCIPAL
# ========================
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE: paused = not paused
            if event.key == pygame.K_r: 
                particles.clear()
                particles = [Particle(random.randint(80, WIDTH-80), random.randint(80, HEIGHT-150)) for _ in range(480)]
                energy_history.clear()
            if event.key == pygame.K_t: show_trails = not show_trails
            if event.key == pygame.K_c: enable_collisions = not enable_collisions
            if event.key == pygame.K_f: show_force_arrows = not show_force_arrows

    current_w, current_h = screen.get_size()

    # ========================
    # DETECCIÓN DE GESTOS (DOS MANOS)
    # ========================
    ret, frame = cap.read()
    if not ret: break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands_detector.process(rgb)

    hand_forces = []
    gesture_text = "Sin manos"
    vortex_centers = []

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            palm = hand_landmarks.landmark[0]
            hx = int(palm.x * current_w)
            hy = int(palm.y * current_h)
            hand_pos = np.array([hx, hy], dtype=float)

            dedos = sum(1 for i in [8,12,16,20] if hand_landmarks.landmark[i].y < hand_landmarks.landmark[i-2].y)
            thumb_up = hand_landmarks.landmark[4].y < hand_landmarks.landmark[2].y - 0.05
            fist = dedos <= 1 and not thumb_up
            dist_thumb_index = abs(hand_landmarks.landmark[4].x - hand_landmarks.landmark[8].x)

            is_attract = not fist

            # === GESTOS MEJORADOS ===
            if dedos == 4:                                 # Mano casi abierta
                is_attract = True
                gesture_text = "Atracción + Glow"
            elif fist:                                     # Puño
                is_attract = False
                gesture_text = "Repulsión + Onda"
                create_explosion(hx, hy, 12)               # onda de repulsión
            elif dedos == 1:                               # Solo índice
                if len(particles) < max_particles:
                    particles.append(Particle(hx, hy))
                gesture_text = "Creando partículas"
            elif dedos == 2:                               # Victory → Vórtice
                vortex_centers.append(hand_pos)
                gesture_text = "¡VÓRTICE ACTIVADO!"
            elif thumb_up:                                 # Pulgar arriba → Explosión
                create_explosion(hx, hy, 45)
                gesture_text = "¡EXPLOSIÓN!"
            elif dedos == 3:                               # 3 dedos → Bacterias
                is_bacteria_mode = not is_bacteria_mode
                gesture_text = f"Bacterias {'ON' if is_bacteria_mode else 'OFF'}"

            hand_forces.append((hand_pos, is_attract, dist_thumb_index))

    # ========================
    # ACTUALIZAR PARTÍCULAS
    # ========================
    if not paused:
        total_ke = 0.0

        for p in particles[:]:
            total_force = np.zeros(2)

            # Fuerza de manos
            for hand_pos, is_attract, strength in hand_forces:
                direction = hand_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 15:
                    direction /= dist
                    force_mag = (12000 + strength*20000) / (dist**2 + 80)
                    force = direction * force_mag
                    if not is_attract:
                        force = -force
                    total_force += force
                    p.glow = max(p.glow, 0.8)   # Activar glow

            # Vórtice (remolino)
            for v_pos in vortex_centers:
                direction = v_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 10:
                    perpendicular = np.array([-direction[1], direction[0]])  # Vector perpendicular
                    p.vel += perpendicular * (800 / (dist + 30))

            p.update(total_force, dt, damping)

            # Rebote bordes + modo bacterias (mismo código anterior)
            if p.pos[0] < 0 or p.pos[0] > current_w:
                p.vel[0] *= -0.8
                p.pos[0] = np.clip(p.pos[0], 0, current_w)
            if p.pos[1] < 0 or p.pos[1] > current_h:
                p.vel[1] *= -0.8
                p.pos[1] = np.clip(p.pos[1], 0, current_h)

            if is_bacteria_mode and random.random() < 0.022 and len(particles) < max_particles:
                particles.append(Particle(p.pos[0] + random.uniform(-25,25), p.pos[1] + random.uniform(-25,25), True))

            total_ke += 0.5 * np.dot(p.vel, p.vel)

        energy_history.append(total_ke)
        if len(energy_history) > 400: energy_history.pop(0)

        if enable_collisions and len(particles) < 900:
            handle_collisions()

    # ========================
    # DIBUJAR
    # ========================
    screen.fill(BLACK)

    # Trails mejorados
    if show_trails:
        for p in particles:
            alpha = min(40, int(25 * (np.linalg.norm(p.vel)/200)))
            pygame.draw.circle(screen, (*p.color[:3], alpha), (int(p.pos[0]), int(p.pos[1])), 3)

    for p in particles:
        p.draw(screen)

    # Dibujar explosiones temporales
    for ep in explosion_particles[:]:
        ep.update(np.zeros(2), dt, 0.92)
        ep.draw(screen)
        if np.linalg.norm(ep.vel) < 20:
            explosion_particles.remove(ep)

    # Información
    screen.blit(big_font.render("SIMULACIÓN AVANZADA - Gestos + Efectos", True, WHITE), (current_w//2 - 300, 15))
    screen.blit(font.render(f"Gestos: {gesture_text}", True, PURPLE), (25, 80))
    screen.blit(font.render(f"Partículas: {len(particles)}", True, WHITE), (25, 120))
    screen.blit(font.render(f"Modo: {'Bacterias' if is_bacteria_mode else 'Física'}", True, GREEN if is_bacteria_mode else CYAN), (25, 160))

    pygame.display.flip()
    clock.tick(60)

    cv2.putText(frame, gesture_text, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)
    cv2.imshow("Camara", frame)

    if cv2.waitKey(1) == 27:
        running = False

cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()