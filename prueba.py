import cv2
import mediapipe as mp
import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import odeint

# ========================
# CONFIGURACIÓN MEDIAPIPE
# ========================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

# ========================
# PARÁMETROS DEL SISTEMA
# ========================
m = 1000.0
c = 200.0
k = 5000.0

# ========================
# FUNCIÓN DEL SISTEMA (NUMÉRICA)
# ========================
def fuerza(t):
    return 1000 * np.sin(2 * np.pi * 1 * t)

def sistema(y, t, m, c, k):
    x, v = y
    dxdt = v
    dvdt = (fuerza(t) - c * v - k * x) / m
    return [dxdt, dvdt]

# ========================
# SOLUCIÓN ANALÍTICA (EQUIVALENTE A LAPLACE)
# ========================
def solucion_analitica(t, m, c, k, F0=1000.0, omega=2*np.pi):
    wn = np.sqrt(k / m)
    zeta = c / (2 * m * wn)
    
    # Solución particular (igual para todos los casos)
    denom = (k - m * omega**2)**2 + (c * omega)**2
    D = F0 * (k - m * omega**2) / denom
    E = -F0 * (c * omega) / denom
    
    # Solución homogénea según el amortiguamiento
    if zeta < 1:  # Subamortiguado (caso inicial)
        wd = wn * np.sqrt(1 - zeta**2)
        alpha = zeta * wn
        A = -E
        B = (alpha * A - omega * D) / wd
        xh = np.exp(-alpha * t) * (A * np.cos(wd * t) + B * np.sin(wd * t))
    
    elif abs(zeta - 1) < 1e-6:  # Críticamente amortiguado
        A = -E
        B = wn * A - omega * D
        xh = (A + B * t) * np.exp(-wn * t)
    
    else:  # Sobreamortiguado
        disc = np.sqrt(zeta**2 - 1)
        r1 = -zeta * wn + wn * disc
        r2 = -zeta * wn - wn * disc
        A = (-omega * D + E * r2) / (r1 - r2)
        B = -E - A
        xh = A * np.exp(r1 * t) + B * np.exp(r2 * t)
    
    xp = D * np.sin(omega * t) + E * np.cos(omega * t)
    return xh + xp

# ========================
# SIMULACIÓN CON COMPARACIÓN
# ========================
plt.ion()
fig, ax = plt.subplots(figsize=(10, 5))

def simular():
    global m, c, k
    y0 = [0, 0]
    t = np.linspace(0, 5, 500)
    
    # Solución numérica
    sol = odeint(sistema, y0, t, args=(m, c, k))
    x_num = sol[:, 0]
    
    # Solución analítica
    x_anal = solucion_analitica(t, m, c, k)
    
    # Zeta para mostrar en título
    wn = np.sqrt(k / m)
    zeta = c / (2 * m * wn)
    
    ax.clear()
    ax.plot(t, x_num, label='Numérica (odeint)', color='blue', linewidth=2)
    ax.plot(t, x_anal, '--', label='Analítica (Laplace)', color='red', linewidth=2)
    ax.set_title(f"Sistema Masa-Resorte-Amortiguador\nm={m:.0f} | c={c:.0f} | k={k:.0f} | ζ={zeta:.3f}")
    ax.set_xlabel("Tiempo (s)")
    ax.set_ylabel("Desplazamiento (m)")
    ax.grid(True)
    ax.legend()
    plt.pause(0.01)

# ========================
# CÁMARA + GESTOS
# ========================
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)
    
    gesture_text = ""
    color = (0, 0, 255)
    
    if result.multi_hand_landmarks:
        for hand_landmarks in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
            
            # Conteo de dedos extendidos (sin pulgar)
            dedos = 0
            if hand_landmarks.landmark[8].y < hand_landmarks.landmark[6].y:   # índice
                dedos += 1
            if hand_landmarks.landmark[12].y < hand_landmarks.landmark[10].y: # medio
                dedos += 1
            if hand_landmarks.landmark[16].y < hand_landmarks.landmark[14].y: # anular
                dedos += 1
            if hand_landmarks.landmark[20].y < hand_landmarks.landmark[18].y: # meñique
                dedos += 1
            
            # ========================
            # ACCIONES POR GESTO
            # ========================
            if dedos >= 3:          # ≥3 dedos → Aumentar rigidez (k)
                k += 50
                gesture_text = "RIGIDEZ + (k ↑)"
                color = (0, 255, 0)
            else:                   # <3 dedos → Aumentar amortiguamiento (c)
                c += 20
                gesture_text = "AMORTIGUAMIENTO + (c ↑)"
                color = (0, 0, 255)
    
    # Mostrar texto del gesto
    cv2.putText(frame, gesture_text, (10, 50),
                cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
    
    # Ejecutar simulación con parámetros actuales
    simular()
    
    cv2.imshow("Control por Gestos - Sistema Masa-Resorte", frame)
    
    if cv2.waitKey(1) == 27:  # ESC para salir
        break

cap.release()
cv2.destroyAllWindows()
plt.close()