import cv2
import mediapipe as mp
import numpy as np
import random
import time

# ── Módulos propios ───────────────────────────────────────────
import audio
import camera
import hand_tracker
import splash
import particles
import graphs
import analysis

# ================================================================
#  CARGA EN PARALELO + SPLASH
# ================================================================
camera.start()
hand_tracker.start()
audio.start()

splash.show(
    camera._ready_camera,
    hand_tracker._ready_mediapipe,
    audio._ready_audio
)

# ── Referencias limpias post-splash ───────────────────────────
cap          = camera.cap
hands        = hand_tracker.hands
mp_hands_mod = mp.solutions.hands
mp_draw      = mp.solutions.drawing_utils

# ================================================================
#  PARÁMETROS FÍSICOS
# ================================================================
dt    = 1.0
c     = 0.01
k_voz = 0.02

# ================================================================
#  CONFIG PARTÍCULAS
# ================================================================
sim_width  = particles.sim_width
sim_height = particles.sim_height

particles.init(600)

# ================================================================
#  DETECCIÓN DE GESTOS
# ================================================================
dedos_hist     = []
HIST_SIZE      = 8
frames_abierta = 0

estado_mano         = "neutro"
last_explosion_time = 0.0
COOLDOWN            = 0.3

# ================================================================
#  DATOS / LOGS
# ================================================================
energy_log   = []
voice_log    = []
analytic_log = []
numeric_log  = []
LOG_MAX      = 300

t  = 0
v0 = 20.0

notif_text  = ""
notif_timer = 0.0
NOTIF_SECS  = 1.5

# ================================================================
#  LOOP PRINCIPAL
# ================================================================
cv2.resizeWindow("Simulacion", sim_width, sim_height + 160)
cv2.namedWindow("Camara", cv2.WINDOW_NORMAL)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    sim   = np.zeros((sim_height, sim_width, 3), dtype=np.uint8)

    level = float(audio.audio_level)
    if level < 2.0:
        level = 0.0

    # ── Detección de mano ────────────────────────────────────
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb.flags.writeable = False
    result = hands.process(rgb)
    rgb.flags.writeable = True

    x_hand, y_hand = sim_width // 2, sim_height // 2
    dedos          = 0
    mano_detectada = False

    if result.multi_hand_landmarks:
        for hand_lm in result.multi_hand_landmarks:
            mp_draw.draw_landmarks(frame, hand_lm, mp_hands_mod.HAND_CONNECTIONS)
            mano_detectada = True
            x_hand = int(hand_lm.landmark[8].x * sim_width)
            y_hand = int(hand_lm.landmark[8].y * sim_height)
            for tip, base in zip([8,12,16,20], [6,10,14,18]):
                if hand_lm.landmark[tip].y < hand_lm.landmark[base].y - 0.02:
                    dedos += 1

    dedos_hist.append(dedos)
    if len(dedos_hist) > HIST_SIZE:
        dedos_hist.pop(0)

    dedos_avg = int(np.mean(dedos_hist))
    cerrada   = dedos_avg <= 1

    if dedos_avg >= 3:
        frames_abierta += 1
    else:
        frames_abierta = 0

    abierta = frames_abierta > 1

    if mano_detectada:
        gesto_str   = "ABIERTA" if abierta else ("CERRADA" if cerrada else "")
        gesto_color = (0, 255, 0) if abierta else (0, 180, 255)
        cv2.putText(frame, f"Dedos: {dedos_avg}  {gesto_str}", (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, gesto_color, 2, cv2.LINE_AA)

    # ── Agarrar ──────────────────────────────────────────────
    if cerrada:
        estado_mano = "cerrada"
        for i in range(particles.num_particles):
            dx = x_hand - particles.particles[i][0]
            dy = y_hand - particles.particles[i][1]
            if dx*dx + dy*dy < 140*140:
                particles.grabbed[i] = True

    # ── Explosión ────────────────────────────────────────────
    current_time = time.time()
    if (abierta and estado_mano == "cerrada" and
            current_time - last_explosion_time > COOLDOWN):
        estado_mano         = "abierta"
        last_explosion_time = current_time
        for i in range(particles.num_particles):
            if particles.grabbed[i]:
                angle = random.uniform(0, 2*np.pi)
                speed = random.uniform(20, 40)
                particles.velocities[i] = [speed*np.cos(angle), speed*np.sin(angle)]
                particles.grabbed[i]    = False

    if cerrada and estado_mano == "abierta":
        estado_mano = "cerrada"

    # ── Física ───────────────────────────────────────────────
    total_energy = 0.0
    total_speed  = 0.0
    for i in range(particles.num_particles):
        if particles.grabbed[i]:
            particles.particles[i]  = [x_hand + np.random.randint(-20, 20),
                                        y_hand + np.random.randint(-20, 20)]
            particles.velocities[i] *= 0
        else:
            particles.velocities[i] += (-c * particles.velocities[i]) * dt
            particles.velocities[i][0] += k_voz * level * random.uniform(-1, 1) * dt
            particles.velocities[i][1] += k_voz * level * random.uniform(-1, 1) * dt
            particles.particles[i]     += particles.velocities[i]

        if particles.particles[i][0] < 0 or particles.particles[i][0] > sim_width:
            particles.velocities[i][0] *= -1
        if particles.particles[i][1] < 0 or particles.particles[i][1] > sim_height:
            particles.velocities[i][1] *= -1

        spd           = float(np.linalg.norm(particles.velocities[i]))
        total_energy += 0.5 * spd**2
        total_speed  += spd

    t += dt
    analytic_log.append(v0 * np.exp(-c * t))
    numeric_log.append(total_speed / particles.num_particles)
    energy_log.append(total_energy)
    voice_log.append(level)
    for log in [analytic_log, numeric_log, energy_log, voice_log]:
        if len(log) > LOG_MAX:
            log.pop(0)

    # ── Dibujo de partículas ──────────────────────────────────
    particles.trail = (particles.trail * 0.85).astype(np.uint8)
    for i, p in enumerate(particles.particles):
        px_x = int(p[0]); px_y = int(p[1])
        pr_x = int(particles.prev_positions[i][0])
        pr_y = int(particles.prev_positions[i][1])
        if 0 <= px_x < sim_width and 0 <= px_y < sim_height:
            pcol = particles.pcolors[i]
            spd  = float(np.linalg.norm(particles.velocities[i]))
            sz   = max(2, min(int(4 + level/5 + spd/15), 18))
            cv2.circle(sim, (px_x, px_y), sz, pcol, -1)
            cv2.line(particles.trail, (pr_x, pr_y), (px_x, px_y), pcol, 1)

    particles.prev_positions = particles.particles.copy()
    sim = cv2.add(sim, particles.trail)

    if mano_detectada:
        ring_c = (0, 255, 100) if cerrada else (255, 200, 0)
        cv2.circle(sim, (x_hand, y_hand), 15,  ring_c, 2, cv2.LINE_AA)
        cv2.circle(sim, (x_hand, y_hand), 140, ring_c, 1, cv2.LINE_AA)

    # ── Panel de gráficas ────────────────────────────────────
    panel_h = 160
    GAP, COLS = 6, 4
    card_w = (sim_width - GAP * (COLS+1)) // COLS
    card_h = panel_h - GAP * 2

    panel = np.full((panel_h, sim_width, 3), (8, 6, 14), dtype=np.uint8)
    cv2.line(panel, (0, 0), (sim_width, 0), (0, 180, 80), 1)

    for i, (gdata, gcolor, glabel, gunit) in enumerate([
        (numeric_log,  (68,  100, 255), "Numerica",  ""),
        (analytic_log, (0,   230, 120), "Analitica", ""),
        (energy_log,   (255, 160,  40), "Energia",   ""),
        (voice_log,    (255, 220,  60), "Voz",       ""),
    ]):
        x0 = GAP + i * (card_w + GAP)
        g  = graphs.draw_graph_pro(gdata, card_w, card_h, gcolor, glabel, gunit)
        panel[GAP:GAP+card_h, x0:x0+card_w] = g

    final = np.vstack((sim, panel))

    # ── HUD superior ─────────────────────────────────────────
    overlay = final.copy()
    cv2.rectangle(overlay, (0, 0), (sim_width, 40), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.55, final, 0.45, 0, final)
    cv2.line(final, (0, 40), (sim_width, 40), (0, 80, 40), 1)
    cv2.putText(final, "dv/dt = -c*v + k_voz*voz(t)", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (225, 225, 225), 1, cv2.LINE_AA)
    params_str = f"c={c:.3f}  k={k_voz:.3f}  [q/a]=c  [w/s]=k  [+/-]=crecimiento [ESC]=guardar"
    (pw, _), _ = cv2.getTextSize(params_str, cv2.FONT_HERSHEY_SIMPLEX, 0.32, 1)
    cv2.putText(final, params_str, (sim_width-pw-8, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, (130, 130, 155), 1, cv2.LINE_AA)
    cv2.putText(final, f"Particulas: {particles.num_particles}",
                (10, sim_height+panel_h-8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)

    # ── Notificación ─────────────────────────────────────────
    if notif_text and (time.time() - notif_timer) < NOTIF_SECS:
        cx, cy = sim_width//2, sim_height//2
        ov2 = final.copy()
        cv2.rectangle(ov2, (cx-160, cy-30), (cx+160, cy+30), (0,0,0), -1)
        cv2.addWeighted(ov2, 0.6, final, 0.4, 0, final)
        (nw, _), _ = cv2.getTextSize(notif_text, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)
        cv2.putText(final, notif_text, (cx-nw//2, cy+10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2, cv2.LINE_AA)
    elif notif_text:
        notif_text = ""

    # ── Teclas ───────────────────────────────────────────────
    key = cv2.waitKey(1) & 0xFF

    if key == ord('q'): c     += 0.005
    if key == ord('a'): c      = max(0.0, c-0.005)
    if key == ord('w'): k_voz += 0.005
    if key == ord('s'): k_voz  = max(0.0, k_voz-0.005)
    if key in (ord('+'), ord('=')):
        particles.set_count(particles.num_particles+50)
        notif_text = f"{particles.num_particles} particulas"; notif_timer = time.time()
    if key == ord('-'):
        particles.set_count(particles.num_particles-50)
        notif_text = f"{particles.num_particles} particulas"; notif_timer = time.time()
    if key == ord('1'):
        particles.set_count(100)
        notif_text = f"Preset 1  {particles.num_particles}"; notif_timer = time.time()
    if key == ord('2'):
        particles.set_count(300)
        notif_text = f"Preset 2  {particles.num_particles}"; notif_timer = time.time()
    if key == ord('3'):
        particles.set_count(600)
        notif_text = f"Preset 3  {particles.num_particles}"; notif_timer = time.time()

    # ── ESC: guardar análisis ────────────────────────────────
    if key == 27:
        analysis.save(
            c, k_voz, v0, dt, particles.num_particles,
            analytic_log, numeric_log, energy_log, voice_log,
            final
        )
        break

    cv2.imshow("Simulacion", final)
    cv2.imshow("Camara", frame)

# ── Limpieza ─────────────────────────────────────────────────
camera.release()
audio.stop()
cv2.destroyAllWindows()