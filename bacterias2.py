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
WIDTH, HEIGHT = 1280, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Simulación de Partículas / Bacterias - Gestos + Estadísticas")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 22)
big_font = pygame.font.SysFont("Arial", 30)
small_font = pygame.font.SysFont("Arial", 18)

# Colores
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
RED = (255, 50, 50)
GREEN = (50, 255, 50)
YELLOW = (255, 255, 0)
GRAY = (100, 100, 100)

# ========================
# CLASE PARTÍCULA (mejorada)
# ========================
class Particle:
    def __init__(self, x, y, is_bacteria=False):
        self.pos = np.array([float(x), float(y)])
        self.vel = np.array([random.uniform(-120, 120), random.uniform(-120, 120)])
        self.state = "healthy" if is_bacteria else "normal"  # healthy / infected
        self.age = 0
        self.color = GREEN if is_bacteria and self.state == "healthy" else CYAN
        self.size = 4

    def update(self, force, dt, damping):
        self.vel += force * dt
        self.vel *= damping
        self.pos += self.vel * dt
        self.age += 1

    def draw(self, surface):
        color = RED if self.state == "infected" else self.color
        pygame.draw.circle(surface, color, (int(self.pos[0]), int(self.pos[1])), self.size)

# ========================
# VARIABLES DEL SISTEMA
# ========================
particles = [Particle(random.randint(50, WIDTH-50), random.randint(50, HEIGHT-50)) for _ in range(450)]

hand_force_strength = 12000.0
damping = 0.965
is_attract = True
is_bacteria_mode = False
show_trails = False
paused = False

# Estadísticas
energy_history = []          # para la mini-gráfica
max_particles = 1400

# ========================
# MEDIAPIPE
# ========================
mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(static_image_mode=False, max_num_hands=1,
                                min_detection_confidence=0.78, min_tracking_confidence=0.78)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

gesture_text = "Esperando mano..."
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
            if event.key == pygame.K_SPACE:          # Pausa
                paused = not paused
            elif event.key == pygame.K_r:            # Reset
                particles.clear()
                particles = [Particle(random.randint(50, WIDTH-50), random.randint(50, HEIGHT-50)) for _ in range(450)]
                energy_history.clear()
            elif event.key == pygame.K_t:            # Toggle trails
                show_trails = not show_trails

    current_w, current_h = screen.get_size()

    # ========================
    # GESTOS CON MEDIAPIPE
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

            palm = hand_landmarks.landmark[0]
            hand_x = int(palm.x * current_w)
            hand_y = int(palm.y * current_h)
            hand_pos = np.array([hand_x, hand_y], dtype=float)

            # Conteo dedos + gestos
            dedos = sum(1 for i in [8,12,16,20] if hand_landmarks.landmark[i].y < hand_landmarks.landmark[i-2].y)
            thumb_up = hand_landmarks.landmark[4].y < hand_landmarks.landmark[2].y - 0.05
            fist = dedos <= 1 and not thumb_up
            dist_thumb_index = abs(hand_landmarks.landmark[4].x - hand_landmarks.landmark[8].x)

            if dedos >= 4:                          # Mano abierta
                is_attract = True
                gesture_text = "ATRAER (Mano abierta)"
                color_gesture = GREEN
            elif fist:                              # Puño
                is_attract = False
                gesture_text = "REPELER (Puño)"
                color_gesture = RED
            elif dedos == 1:                        # Crear
                if len(particles) < max_particles:
                    particles.append(Particle(hand_x, hand_y, is_bacteria_mode))
                gesture_text = "Crear partícula"
            elif dedos == 2:                        # Acelerar
                for p in particles:
                    p.vel *= 1.12
                gesture_text = "Acelerar"
            elif thumb_up:                          # Más partículas
                for _ in range(25):
                    if len(particles) < max_particles:
                        particles.append(Particle(random.randint(0, current_w), random.randint(0, current_h), is_bacteria_mode))
                gesture_text = "Más partículas"
            elif dedos == 3:                        # Toggle bacterias
                is_bacteria_mode = not is_bacteria_mode
                gesture_text = "Modo Bacterias " + ("ON" if is_bacteria_mode else "OFF")
                color_gesture = YELLOW
            else:
                hand_force_strength = 8000 + dist_thumb_index * 30000

    # ========================
    # ACTUALIZAR PARTÍCULAS (solo si no está pausado)
    # ========================
    if not paused:
        total_ke = 0.0
        total_speed = 0.0

        for p in particles[:]:
            force = np.zeros(2)
            if hand_pos is not None:
                direction = hand_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 8:
                    direction /= dist
                    force = direction * (hand_force_strength / (dist**2 + 30))
                    if not is_attract:
                        force = -force

            p.update(force, dt, damping)

            # Rebote en bordes
            if p.pos[0] < 0 or p.pos[0] > current_w:
                p.vel[0] *= -0.85
                p.pos[0] = np.clip(p.pos[0], 0, current_w)
            if p.pos[1] < 0 or p.pos[1] > current_h:
                p.vel[1] *= -0.85
                p.pos[1] = np.clip(p.pos[1], 0, current_h)

            # Modo bacterias
            if is_bacteria_mode:
                p.age += 1
                if p.state == "healthy":
                    p.color = GREEN
                    if random.random() < 0.018 and len(particles) < max_particles:  # reproducción
                        particles.append(Particle(p.pos[0], p.pos[1], True))
                else:
                    p.color = RED
                    if p.age > 180 and random.random() < 0.04:  # muerte
                        particles.remove(p)
                        continue

                # Infección aleatoria
                if random.random() < 0.008:
                    p.state = "infected"

            # Estadísticas
            speed_sq = np.dot(p.vel, p.vel)
            total_ke += 0.5 * speed_sq
            total_speed += math.sqrt(speed_sq)

        # Guardar energía para la gráfica
        energy_history.append(total_ke)
        if len(energy_history) > 350:
            energy_history.pop(0)

        avg_speed = total_speed / len(particles) if particles else 0

    # ========================
    # DIBUJAR TODO
    # ========================
    screen.fill(BLACK)

    # Trails (opcional)
    if show_trails:
        for p in particles:
            pygame.draw.circle(screen, (*p.color[:3], 40), (int(p.pos[0]), int(p.pos[1])), 2)

    # Partículas
    for p in particles:
        p.draw(screen)

    # Mini-gráfica de energía (abajo izquierda)
    graph_x, graph_y = 20, current_h - 160
    graph_w, graph_h = 380, 130
    pygame.draw.rect(screen, GRAY, (graph_x, graph_y, graph_w, graph_h), 2)

    if len(energy_history) > 1:
        max_e = max(energy_history)
        if max_e > 0:
            for i in range(1, len(energy_history)):
                x1 = graph_x + (i-1) * (graph_w / len(energy_history))
                y1 = graph_y + graph_h - (energy_history[i-1] / max_e * graph_h)
                x2 = graph_x + i * (graph_w / len(energy_history))
                y2 = graph_y + graph_h - (energy_history[i] / max_e * graph_h)
                pygame.draw.line(screen, YELLOW, (x1, y1), (x2, y2), 2)

    # Panel de estadísticas
    stats_y = 15
    screen.blit(big_font.render("PARTÍCULAS + GESTOS", True, WHITE), (current_w//2 - 180, 10))
    
    screen.blit(font.render(f"Partículas: {len(particles)}", True, WHITE), (20, stats_y))
    screen.blit(font.render(f"Energía cinética: {energy_history[-1]:.1f}" if energy_history else "Energía: 0", True, YELLOW), (20, stats_y+35))
    screen.blit(font.render(f"Vel. promedio: {avg_speed:.1f} px/s", True, CYAN), (20, stats_y+70))
    screen.blit(font.render(f"FPS: {clock.get_fps():.1f}", True, WHITE), (20, stats_y+105))
    screen.blit(font.render(f"Modo: {'Bacterias' if is_bacteria_mode else 'Física'}", True, GREEN if is_bacteria_mode else CYAN), (20, stats_y+140))
    screen.blit(font.render(f"Gestos → {gesture_text}", True, color_gesture), (20, stats_y+175))

    if paused:
        pause_text = big_font.render("PAUSADO (SPACE para continuar)", True, RED)
        screen.blit(pause_text, (current_w//2 - 260, current_h//2 - 30))

    pygame.display.flip()
    clock.tick(60)

    # Ventana cámara
    cv2.putText(frame, gesture_text, (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 255, 255), 3)
    cv2.imshow("Camara - Gestos", frame)

    if cv2.waitKey(1) == 27:
        running = False

cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()