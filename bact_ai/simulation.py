# ========================
# SIMULATION.PY - Lógica de partículas y crecimiento con 5 factores
# Formas visuales distintas por tipo de microbio
# ========================

import pygame
import math
import random
import numpy as np
from config import *
from microbes import calculate_growth_rate, get_microbe_data

extinction_mode = False
invasion_active = False
invasion_key    = None

_capsule_cache = {} 
def _get_capsule_surf(color, cap_w, cap_h, state):
        """
        Devuelve una Surface de cápsula cacheada.
        Solo regenera si la combinación color+tamaño+estado no existe.
        Reduce creación de Surface de O(n) a O(1) en steady state.
        """
        key = (color, cap_w, cap_h, state)
        if key in _capsule_cache:
            return _capsule_cache[key]
    
        surf = pygame.Surface((cap_w + 6, cap_h + 6), pygame.SRCALPHA)
        cx, cy = (cap_w + 6) // 2, (cap_h + 6) // 2
        rect   = pygame.Rect(cx - cap_w // 2, cy - cap_h // 2, cap_w, cap_h)
        brad   = int(cap_h // 2)
    
        pygame.draw.rect(surf, color, rect, border_radius=brad)
    
        if state == "healthy":
            bcol = tuple(min(255, c + 70) for c in color[:3])
            pygame.draw.rect(surf, bcol, rect, 1, border_radius=brad)
        else:
            pygame.draw.rect(surf, (255, 70, 70), rect, 2, border_radius=brad)
    
        # Highlight
        hl_rect = pygame.Rect(cx - cap_w // 2 + 2,
                            cy - cap_h // 2 + 1,
                            cap_w - 4, max(2, cap_h // 3))
        hcol = tuple(min(255, c + 90) for c in color[:3])
        hl   = pygame.Surface((hl_rect.width, hl_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(hl, (*hcol, 80), hl.get_rect(),
                        border_radius=int(cap_h // 3))
        surf.blit(hl, (hl_rect.x, hl_rect.y))
    
        # Brillo central
        dot = pygame.Surface((4, 4), pygame.SRCALPHA)
        pygame.draw.circle(dot, (255, 255, 255, 60), (2, 2), 2)
        surf.blit(dot, (cx - 2, cy - 2))
    
        # Limitar tamaño del caché
        if len(_capsule_cache) > 80:
            _capsule_cache.clear()
    
        _capsule_cache[key] = surf
        return surf

class Particle:
    def __init__(self, x, y, is_bacteria=False, microbe_key="E. coli"):
        self.pos          = np.array([float(x), float(y)])
        self.vel          = np.array([random.uniform(-90, 90), random.uniform(-90, 90)])
        self.state        = "healthy" if is_bacteria else "normal"
        self.age          = 0
        self.max_age      = None if is_bacteria else 60  # ← partículas de explosión mueren en 60 frames
        self.collision_timer = 0
        self.glow         = 0.0
        self.stress_timer = 0

        data = get_microbe_data(microbe_key)
        self.color       = tuple(data["color"]) if data and is_bacteria else CYAN
        self.size        = 6.5 if is_bacteria else 4.5
        self.is_bacteria = is_bacteria
        self.microbe_key = microbe_key
        self.shape       = data.get("shape", "bacilo_peritrico") if data else "bacilo_peritrico"

    def update(self, force, dt, damping=DAMPING):
        self.vel += force * dt
        self.vel *= damping
        self.pos += self.vel * dt
        self.age += 1

        # Movimiento browniano — simula agitación térmica
        # Solo si la velocidad es muy baja
        speed = np.linalg.norm(self.vel)
        if speed < 15:
            brownian = np.array([
                random.uniform(-1, 1),
                random.uniform(-1, 1)
            ]) * 18.0
            self.vel += brownian

        if self.collision_timer > 0:
            self.collision_timer -= 1
        if self.glow > 0:
            self.glow *= 0.92
        if self.max_age is not None and self.age >= self.max_age:
            self.state = "dead"

    # ── Helpers de dibujo ──────────────────────────────────────────────────

    def _base_color(self):
        """Color según estado con parpadeo para stressed."""
        if self.state == "stressed":
            return ORANGE if (self.age // 8) % 2 == 0 else RED
        color = self.color
        if self.collision_timer > 0:
            color = tuple(min(255, c + 40) for c in color[:3])
        return color

    def _draw_glow(self, surface, ix, iy, size, color):
        if self.glow > 0.08:
            gr = int(size * 2.5)
            gs = pygame.Surface((gr * 2, gr * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*color[:3], int(55 * self.glow)), (gr, gr), gr)
            surface.blit(gs, (ix - gr, iy - gr))

    def _capsule_surf(self, color, cap_w, cap_h):
        return _get_capsule_surf(color, cap_w, cap_h, self.state), \
            (cap_w + 6) // 2, (cap_h + 6) // 2

    
    def _draw_flagelo_ondulado(self, surface, start_x, start_y,
                                angle_base, length, color, segments=6):
        """
        Dibuja un flagelo ondulado como una serie de segmentos
        con una onda sinusoidal animada por self.age.
        """
        alpha_col = tuple(color[:3])
        px, py = float(start_x), float(start_y)
        seg_len = length / segments
        wave_amp = seg_len * 0.55       # amplitud de la onda
        wave_freq = 0.055               # frecuencia espacial
        phase = self.age * 0.18         # animación temporal

        for k in range(segments):
            t = k / segments
            # Ángulo base + onda sinusoidal
            wave = wave_amp * math.sin(wave_freq * k * 20 + phase)
            seg_angle = angle_base + math.radians(wave * 6)
            nx2 = px + math.cos(seg_angle) * seg_len
            ny2 = py + math.sin(seg_angle) * seg_len

            # Grosor decrece hacia la punta
            thickness = max(1, 2 - k // 3)
            pygame.draw.line(surface, alpha_col,
                             (int(px), int(py)),
                             (int(nx2), int(ny2)),
                             thickness)
            px, py = nx2, ny2

    # ── Métodos de dibujo por forma ───────────────────────────────────────

    def _draw_bacilo_peritrico(self, surface, ix, iy, size, color, angle_rad):
        """
        E. coli / Salmonella — cápsula con 3 flagelos ondulados
        distribuidos alrededor del cuerpo (perítricos).
        """
        cap_w = int(size * 2.8)
        cap_h = int(size * 1.2)

        cap_surf, cx, cy = self._capsule_surf(color, cap_w, cap_h)

        # Flagelos ANTES de rotar (sobre cap_surf) desde ambos extremos
        flag_color = tuple(max(0, c - 40) for c in color[:3])
        flag_len   = int(size * 4.5)
        flag_segs  = 7
        phase_off  = self.age * 0.18

        # 3 flagelos: izquierda, izquierda-arriba, izquierda-abajo
        origins = [
            (cx - cap_w // 2, cy),
            (cx - cap_w // 2 + 3, cy - cap_h // 3),
            (cx - cap_w // 2 + 3, cy + cap_h // 3),
        ]
        for ox, oy in origins:
            px2, py2 = float(ox), float(oy)
            seg_len  = flag_len / flag_segs
            for k in range(flag_segs):
                wave  = math.sin(k * 0.9 + phase_off + ox * 0.1) * seg_len * 0.5
                fa    = math.pi + math.radians(wave * 5)
                nx2   = px2 + math.cos(fa) * seg_len
                ny2   = py2 + math.sin(fa) * seg_len + wave * 0.3
                thick = max(1, 2 - k // 3)
                pygame.draw.line(cap_surf, flag_color,
                                 (int(px2), int(py2)),
                                 (int(nx2), int(ny2)), thick)
                px2, py2 = nx2, ny2

        # Rotar y dibujar
        rotated = pygame.transform.rotate(cap_surf, -np.degrees(angle_rad))
        surface.blit(rotated, rotated.get_rect(center=(ix, iy)))

    def _draw_bacilo_polar(self, surface, ix, iy, size, color, angle_rad):
        """
        Pseudomonas — cápsula con 1 flagelo largo en la punta posterior.
        """
        cap_w = int(size * 2.6)
        cap_h = int(size * 1.1)

        cap_surf, cx, cy = self._capsule_surf(color, cap_w, cap_h)

        # 1 flagelo largo en el extremo izquierdo (posterior)
        flag_color = tuple(max(0, c - 50) for c in color[:3])
        flag_len   = int(size * 6.5)   # más largo que peritrico
        flag_segs  = 9
        phase_off  = self.age * 0.22

        px2, py2 = float(cx - cap_w // 2), float(cy)
        seg_len  = flag_len / flag_segs
        for k in range(flag_segs):
            wave  = math.sin(k * 0.7 + phase_off) * seg_len * 0.65
            fa    = math.pi + math.radians(wave * 7)
            nx2   = px2 + math.cos(fa) * seg_len
            ny2   = py2 + math.sin(fa) * seg_len + wave * 0.35
            thick = max(1, 2 - k // 4)
            pygame.draw.line(cap_surf, flag_color,
                             (int(px2), int(py2)),
                             (int(nx2), int(ny2)), thick)
            px2, py2 = nx2, ny2

        rotated = pygame.transform.rotate(cap_surf, -np.degrees(angle_rad))
        surface.blit(rotated, rotated.get_rect(center=(ix, iy)))

    def _draw_coco(self, surface, ix, iy, size, color):
        """
        Staphylococcus — esfera sin flagelos.
        Se dibuja en pares/tríos para simular racimos.
        """
        sz = int(size * 0.95)

        # Círculo principal
        pygame.draw.circle(surface, color, (ix, iy), sz)

        # Borde
        if self.state == "healthy":
            bcol = tuple(min(255, c + 70) for c in color[:3])
            pygame.draw.circle(surface, bcol, (ix, iy), sz, 1)
        else:
            pygame.draw.circle(surface, RED, (ix, iy), sz, 2)

        # Highlight 3D
        hx = ix - sz // 3
        hy = iy - sz // 3
        hr = max(2, sz // 3)
        hs = pygame.Surface((hr * 2, hr * 2), pygame.SRCALPHA)
        pygame.draw.circle(hs, (255, 255, 255, 55), (hr, hr), hr)
        surface.blit(hs, (hx - hr, hy - hr))

        # Segundo coco adyacente (simula diplococo)
        offset = int(sz * 1.5)
        off_angle = (self.age * 0.5) % (2 * math.pi)
        ox = ix + int(math.cos(off_angle) * offset)
        oy = iy + int(math.sin(off_angle) * offset)
        sz2 = max(3, int(sz * 0.8))
        scol = tuple(max(0, c - 30) for c in color[:3])
        pygame.draw.circle(surface, scol, (ox, oy), sz2)
        pygame.draw.circle(surface, bcol if self.state == "healthy" else RED,
                           (ox, oy), sz2, 1)

    def _draw_virus(self, surface, ix, iy, size, color):
        """
        Influenza — esfera pequeña con espículas (picos cortos) alrededor.
        """
        sz = int(size * 0.9)

        # Núcleo
        pygame.draw.circle(surface, color, (ix, iy), sz)
        if self.state == "healthy":
            bcol = tuple(min(255, c + 80) for c in color[:3])
            pygame.draw.circle(surface, bcol, (ix, iy), sz, 1)
        else:
            pygame.draw.circle(surface, RED, (ix, iy), sz, 2)

        # Highlight
        hs = pygame.Surface((sz, sz), pygame.SRCALPHA)
        pygame.draw.circle(hs, (255, 255, 255, 50), (sz // 3, sz // 3), sz // 3)
        surface.blit(hs, (ix - sz // 2, iy - sz // 2))

        # Espículas — picos cortos animados girando lentamente
        num_spikes = 10
        spike_len  = int(size * 1.4)
        spike_col  = tuple(min(255, c + 50) for c in color[:3])
        rotation   = self.age * 0.8   # rotación lenta

        for k in range(num_spikes):
            angle = math.radians(k * (360 / num_spikes) + rotation)
            sx1   = ix + int(math.cos(angle) * sz)
            sy1   = iy + int(math.sin(angle) * sz)
            sx2   = ix + int(math.cos(angle) * (sz + spike_len))
            sy2   = iy + int(math.sin(angle) * (sz + spike_len))
            pygame.draw.line(surface, spike_col, (sx1, sy1), (sx2, sy2), 2)
            # Punta de la espícula
            pygame.draw.circle(surface, spike_col, (sx2, sy2), 2)

    # ── Método draw principal ─────────────────────────────────────────────

    def draw(self, surface):
        if self.state == "dead":
            return

        color = self._base_color()
        size  = max(2.5, self.size * 0.75) if self.state == "stressed" else self.size
        ix, iy = int(self.pos[0]), int(self.pos[1])

        self._draw_glow(surface, ix, iy, size, color)

        speed     = np.linalg.norm(self.vel)
        angle_rad = np.arctan2(self.vel[1], self.vel[0]) if speed > 1 else 0.0

        if self.shape == "bacilo_peritrico":
            self._draw_bacilo_peritrico(surface, ix, iy, size, color, angle_rad)
        elif self.shape == "bacilo_polar":
            self._draw_bacilo_polar(surface, ix, iy, size, color, angle_rad)
        elif self.shape == "coco":
            self._draw_coco(surface, ix, iy, size, color)
        elif self.shape == "virus":
            self._draw_virus(surface, ix, iy, size, color)
        else:
            # Fallback: cápsula simple sin flagelos
            cap_w = int(size * 2.6)
            cap_h = int(size * 1.2)
            cap_surf, _, _ = self._capsule_surf(color, cap_w, cap_h)
            rotated = pygame.transform.rotate(cap_surf, -np.degrees(angle_rad))
            surface.blit(rotated, rotated.get_rect(center=(ix, iy)))


# ========================
# FUNCIONES DE SIMULACIÓN
# ========================

def create_explosion(particles_list, x, y, count=35,
                     intensity=1.0, microbe_key="E. coli"):
    from microbes import get_microbe_data
    data  = get_microbe_data(microbe_key)
    color = tuple(data["color"]) if data else (255, 255, 100)

    for _ in range(count):
        p       = Particle(x, y, is_bacteria=False)
        p.vel   = np.array([
            random.uniform(-300, 300) * intensity,
            random.uniform(-300, 300) * intensity
        ])
        p.glow  = 1.3
        p.size  = random.uniform(3.5, 8.0)
        p.color = color          # color del microbio en vez de CYAN
        particles_list.append(p)


def handle_collisions(particles, max_checks=700):
    n = len(particles)
    if n > max_checks:
        return

    for i in range(n):
        for j in range(i + 1, n):
            p1 = particles[i]
            p2 = particles[j]

            dx = p2.pos[0] - p1.pos[0]
            dy = p2.pos[1] - p1.pos[1]
            dist_sq = dx * dx + dy * dy
            min_dist_sq = (p1.size + p2.size) ** 2

            if dist_sq < min_dist_sq and dist_sq > 0.001:
                dist = math.sqrt(dist_sq)
                nx, ny = dx / dist, dy / dist
                rv = np.dot(p2.vel - p1.vel, np.array([nx, ny]))
                if rv > 0:
                    continue
                impulse = -1.65 * rv / 2.0
                p1.vel -= impulse * np.array([nx, ny])
                p2.vel += impulse * np.array([nx, ny])
                p1.collision_timer = p2.collision_timer = 3



def update_bacteria_growth(particles, temp, humidity, ph, light, nutrients,
                           microbe_key, max_particles):
    global invasion_active, invasion_key

    if not particles:
        return nutrients

    if extinction_mode:
        for p in particles:
            if p.is_bacteria and random.random() < 0.08:
                p.state = "dead"
        particles[:] = [p for p in particles if p.state != "dead"]
        return max(0.0, nutrients - 0.1)

    # ── Detectar si hay invasores ─────────────────────────────────────────
    total    = sum(1 for p in particles if p.is_bacteria)
    # ✅ Reemplaza ese bloque por:
    invaders = sum(1 for p in particles 
                if p.is_bacteria 
                and p.microbe_key != microbe_key
                and p.state != "dead")
    natives        = total - invaders
    invasion_ratio = invaders / total if total > 0 else 0.0
    invasion_active = invaders > 0

    # Solo actualizar invasion_key si hay invasores, nunca resetear a None si quedan vivos
    _found_key = None
    for p in particles:
        if p.is_bacteria and p.microbe_key != microbe_key and p.state != "dead":
            _found_key = p.microbe_key
            break
    if _found_key is not None:
        invasion_key = _found_key
    elif invaders == 0:
        invasion_key = None   # solo limpiar cuando realmente no queda ninguno vivo

    # ── Datos de ambos tipos ──────────────────────────────────────────────
    data_native  = get_microbe_data(microbe_key)
    data_invader = get_microbe_data(invasion_key) if invasion_key else None
    if not data_native:
        return nutrients

    growth_native  = calculate_growth_rate(temp, humidity, ph, light, nutrients, microbe_key)
    growth_invader = calculate_growth_rate(temp, humidity, ph, light, nutrients, invasion_key) \
                     if invasion_key else 0.0

    nutrient_cost_native  = data_native.get("nutrient_consumption", 0.005)
    nutrient_cost_invader = (data_invader.get("nutrient_consumption", 0.005) * 3.0) \
                             if data_invader else 0.0  # invasor consume 3x

    # ── Radio de toxinas ──────────────────────────────────────────────────
    TOXIN_RADIUS   = 55.0
    TOXIN_RADIUS_SQ = TOXIN_RADIUS ** 2
    TOXIN_PROB     = 0.012   # prob por frame de envenenar a un nativo cercano
    CASCADE_THRESH = 0.40    # si invasor > 40% → colapso acelerado

    # Construir listas separadas para eficiencia
    invader_positions = np.array([
        p.pos for p in particles
        if p.is_bacteria and p.microbe_key != microbe_key
    ]) if invaders > 0 else None

    new_bacteria = []

    for p in particles:
        if not p.is_bacteria:
            continue

        is_invader = p.microbe_key != microbe_key
        data       = data_invader if is_invader else data_native

        # ── Estrés por temperatura y pH ───────────────────────────────────
        temp_ok = data["temp_range"][0] <= temp <= data["temp_range"][1]
        ph_ok   = data["ph_range"][0]   <= ph   <= data["ph_range"][1]

        if not temp_ok or not ph_ok:
            p.stress_timer += 1
            p.state = "stressed"
        else:
            p.stress_timer = max(0, p.stress_timer - 2)
            if p.stress_timer == 0:
                p.state = "healthy"

        if p.stress_timer > 180:
            p.state = "dead"
            continue

        if nutrients <= 5.0:
            p.stress_timer += 1
            p.state = "stressed"
            continue

        # ── MECANISMO 1: Toxinas ──────────────────────────────────────────
        # Los nativos cerca de invasores tienen prob de ser envenenados
        if not is_invader and invader_positions is not None and len(invader_positions) > 0:
            diff    = invader_positions - p.pos
            dists_sq = (diff * diff).sum(axis=1)
            nearby  = np.any(dists_sq < TOXIN_RADIUS_SQ)
            if nearby and random.random() < TOXIN_PROB:
                p.stress_timer += 8
                p.state = "stressed"
                p.glow  = 0.6   # brillo rojizo al ser envenenado

        # ── MECANISMO 3: Cascada de colapso ──────────────────────────────
        # Si invasor supera 40%, nativos se estresan más rápido
        if not is_invader and invasion_ratio >= CASCADE_THRESH:
            extra_stress = int((invasion_ratio - CASCADE_THRESH) * 20)
            p.stress_timer += extra_stress
            if p.stress_timer > 0:
                p.state = "stressed"

        if p.stress_timer > 180:
            p.state = "dead"
            continue

        # ── Reproducción ─────────────────────────────────────────────────
        if p.state == "healthy":
            growth = growth_invader if is_invader else growth_native
            cost   = nutrient_cost_invader if is_invader else nutrient_cost_native

            if len(particles) + len(new_bacteria) < max_particles:
                if len(new_bacteria) < 12:
                    if random.random() < growth:
                        new_bacteria.append(Particle(
                            p.pos[0] + random.uniform(-25, 25),
                            p.pos[1] + random.uniform(-25, 25),
                            is_bacteria=True,
                            microbe_key=p.microbe_key  # ← hereda su propio tipo
                        ))
                        # ── MECANISMO 2: Competencia por nutrientes ───────
                        nutrients -= cost  # invasor consume 3x más

    particles[:] = [p for p in particles if p.state != "dead"]
    particles.extend(new_bacteria)
    return max(0.0, nutrients)

def contaminate(particles, current_w, current_h, invader_key, count=25):
    """
    Agrega bacterias invasoras en una zona aleatoria con efecto de invasión.
    """
    # Zona aleatoria de aparición (evita bordes)
    zone_x = random.randint(current_w // 5, current_w * 4 // 5)
    zone_y = random.randint(current_h // 5, current_h * 4 // 5)
    zone_r = 80  # radio de la zona de invasión

    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi)
        dist  = random.uniform(0, zone_r)
        x = zone_x + math.cos(angle) * dist
        y = zone_y + math.sin(angle) * dist

        p = Particle(x, y, is_bacteria=True, microbe_key=invader_key)
        p.vel   = np.array([random.uniform(-120, 120),
                            random.uniform(-120, 120)])
        p.glow  = 1.5   # brillo máximo al aparecer
        p.state = "healthy"
        particles.append(p)

    # Partículas de explosión visual en el centro de la zona
    create_explosion(particles, zone_x, zone_y,
                     count=18, intensity=0.5, microbe_key=invader_key)