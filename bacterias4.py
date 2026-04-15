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
pygame.display.set_caption("Partículas con Dos Manos + Colisiones")
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
# CLASE PARTÍCULA (mejorada para colisiones)
# ========================
class Particle:
    def __init__(self, x, y, is_bacteria=False):
        self.pos = np.array([float(x), float(y)])
        self.vel = np.array([random.uniform(-100, 100), random.uniform(-100, 100)])
        self.state = "healthy" if is_bacteria else "normal"
        self.age = 0
        self.color = GREEN if is_bacteria else CYAN
        self.size = 5.0
        self.collision_timer = 0   # Para efecto visual al chocar

    def update(self, force, dt, damping):
        self.vel += force * dt
        self.vel *= damping
        self.pos += self.vel * dt
        self.age += 1
        if self.collision_timer > 0:
            self.collision_timer -= 1

    def draw(self, surface):
        draw_color = RED if self.state == "infected" else self.color
        if self.collision_timer > 0:
            draw_color = YELLOW  # Brilla al chocar
        pygame.draw.circle(surface, draw_color, (int(self.pos[0]), int(self.pos[1])), int(self.size))

# ========================
# VARIABLES
# ========================
particles = [Particle(random.randint(80, WIDTH-80), random.randint(80, HEIGHT-150)) for _ in range(450)]

damping = 0.96
max_particles = 1600
energy_history = []
show_trails = False
paused = False
is_bacteria_mode = False
enable_collisions = True   # ← Nueva variable

# ========================
# MEDIAPIPE
# ========================
mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(static_image_mode=False, max_num_hands=2,
                                min_detection_confidence=0.75, min_tracking_confidence=0.75)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

gesture_text = "Esperando manos..."
running = True
dt = 0.016

def handle_collisions():
    """Maneja colisiones elásticas entre partículas"""
    for i in range(len(particles)):
        for j in range(i + 1, len(particles)):
            p1 = particles[i]
            p2 = particles[j]
            
            dx = p2.pos[0] - p1.pos[0]
            dy = p2.pos[1] - p1.pos[1]
            dist_sq = dx*dx + dy*dy
            min_dist = p1.size + p2.size
            
            if dist_sq < min_dist * min_dist and dist_sq > 0.001:
                dist = math.sqrt(dist_sq)
                # Vector normal
                nx, ny = dx / dist, dy / dist
                
                # Velocidades relativas
                rvx = p2.vel[0] - p1.vel[0]
                rvy = p2.vel[1] - p1.vel[1]
                
                # Velocidad relativa en la dirección de la colisión
                vel_along_normal = rvx * nx + rvy * ny
                
                # Si se están alejando, no colisionar
                if vel_along_normal > 0:
                    continue
                
                # Coeficiente de restitución (elasticidad)
                e = 0.85
                
                # Impulso
                impulse = -(1 + e) * vel_along_normal / 2
                
                # Aplicar impulso
                p1.vel[0] -= impulse * nx
                p1.vel[1] -= impulse * ny
                p2.vel[0] += impulse * nx
                p2.vel[1] += impulse * ny
                
                # Separar partículas para evitar que se peguen
                overlap = min_dist - dist
                p1.pos[0] -= overlap * nx * 0.5
                p1.pos[1] -= overlap * ny * 0.5
                p2.pos[0] += overlap * nx * 0.5
                p2.pos[1] += overlap * ny * 0.5
                
                # Efecto visual
                p1.collision_timer = 8
                p2.collision_timer = 8

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
            if event.key == pygame.K_SPACE:
                paused = not paused
            elif event.key == pygame.K_r:
                particles.clear()
                particles = [Particle(random.randint(80, WIDTH-80), random.randint(80, HEIGHT-150)) for _ in range(450)]
                energy_history.clear()
            elif event.key == pygame.K_t:
                show_trails = not show_trails
            elif event.key == pygame.K_c:           # ← Nueva tecla
                enable_collisions = not enable_collisions

    current_w, current_h = screen.get_size()

    # ========================
    # GESTOS CON DOS MANOS
    # ========================
    ret, frame = cap.read()
    if not ret:
        break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands_detector.process(rgb)

    hand_forces = []
    gesture_text = "Sin manos"

    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            palm = hand_landmarks.landmark[0]
            hand_x = int(palm.x * current_w)
            hand_y = int(palm.y * current_h)
            hand_pos = np.array([hand_x, hand_y], dtype=float)

            dedos = sum(1 for i in [8,12,16,20] if hand_landmarks.landmark[i].y < hand_landmarks.landmark[i-2].y)
            thumb_up = hand_landmarks.landmark[4].y < hand_landmarks.landmark[2].y - 0.05
            fist = dedos <= 1 and not thumb_up
            dist_thumb_index = abs(hand_landmarks.landmark[4].x - hand_landmarks.landmark[8].x)

            is_attract = not fist

            hand_forces.append((hand_pos, is_attract))

            if dedos == 1 and len(particles) < max_particles:
                particles.append(Particle(hand_x, hand_y, is_bacteria_mode))
                gesture_text = "Creando partículas"
            elif thumb_up:
                for _ in range(25):
                    if len(particles) < max_particles:
                        particles.append(Particle(random.randint(50, current_w-50), random.randint(50, current_h-150), is_bacteria_mode))
                gesture_text = "Añadiendo partículas"
            elif dedos == 3:
                is_bacteria_mode = not is_bacteria_mode
                gesture_text = f"Modo Bacterias {'ON' if is_bacteria_mode else 'OFF'}"

    # ========================
    # ACTUALIZAR PARTÍCULAS
    # ========================
    if not paused:
        total_ke = 0.0

        for p in particles[:]:
            total_force = np.zeros(2)

            for hand_pos, is_attract in hand_forces:
                direction = hand_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 10:
                    direction /= dist
                    force = direction * (14000 / (dist * dist + 50))
                    if not is_attract:
                        force = -force
                    total_force += force

            p.update(total_force, dt, damping)

            # Rebote bordes
            if p.pos[0] < 0 or p.pos[0] > current_w:
                p.vel[0] *= -0.82
                p.pos[0] = np.clip(p.pos[0], 0, current_w)
            if p.pos[1] < 0 or p.pos[1] > current_h:
                p.vel[1] *= -0.82
                p.pos[1] = np.clip(p.pos[1], 0, current_h)

            # Modo bacterias
            if is_bacteria_mode:
                if p.state == "healthy" and random.random() < 0.018 and len(particles) < max_particles:
                    particles.append(Particle(p.pos[0] + random.uniform(-20,20), p.pos[1] + random.uniform(-20,20), True))
                if p.state != "infected" and random.random() < 0.008:
                    p.state = "infected"
                if p.state == "infected" and p.age > 200 and random.random() < 0.03:
                    particles.remove(p)
                    continue

            total_ke += 0.5 * np.dot(p.vel, p.vel)

        energy_history.append(total_ke)
        if len(energy_history) > 400:
            energy_history.pop(0)

        # COLISIONES
        if enable_collisions and len(particles) < 800:   # Evitar lag con muchas partículas
            handle_collisions()

    # ========================
    # DIBUJAR
    # ========================
    screen.fill(BLACK)

    if show_trails:
        for p in particles:
            pygame.draw.circle(screen, (*p.color[:3], 30), (int(p.pos[0]), int(p.pos[1])), 2)

    for p in particles:
        p.draw(screen)

    # Mini-gráfica
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

    # Información
    screen.blit(big_font.render("PARTÍCULAS + COLISIONES + DOS MANOS", True, WHITE), (current_w//2 - 320, 15))
    
    screen.blit(font.render(f"Partículas: {len(particles)}", True, WHITE), (25, 80))
    screen.blit(font.render(f"Colisiones: {'ON' if enable_collisions else 'OFF'} (tecla C)", True, YELLOW), (25, 115))
    screen.blit(font.render(f"Energía: {energy_history[-1]:.0f}" if energy_history else "Energía: 0", True, YELLOW), (25, 150))
    screen.blit(font.render(f"Modo: {'Bacterias' if is_bacteria_mode else 'Física'}", True, GREEN if is_bacteria_mode else CYAN), (25, 185))
    screen.blit(font.render(f"Gestos: {gesture_text}", True, PURPLE), (25, 220))

    if paused:
        screen.blit(big_font.render("PAUSADO - ESPACIO", True, RED), (current_w//2 - 180, current_h//2))

    pygame.display.flip()
    clock.tick(60)

    cv2.putText(frame, gesture_text, (15, 70), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 255), 3)
    cv2.imshow("Camara - Dos Manos + Colisiones", frame)

    if cv2.waitKey(1) == 27:
        running = False

cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()