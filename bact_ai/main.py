# ========================
# MAIN.PY - GestBact AI con 5 Factores (Temp, Humedad, pH, Luz, Nutrientes)
# ========================

import pygame
import sys
import numpy as np
import cv2
import random
from collections import deque

from config import *
from microbes import get_all_microbes, get_microbe_data, calculate_growth_rate
from simulation import Particle, create_explosion, handle_collisions, update_bacteria_growth
from gestures import GestureController
from ui import Slider, PopulationGraph, draw_ui, CustomMicrobeForm, draw_ui_overlay, StressGraph, InvasionGraph
from analysis import show_analysis

from simulation import Particle, create_explosion, handle_collisions, update_bacteria_growth, contaminate
from microbes import get_all_microbes, get_microbe_data, calculate_growth_rate, get_invader


# ========================
# INICIALIZACIÓN
# ========================
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("GestBact AI - Simulador con 5 Factores")
clock = pygame.time.Clock()

# === VARIABLES AMBIENTALES ===
temp              = 25.0
humidity          = 50.0
ph                = 7.0
light             = 30.0
nutrients         = INITIAL_NUTRIENTS
current_microbe   = "E. coli"
paused            = False
show_trails       = True
enable_collisions = True

# === SISTEMA DE DÍAS — UN SOLO MÉTODO (tiempo absoluto) ===
SECONDS_PER_DAY = 5.0       # 1 día simulado = 5 segundos reales
simulated_days  = 0.0       # float continuo
_start_ticks    = pygame.time.get_ticks()
_paused_accum   = 0         # ms totales pausados
_pause_start    = 0         # ms cuando empezó la pausa actual

# === HISTORIAL DE POBLACIÓN ===
simulation_history = []
invasion_history   = []     # [(día, n_nativas, n_invasoras), ...]
HISTORY_SAMPLE     = 10

# === PARTÍCULAS ===
particles = [
    Particle(
        random.randint(80, WIDTH - 80),
        random.randint(80, HEIGHT - 150),
        is_bacteria=True,
        microbe_key=current_microbe
    )
    for _ in range(INITIAL_PARTICLES)
]

# === COMPONENTES UI ===
temp_slider     = Slider(450,  65, 280,  0,    60,   "Temperatura (°C)",   YELLOW)
hum_slider      = Slider(450, 115, 280,  5,   100,   "Humedad (%)",         CYAN)
ph_slider       = Slider(450, 165, 280,  4.0,   9.0, "pH",                  PURPLE)
light_slider    = Slider(450, 215, 280,  0,   100,   "Iluminación UV (%)", ORANGE)
nutrient_slider = Slider(450, 265, 280,  0,   100,   "Nutrientes (%)",      GREEN)

population_graph   = PopulationGraph(780, 65, 460, 180)
gesture_controller = GestureController()
custom_form        = CustomMicrobeForm()
stress_graph       = StressGraph()
invasion_graph     = InvasionGraph()

# === AUXILIARES ===
running       = True
gesture_text  = "Esperando manos..."
last_day_time = 0
DAY_COOLDOWN  = 800

print("GestBact AI iniciado con 5 factores científicos!")

# ========================
# BUCLE PRINCIPAL
# ========================
while running:
    dt = clock.tick(FPS) / 1000.0
    current_w, current_h = screen.get_size()

    # ── DÍAS:
    if not paused:
        elapsed_ms     = pygame.time.get_ticks() - _start_ticks - _paused_accum
        simulated_days = max(0.0, (elapsed_ms / 1000.0) / SECONDS_PER_DAY)
        stress_graph.update(particles)

    # ------------------- Eventos -------------------
    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.VIDEORESIZE:
            screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

        # Sliders
        for slider in (temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider):
            if slider.handle_event(event):
                temp      = temp_slider.value
                humidity  = hum_slider.value
                ph        = ph_slider.value
                light     = light_slider.value
                nutrients = nutrient_slider.value

        # Teclado
        if event.type == pygame.KEYDOWN:

            if custom_form.active:
                result_form = custom_form.handle_event(event)
                if result_form:
                    key, data = result_form
                    current_microbe = key
                continue

            if event.key == pygame.K_SPACE:
                paused = not paused
                if paused:
                    _pause_start = pygame.time.get_ticks()
                else:
                    _paused_accum += pygame.time.get_ticks() - _pause_start

            elif event.key == pygame.K_r:
                particles.clear()
                particles = [
                    Particle(
                        random.randint(80, current_w - 80),
                        random.randint(80, current_h - 150),
                        is_bacteria=True,
                        microbe_key=current_microbe
                    )
                    for _ in range(INITIAL_PARTICLES)
                ]
                
                simulated_days = 0.0
                _start_ticks   = pygame.time.get_ticks()
                _paused_accum  = 0
                _pause_start   = 0
                simulation_history.clear()
                invasion_history.clear()
                invasion_graph.clear()
                population_graph.history.clear()

            elif event.key == pygame.K_b:
                import simulation as _sim_mod

            
                invasoras_vivas = [p for p in particles
                                   if p.is_bacteria
                                   and p.microbe_key != current_microbe
                                   and p.state != "dead"]

                if invasoras_vivas:
                    antes = len(particles)
                    particles[:] = [p for p in particles
                                    if not (p.is_bacteria
                                            and p.microbe_key != current_microbe)]
                    eliminadas = antes - len(particles)
                    _sim_mod.invasion_active = False
                    _sim_mod.invasion_key    = None
                    invasion_graph.clear()
                    gesture_text = f"Antibiótico: -{eliminadas} invasoras"
                else:
                    
                    antes = len(particles)
                    particles[:] = [p for p in particles
                                    if not (p.is_bacteria
                                            and p.microbe_key == current_microbe)]
                    eliminadas = antes - len(particles)
                    _sim_mod.invasion_active = False
                    _sim_mod.invasion_key    = None
                    gesture_text = f"¡Antibiótico! -{eliminadas} bacterias"

            elif event.key == pygame.K_f:
                nutrients = MAX_NUTRIENTS
                nutrient_slider.update(nutrients)
                gesture_text = "¡Nutrientes repuestos al 100%!"

            elif event.key == pygame.K_t:
                show_trails = not show_trails

            elif event.key == pygame.K_c:
                enable_collisions = not enable_collisions

            elif event.key == pygame.K_e:
                import simulation as _sim_mod
                _sim_mod.extinction_mode = not _sim_mod.extinction_mode
                modo = "EXTINCIÓN" if _sim_mod.extinction_mode else "NORMAL"
                gesture_text = f"Modo {modo} activado"

            elif event.key == pygame.K_n:
                custom_form.toggle()

            elif event.key == pygame.K_i:
                invader = get_invader(current_microbe)
                contaminate(particles, current_w, current_h,
                            invader_key=invader, count=30)
                gesture_text = f"¡Invasión de {invader}!"

            elif event.key == pygame.K_RIGHT:
                keys = get_all_microbes()
                idx = keys.index(current_microbe)
                current_microbe = keys[(idx + 1) % len(keys)]
                gesture_text = f"Microbio: {current_microbe}"
                data = get_microbe_data(current_microbe)
                if data:
                    for p in particles:
                        if p.is_bacteria:
                            p.shape       = data.get("shape", "bacilo_peritrico")
                            p.color       = tuple(data["color"])
                            p.microbe_key = current_microbe

            elif event.key == pygame.K_LEFT:
                keys = get_all_microbes()
                idx = keys.index(current_microbe)
                current_microbe = keys[(idx - 1) % len(keys)]
                gesture_text = f"Microbio: {current_microbe}"
                data = get_microbe_data(current_microbe)
                if data:
                    for p in particles:
                        if p.is_bacteria:
                            p.shape       = data.get("shape", "bacilo_peritrico")
                            p.color       = tuple(data["color"])
                            p.microbe_key = current_microbe

            elif event.key == pygame.K_m:
                # ── Análisis matemático ──
                import simulation as _sim_mod_m

                r_actual = calculate_growth_rate(
                    temp, humidity, ph, light, nutrients, current_microbe
                )
                t_max_analisis = max(30.0, simulated_days * 2.0)

                # Parámetros de invasión
                _inv_active = _sim_mod_m.invasion_active
                _inv_key    = _sim_mod_m.invasion_key
                _r_inv      = None
                if _inv_active and _inv_key:
                    _r_inv = calculate_growth_rate(
                        temp, humidity, ph, light, nutrients, _inv_key
                    )

                _n0_nat = sum(1 for p in particles
                              if p.is_bacteria
                              and p.microbe_key == current_microbe)
                _m0_inv = sum(1 for p in particles
                              if p.is_bacteria
                              and p.microbe_key != current_microbe
                              and p.state != "dead")

                show_analysis(
                    N0                 = max(1, len(particles)),
                    r_frame            = r_actual,
                    K                  = MAX_PARTICLES,
                    t_max              = t_max_analisis,
                    steps              = 800,
                    simulation_history = simulation_history.copy(),
                    microbe_name       = current_microbe,
                    factor_values      = {
                        "temp":      temp,
                        "humidity":  humidity,
                        "ph":        ph,
                        "light":     light,
                        "nutrients": nutrients,
                    },
                )
                gesture_text = f"Análisis abierto — día {simulated_days:.2f}"

    # ------------------- Gestos -------------------
    frame, result = gesture_controller.get_frame()
    if frame is None:
        break

    hand_forces    = []
    vortex_centers = []
    _kb_gesture    = gesture_text  

    if result and not custom_form.active:
        frame = gesture_controller.draw_landmarks(frame, result)
        hand_forces, vortex_centers, temp, humidity, ph, light, current_microbe, gesture_text = \
            gesture_controller.process_gestures(
                result, current_w, current_h,
                temp, humidity, ph, light, current_microbe
            )
        if any(w in _kb_gesture for w in
               ["Antibiótico", "Invasión", "Extinción", "Nutrientes repuestos"]):
            gesture_text = _kb_gesture

    if gesture_controller.pause_triggered:
        paused = not paused
        if paused:
            _pause_start = pygame.time.get_ticks()
        else:
            _paused_accum += pygame.time.get_ticks() - _pause_start
        gesture_controller.pause_triggered = False

    if gesture_text.startswith("Nutrientes:"):
        try:
            nutrients = float(gesture_text.split(":")[1])
            nutrient_slider.update(nutrients)
            gesture_text = f"Nutrientes: {nutrients:.0f}%"
        except:
            pass

    # Sincronizar sliders
    temp_slider.update(temp)
    hum_slider.update(humidity)
    ph_slider.update(ph)
    light_slider.update(light)

    # ------------------- Simulación -------------------
    if not paused:
        import simulation as _sim_upd

        for p in particles:
            total_force = np.zeros(2)

            for hand_pos, is_attract, strength in hand_forces:
                direction = hand_pos - p.pos
                dist = np.linalg.norm(direction)
                if dist > 15:
                    direction /= dist
                    force_mag = (12500 + strength * 19000) / (dist**2 + 80)
                    force = direction * force_mag
                    if not is_attract:
                        force = -force
                    total_force += force
                    p.glow = max(p.glow, 0.9)

            p.update(total_force, dt)

            # Límite de velocidad
            MAX_SPEED = 400.0
            speed = np.linalg.norm(p.vel)
            if speed > MAX_SPEED:
                p.vel = (p.vel / speed) * MAX_SPEED

            # Paredes con empuje suave
            margin = 30
            if p.pos[0] < margin:
                p.vel[0] += (margin - p.pos[0]) * 2.5
                p.pos[0]  = max(2.0, p.pos[0])
            elif p.pos[0] > current_w - margin:
                p.vel[0] -= (p.pos[0] - (current_w - margin)) * 2.5
                p.pos[0]  = min(float(current_w - 2), p.pos[0])

            if p.pos[1] < margin:
                p.vel[1] += (margin - p.pos[1]) * 2.5
                p.pos[1]  = max(2.0, p.pos[1])
            elif p.pos[1] > current_h - margin:
                p.vel[1] -= (p.pos[1] - (current_h - margin)) * 2.5
                p.pos[1]  = min(float(current_h - 2), p.pos[1])

        nutrients = update_bacteria_growth(
            particles, temp, humidity, ph, light, nutrients,
            current_microbe, MAX_PARTICLES
        )
        nutrient_slider.update(nutrients)

        if enable_collisions and len(particles) < 600:
            handle_collisions(particles)

        population_graph.update(len(particles))

        # ── Historial de población (para análisis logístico) ──────────
        if not simulation_history or pygame.time.get_ticks() % HISTORY_SAMPLE == 0:
            simulation_history.append((simulated_days, len(particles)))
            if len(simulation_history) > 500:
                simulation_history.pop(0)

        # ── Historial de invasión (para análisis Lotka-Volterra) ──────
        if _sim_upd.invasion_active:
            invasion_graph.update(particles, current_microbe)
            _nat_count = sum(1 for p in particles
                             if p.is_bacteria
                             and p.microbe_key == current_microbe)
            _inv_count = sum(1 for p in particles
                             if p.is_bacteria
                             and p.microbe_key != current_microbe
                             and p.state != "dead")
            if (not invasion_history
                    or invasion_history[-1][0] != simulated_days):
                invasion_history.append((simulated_days, _nat_count, _inv_count))
                if len(invasion_history) > 500:
                    invasion_history.pop(0)

    # Explosión por gesto de pulgar (solo visual, no toca días)
    current_time = pygame.time.get_ticks()
    if "¡+1 Día" in gesture_text and current_time - last_day_time > DAY_COOLDOWN:
        last_day_time = current_time
        if particles:
            create_explosion(particles, current_w // 2, current_h // 2,
                             count=25, intensity=0.7, microbe_key=current_microbe)

    # ========================
    # DIBUJAR
    # ========================

    # 1. Fondo
    draw_ui(screen, temp, humidity, ph, light, nutrients, current_microbe,
            simulated_days, particles, population_graph, stress_graph,
            temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider)

    # 2. Trails
    if show_trails and len(particles) < 500:
        for p in particles:
            speed = np.linalg.norm(p.vel)
            if speed > 25:
                trail_surf = pygame.Surface((6, 6), pygame.SRCALPHA)
                alpha = min(35, int(20 * (speed / 200)))
                pygame.draw.circle(trail_surf, (*p.color[:3], alpha), (3, 3), 3)
                screen.blit(trail_surf, (int(p.pos[0]) - 3, int(p.pos[1]) - 3))

    # 3. Bacterias
    for p in particles:
        p.draw(screen)

    # 4. Paneles encima de todo
    draw_ui_overlay(screen, temp, humidity, ph, light, nutrients, current_microbe,
                    simulated_days, particles, population_graph, stress_graph,
                    temp_slider, hum_slider, ph_slider, light_slider, nutrient_slider,
                    invasion_graph=invasion_graph)

    # 5. Texto de gesto
    if any(w in gesture_text for w in
           ["Temp", "Humedad", "pH", "Luz", "Microbio",
            "Antibiótico", "Nutrientes", "Invasión", "Extinción"]):
        gesture_font = pygame.font.SysFont("Arial", 28)
        gesture_surf = gesture_font.render(gesture_text, True, PURPLE)
        screen.blit(gesture_surf,
                    (current_w // 2 - gesture_surf.get_width() // 2, 25))

    # 6. Formulario (siempre al frente)
    custom_form.draw(screen)

    import analysis as _ana_mod
    with _ana_mod._analysis_lock:
        if _ana_mod.analysis_ready:
            import subprocess
            subprocess.Popen(["xdg-open", _ana_mod.analysis_path])
            _ana_mod.analysis_ready = False 
    pygame.display.flip()

    if frame is not None:
        cv2.putText(frame, gesture_text, (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.3, (0, 255, 255), 3)
        cv2.imshow("Camara - GestBact AI", frame)

    if cv2.waitKey(1) == 27:
        running = False

# ========================
# FINALIZACIÓN
# ========================
gesture_controller.release()
cv2.destroyAllWindows()
pygame.quit()
sys.exit()