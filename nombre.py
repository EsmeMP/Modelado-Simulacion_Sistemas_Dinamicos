import cv2
import mediapipe as mp
import numpy as np
import matplotlib.pyplot as plt
from scipy.integrate import odeint
from scipy import signal


# ========================
# CONFIGURACIÓN MEDIAPIPE
# ========================
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

# ========================
# PARÁMETROS DEL SISTEMA
# m = masa (kg), c = amortiguamiento (N·s/m), k = rigidez (N/m)
# ========================
m, c, k = 1000.0, 200.0, 5000.0
F0 = 1000.0   # Amplitud de fuerza (N)
omega = 2 * np.pi * 1  # Frecuencia de excitación (rad/s)
t = np.linspace(0, 10, 1000)

# ========================
# GESTOS → ACCIONES
# ========================
GESTO_INFO = {
    0: ("PUÑO",         (0, 0, 255),  "m +100 kg"),
    1: ("1 dedo",       (0, 165, 255),"k +500 N/m"),
    2: ("2 dedos",      (0, 255, 255),"k -500 N/m"),
    3: ("3 dedos",      (0, 255, 0),  "c +50 N·s/m"),
    4: ("4 dedos",      (255, 0, 255),"c -50 N·s/m"),
    5: ("MANO ABIERTA", (255, 255, 0),"RESET"),
}

def contar_dedos(lm):
    dedos = 0
    for punta, base in [(8,6),(12,10),(16,14),(20,18)]:
        if lm[punta].y < lm[base].y:
            dedos += 1
    # Pulgar
    if lm[4].x > lm[3].x:
        dedos += 1
    return dedos

def aplicar_gesto(dedos):
    global m, c, k
    if dedos == 0:   m = min(m + 100, 5000)
    elif dedos == 1: k = min(k + 500, 50000)
    elif dedos == 2: k = max(k - 500, 100)
    elif dedos == 3: c = min(c + 50, 5000)
    elif dedos == 4: c = max(c - 50, 10)
    elif dedos == 5: m, c, k = 1000.0, 200.0, 5000.0  # Reset

# ========================
# SOLUCIÓN ANALÍTICA (Laplace → Respuesta forzada)
# x(s) = F(s) / (ms² + cs + k)
# Respuesta particular: x_p(t) para entrada senoidal
# ========================
def solucion_analitica(t, m, c, k):
    wn = np.sqrt(k / m)
    zeta = c / (2 * np.sqrt(m * k))
    wd = wn * np.sqrt(max(1 - zeta**2, 1e-6))

    # Respuesta forzada (amplitud de estado estacionario)
    denom = np.sqrt((k - m*omega**2)**2 + (c*omega)**2)
    X = F0 / denom if denom > 0 else 0
    phi = np.arctan2(c*omega, k - m*omega**2)

    # Respuesta transitoria (condiciones iniciales = 0)
    if zeta < 1:  # Subamortiguado
        A = -X * np.cos(phi)
        B = (-X * np.sin(phi) - zeta*wn*A) / wd if wd > 0 else 0
        x_trans = np.exp(-zeta*wn*t) * (A*np.cos(wd*t) + B*np.sin(wd*t))
    else:          # Sobreamortiguado / críticamente amortiguado
        x_trans = np.zeros_like(t)

    x_part = X * np.sin(omega*t - phi)
    return x_trans + x_part

# ========================
# SOLUCIÓN NUMÉRICA (odeint / RK45)
# ========================
def fuerza(t): return F0 * np.sin(omega * t)

def sistema(y, t, m, c, k):
    x, v = y
    return [v, (fuerza(t) - c*v - k*x) / m]

def solucion_numerica(t, m, c, k):
    sol = odeint(sistema, [0, 0], t, args=(m, c, k))
    return sol[:, 0]

# ========================
# GRÁFICA COMPARATIVA
# ========================
fig, axes = plt.subplots(2, 1, figsize=(8, 6))
fig.suptitle("Sistema masa-resorte-amortiguador", fontsize=13)
plt.tight_layout(pad=2.5)
plt.ion()

def actualizar_grafica():
    x_anal = solucion_analitica(t, m, c, k)
    x_num  = solucion_numerica(t, m, c, k)
    error  = np.abs(x_anal - x_num)

    wn   = np.sqrt(k / m)
    zeta = c / (2 * np.sqrt(m * k))
    tipo = "Subamortiguado" if zeta < 1 else ("Crítico" if abs(zeta-1) < 0.01 else "Sobreamortiguado")

    # Subplot 1: comparación
    ax1 = axes[0]
    ax1.cla()
    ax1.plot(t, x_anal, 'b-',  lw=1.5, label='Analítica (Laplace)')
    ax1.plot(t, x_num,  'r--', lw=1.2, label='Numérica (odeint)', alpha=0.8)
    ax1.set_title(f"m={m:.0f} kg  |  c={c:.0f} N·s/m  |  k={k:.0f} N/m  |  ζ={zeta:.3f}  [{tipo}]",
                  fontsize=9)
    ax1.set_ylabel("Desplazamiento (m)")
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)

    # Subplot 2: error absoluto
    ax2 = axes[1]
    ax2.cla()
    ax2.plot(t, error, 'g-', lw=1)
    ax2.fill_between(t, 0, error, alpha=0.2, color='green')
    ax2.set_title(f"Error absoluto  |  máx={error.max():.2e} m", fontsize=9)
    ax2.set_ylabel("|Error| (m)")
    ax2.set_xlabel("Tiempo (s)")
    ax2.grid(True, alpha=0.3)

    plt.pause(0.01)

# ========================
# CÁMARA PRINCIPAL
# ========================
cap = cv2.VideoCapture(0)
dedos_anterior = -1
frame_count = 0
UPDATE_EVERY = 20  # Actualizar simulación cada N frames

while True:
    ret, frame = cap.read()
    if not ret: break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb)

    if result.multi_hand_landmarks:
        for hand_lm in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_lm, mp_hands.HAND_CONNECTIONS)
            dedos = contar_dedos(hand_lm.landmark)

            if dedos != dedos_anterior:
                aplicar_gesto(dedos)
                dedos_anterior = dedos

            nombre, color, accion = GESTO_INFO[dedos]
            # HUD
            cv2.rectangle(frame, (0,0), (380, 120), (20,20,20), -1)
            cv2.putText(frame, f"Gesto: {nombre}",  (10, 30),  cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.putText(frame, f"Accion: {accion}", (10, 60),  cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 1)
            cv2.putText(frame, f"m={m:.0f}  c={c:.0f}  k={k:.0f}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 1)
            cv2.putText(frame, "ESC para salir", (10, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (150,150,150), 1)
    else:
        cv2.putText(frame, "Sin mano detectada", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (100,100,100), 2)
        dedos_anterior = -1

    # Actualizar simulación periódicamente
    frame_count += 1
    if frame_count % UPDATE_EVERY == 0:
        actualizar_grafica()

    cv2.imshow("Control por gestos", frame)
    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()
plt.ioff()
plt.close()