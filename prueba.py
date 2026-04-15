import pygame
import sys
import math
import cv2
import mediapipe as mp
import numpy as np
from scipy.integrate import odeint

# ========================
# CONFIGURACIÓN PYGAME
# ========================
pygame.init()
WIDTH, HEIGHT = 1500, 1000
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Doble Péndulo Caótico - Control por Gestos")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 20)

# Colores
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
BLUE = (0, 100, 255)
GREEN = (0, 255, 0)

# ========================
# PARÁMETROS DEL DOBLE PÉNDULO
# ========================
L1 = 200.0      # Longitud primer brazo
L2 = 200.0      # Longitud segundo brazo
m1 = 10.0
m2 = 10.0
g = 9.81
damping = 0.0   # Amortiguamiento (fricción)

# Estado inicial (ángulos en radianes y velocidades angulares)
state = np.array([math.pi/2, math.pi/2, 0.0, 0.0])  # theta1, theta2, omega1, omega2

# ========================
# ECUACIONES DEL DOBLE PÉNDULO (derivadas)
# ========================
def derivs(state, t, L1, L2, m1, m2, g, damping):
    theta1, theta2, omega1, omega2 = state
    
    delta = theta2 - theta1
    den1 = (m1 + m2) * L1 - m2 * L1 * math.cos(delta)**2
    den2 = (L2 / L1) * den1
    
    dtheta1_dt = omega1
    dtheta2_dt = omega2
    
    # Aceleraciones (derivadas de las ecuaciones de Lagrange)
    domega1_dt = (m2 * L1 * omega1**2 * math.sin(delta) * math.cos(delta) +
                  m2 * g * math.sin(theta2) * math.cos(delta) +
                  m2 * L2 * omega2**2 * math.sin(delta) -
                  (m1 + m2) * g * math.sin(theta1)) / den1 - damping * omega1
    
    domega2_dt = (-m2 * L2 * omega2**2 * math.sin(delta) * math.cos(delta) +
                  (m1 + m2) * g * math.sin(theta1) * math.cos(delta) -
                  (m1 + m2) * L1 * omega1**2 * math.sin(delta) -
                  (m1 + m2) * g * math.sin(theta2)) / den2 - damping * omega2
    
    return [dtheta1_dt, dtheta2_dt, domega1_dt, domega2_dt]

# ========================
# MEDIAPIPE
# ========================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, 
                       min_detection_confidence=0.7, min_tracking_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

cap = cv2.VideoCapture(0)

# Variables para control por gesto
last_hand_x = WIDTH // 2
last_hand_y = HEIGHT // 2
trail = []  # Para dibujar trayectoria del segundo bob

running = True
dt = 0.015  # Paso de tiempo (ajusta si va muy rápido o lento)

while running:
    # ========================
    # PROCESAR CÁMARA Y GESTOS
    # ========================
    ret, frame = cap.read()
    if not ret:
        break
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)
    
    gesture = "Ningún gesto"
    hand_x_norm = 0.5
    hand_y_norm = 0.5
    
    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            
            # Obtener posición aproximada de la palma (landmark 0)
            palm = hand_landmarks.landmark[0]
            hand_x_norm = palm.x
            hand_y_norm = palm.y
            
            # Conteo de dedos para gestos
            dedos = 0
            if hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y: dedos += 1  # índice
            if hand_landmarks.landmark[12].y < hand_landmarks.landmark[10].y: dedos += 1 # medio
            if hand_landmarks.landmark[16].y < hand_landmarks.landmark[14].y: dedos += 1 # anular
            if hand_landmarks.landmark[20].y < hand_landmarks.landmark[18].y: dedos += 1 # meñique
            
            # ========================
            # GESTOS INTERACTIVOS
            # ========================
            if dedos >= 4:                     # Mano casi abierta → Reset
                state = np.array([math.pi/2, math.pi/2, 0.0, 0.0])
                trail.clear()
                gesture = "RESET"
            
            elif dedos == 1:                   # Solo índice → Empujar primer péndulo
                # Mapear posición de mano a ángulo
                target_theta1 = (hand_x_norm - 0.5) * 4.0  # rango amplio
                state[2] += (target_theta1 - state[0]) * 0.8  # aplicar velocidad
                gesture = "Empujar P1"
            
            elif dedos == 2:                   # Índice + medio → Empujar segundo péndulo
                target_theta2 = (hand_y_norm - 0.5) * 4.0
                state[3] += (target_theta2 - state[1]) * 0.8
                gesture = "Empujar P2"
            
            elif dedos == 0:                   # Puño → Aumentar amortiguamiento (frenar)
                damping = min(damping + 0.05, 2.0)
                gesture = "Frenar (damping ↑)"
            
            else:                              # 3 dedos → Reducir damping + aumentar gravedad temporal
                damping = max(damping - 0.03, 0.0)
                g = 9.81 * 1.2
                gesture = "Acelerar"
    
    # Actualizar gravedad a valor normal si no se está acelerando
    if "Acelerar" not in gesture:
        g = 9.81
    
    # ========================
    # INTEGRACIÓN NUMÉRICA (un paso)
    # ========================
    t_span = [0, dt]
    sol = odeint(derivs, state, t_span, args=(L1, L2, m1, m2, g, damping))
    state = sol[-1]
    
    # Limitar ángulos (opcional)
    state[0] = state[0] % (2 * math.pi)
    state[1] = state[1] % (2 * math.pi)
    
    # ========================
    # DIBUJAR EN PYGAME
    # ========================
    screen.fill(BLACK)
    
    # Centro de pivote
    cx, cy = WIDTH // 2, HEIGHT // 3
    
    # Calcular posiciones
    x1 = cx + L1 * math.sin(state[0])
    y1 = cy + L1 * math.cos(state[0])
    x2 = x1 + L2 * math.sin(state[1])
    y2 = y1 + L2 * math.cos(state[1])
    
    # Guardar trayectoria
    trail.append((int(x2), int(y2)))
    if len(trail) > 800:
        trail.pop(0)
    
    # Dibujar trayectoria
    if len(trail) > 1:
        pygame.draw.lines(screen, (100, 100, 255), False, trail, 2)
    
    # Dibujar brazos y masas
    pygame.draw.line(screen, WHITE, (cx, cy), (int(x1), int(y1)), 6)
    pygame.draw.line(screen, WHITE, (int(x1), int(y1)), (int(x2), int(y2)), 6)
    
    pygame.draw.circle(screen, RED, (int(x1), int(y1)), 15)
    pygame.draw.circle(screen, BLUE, (int(x2), int(y2)), 15)
    
    # Información en pantalla
    info1 = font.render(f"θ1: {state[0]:.2f} rad   θ2: {state[1]:.2f} rad", True, WHITE)
    info2 = font.render(f"Amortiguamiento: {damping:.2f}   g: {g:.2f}", True, WHITE)
    info3 = font.render(f"Gestos: {gesture}", True, GREEN)
    screen.blit(info1, (10, 10))
    screen.blit(info2, (10, 40))
    screen.blit(info3, (10, 70))
    
    pygame.display.flip()
    clock.tick(60)
    
    # Mostrar cámara en ventana aparte (opcional, puedes comentarlo si molesta)
    cv2.putText(frame, gesture, (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow("Camara - Gestos", frame)
    
    # Salir con ESC o cerrando ventana
    if cv2.waitKey(1) == 27 or pygame.event.get(pygame.QUIT):
        running = False

cap.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()