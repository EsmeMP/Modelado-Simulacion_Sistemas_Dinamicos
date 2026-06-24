# ========================
# SIMULATION.PY - Lógica de partículas y crecimiento con 5 factores
# ========================
# FIXES CRÍTICOS APLICADOS:
#   [1] handle_collisions: O(n²) → spatial hashing O(n) promedio
#   [2] Particle.update: p.speed cacheado como atributo (evita norm doble en main.py y draw())
#   [3] update_bacteria_growth: 6 sum() separados → 1 sola pasada sobre particles
#   [4] _capsule_cache: phase discretizada (16 fases) → 16x menos Surface() creadas
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

# ========================
# CACHÉ DE SUPERFICIES
# ========================

_capsule_cache = {}

def _get_capsule_surf(color, cap_w, cap_h, state):
    """
    Devuelve una Surface de cápsula cacheada.
    Solo regenera si la combinación color+tamaño+estado no existe.
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

    hl_rect = pygame.Rect(cx - cap_w // 2 + 2,
                          cy - cap_h // 2 + 1,
                          cap_w - 4, max(2, cap_h // 3))
    hcol = tuple(min(255, c + 90) for c in color[:3])
    hl   = pygame.Surface((hl_rect.width, hl_rect.height), pygame.SRCALPHA)
    pygame.draw.rect(hl, (*hcol, 80), hl.get_rect(),
                     border_radius=int(cap_h // 3))
    surf.blit(hl, (hl_rect.x, hl_rect.y))

    dot = pygame.Surface((4, 4), pygame.SRCALPHA)
    pygame.draw.circle(dot, (255, 255, 255, 60), (2, 2), 2)
    surf.blit(dot, (cx - 2, cy - 2))

    if len(_capsule_cache) > 80:
        _capsule_cache.clear()

    _capsule_cache[key] = surf
    return surf


# ========================
# CLASE PARTICLE
# ========================

class Particle:
    def __init__(self, x, y, is_bacteria=False, microbe_key="E. coli"):
        self.pos             = np.array([float(x), float(y)])
        self.vel             = np.array([random.uniform(-90, 90), random.uniform(-90, 90)])
        self.state           = "healthy" if is_bacteria else "normal"
        self.age             = 0
        self.max_age         = None if is_bacteria else 60
        self.collision_timer = 0
        self.glow            = 0.0
        self.stress_timer    = 0
        # ── [FIX 2] speed cacheado — calculado en update(), leído en draw() y main.py ──
        self.speed           = 0.0

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

        # ── [FIX 2] calcular speed una sola vez y guardarlo ──────────────────
        # Usamos dot product en lugar de linalg.norm para evitar import lookup
        self.speed = float(np.dot(self.vel, self.vel) ** 0.5)

        # Movimiento browniano — solo si velocidad muy baja
        if self.speed < 15:
            self.vel[0] += random.uniform(-18.0, 18.0)
            self.vel[1] += random.uniform(-18.0, 18.0)
            # Recalcular speed si cambiamos vel
            self.speed = float(np.dot(self.vel, self.vel) ** 0.5)

        if self.collision_timer > 0:
            self.collision_timer -= 1
        if self.glow > 0:
            self.glow *= 0.92
        if self.max_age is not None and self.age >= self.max_age:
            self.state = "dead"

    # ── Helpers de dibujo ─────────────────────────────────────────────────

    def _base_color(self):
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

    # ── [FIX 4] phase discretizada: 16 buckets en lugar de self.age continuo ─
    @property
    def _phase_bucket(self):
        return (self.age // 4) % 16

    def _draw_flagelo_ondulado(self, surface, start_x, start_y,
                               angle_base, length, color, segments=6):
        alpha_col = tuple(color[:3])
        px, py = float(start_x), float(start_y)
        seg_len = length / segments
        wave_amp = seg_len * 0.55
        wave_freq = 0.055
        phase = self._phase_bucket * (2 * math.pi / 16)   # fase discreta

        for k in range(segments):
            wave = wave_amp * math.sin(wave_freq * k * 20 + phase)
            seg_angle = angle_base + math.radians(wave * 6)
            nx2 = px + math.cos(seg_angle) * seg_len
            ny2 = py + math.sin(seg_angle) * seg_len
            thickness = max(1, 2 - k // 3)
            pygame.draw.line(surface, alpha_col,
                             (int(px), int(py)),
                             (int(nx2), int(ny2)),
                             thickness)
            px, py = nx2, ny2

    # ── Métodos de dibujo por forma ──────────────────────────────────────

    def _draw_bacilo_peritrico(self, surface, ix, iy, size, color, angle_rad):
        cap_w = int(size * 2.8)
        cap_h = int(size * 1.2)

        cap_surf, cx, cy = self._capsule_surf(color, cap_w, cap_h)

        flag_color = tuple(max(0, c - 40) for c in color[:3])
        flag_len   = int(size * 4.5)
        flag_segs  = 7
        # ── [FIX 4] phase discreta ────────────────────────────────────────
        phase_off  = self._phase_bucket * (2 * math.pi / 16)

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

        rotated = pygame.transform.rotate(cap_surf, -np.degrees(angle_rad))
        surface.blit(rotated, rotated.get_rect(center=(ix, iy)))

    def _draw_bacilo_polar(self, surface, ix, iy, size, color, angle_rad):
        cap_w = int(size * 2.6)
        cap_h = int(size * 1.1)

        cap_surf, cx, cy = self._capsule_surf(color, cap_w, cap_h)

        flag_color = tuple(max(0, c - 50) for c in color[:3])
        flag_len   = int(size * 6.5)
        flag_segs  = 9
        phase_off  = self._phase_bucket * (2 * math.pi / 16)

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
        sz = int(size * 0.95)
        pygame.draw.circle(surface, color, (ix, iy), sz)

        if self.state == "healthy":
            bcol = tuple(min(255, c + 70) for c in color[:3])
            pygame.draw.circle(surface, bcol, (ix, iy), sz, 1)
        else:
            pygame.draw.circle(surface, RED, (ix, iy), sz, 2)

        hx = ix - sz // 3
        hy = iy - sz // 3
        hr = max(2, sz // 3)
        hs = pygame.Surface((hr * 2, hr * 2), pygame.SRCALPHA)
        pygame.draw.circle(hs, (255, 255, 255, 55), (hr, hr), hr)
        surface.blit(hs, (hx - hr, hy - hr))

        # ── [FIX 4] ángulo discretizado también ──────────────────────────
        offset    = int(sz * 1.5)
        off_angle = (self._phase_bucket / 16.0) * 2 * math.pi
        ox = ix + int(math.cos(off_angle) * offset)
        oy = iy + int(math.sin(off_angle) * offset)
        sz2 = max(3, int(sz * 0.8))
        scol = tuple(max(0, c - 30) for c in color[:3])
        bcol = tuple(min(255, c + 70) for c in color[:3])
        pygame.draw.circle(surface, scol, (ox, oy), sz2)
        pygame.draw.circle(surface, bcol if self.state == "healthy" else RED,
                           (ox, oy), sz2, 1)

    def _draw_virus(self, surface, ix, iy, size, color):
        sz = int(size * 0.9)
        pygame.draw.circle(surface, color, (ix, iy), sz)

        if self.state == "healthy":
            bcol = tuple(min(255, c + 80) for c in color[:3])
            pygame.draw.circle(surface, bcol, (ix, iy), sz, 1)
        else:
            pygame.draw.circle(surface, RED, (ix, iy), sz, 2)

        hs = pygame.Surface((sz, sz), pygame.SRCALPHA)
        pygame.draw.circle(hs, (255, 255, 255, 50), (sz // 3, sz // 3), sz // 3)
        surface.blit(hs, (ix - sz // 2, iy - sz // 2))

        num_spikes = 10
        spike_len  = int(size * 1.4)
        spike_col  = tuple(min(255, c + 50) for c in color[:3])
        # ── [FIX 4] rotación discreta (16 pasos) ─────────────────────────
        rotation   = self._phase_bucket * (360 / 16)

        for k in range(num_spikes):
            angle = math.radians(k * (360 / num_spikes) + rotation)
            sx1   = ix + int(math.cos(angle) * sz)
            sy1   = iy + int(math.sin(angle) * sz)
            sx2   = ix + int(math.cos(angle) * (sz + spike_len))
            sy2   = iy + int(math.sin(angle) * (sz + spike_len))
            pygame.draw.line(surface, spike_col, (sx1, sy1), (sx2, sy2), 2)
            pygame.draw.circle(surface, spike_col, (sx2, sy2), 2)

    # ── Método draw principal ─────────────────────────────────────────────

    def draw(self, surface):
        if self.state == "dead":
            return

        color = self._base_color()
        size  = max(2.5, self.size * 0.75) if self.state == "stressed" else self.size
        ix, iy = int(self.pos[0]), int(self.pos[1])

        self._draw_glow(surface, ix, iy, size, color)

        # ── [FIX 2] usar p.speed ya calculado, sin llamar norm de nuevo ──────
        spd       = self.speed
        angle_rad = np.arctan2(self.vel[1], self.vel[0]) if spd > 1 else 0.0

        if self.shape == "bacilo_peritrico":
            self._draw_bacilo_peritrico(surface, ix, iy, size, color, angle_rad)
        elif self.shape == "bacilo_polar":
            self._draw_bacilo_polar(surface, ix, iy, size, color, angle_rad)
        elif self.shape == "coco":
            self._draw_coco(surface, ix, iy, size, color)
        elif self.shape == "virus":
            self._draw_virus(surface, ix, iy, size, color)
        else:
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
        p.color = color
        particles_list.append(p)


# ── [FIX 1] handle_collisions: spatial hashing O(n) promedio ─────────────────

def handle_collisions(particles, cell_size=30):
    """
    Spatial hashing: divide el espacio en celdas de cell_size px.
    Solo se comprueban pares en celdas vecinas (3×3 = 9 celdas).
    Complejidad: O(n) promedio vs O(n²) anterior.
    """
    if len(particles) < 2:
        return

    # Construir grid: celda → lista de índices
    grid = {}
    for i, p in enumerate(particles):
        cx = int(p.pos[0] / cell_size)
        cy = int(p.pos[1] / cell_size)
        key = (cx, cy)
        if key not in grid:
            grid[key] = []
        grid[key].append(i)

    checked = set()

    for (gcx, gcy), cell_indices in grid.items():
        # Recopilar candidatos de la celda actual + 8 vecinas
        candidates = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                neighbor = (gcx + dx, gcy + dy)
                if neighbor in grid:
                    candidates.extend(grid[neighbor])

        # Comprobar pares dentro de candidatos
        n = len(candidates)
        for a in range(n):
            for b in range(a + 1, n):
                i = candidates[a]
                j = candidates[b]
                if i >= j:
                    continue
                pair = (i, j)
                if pair in checked:
                    continue
                checked.add(pair)

                p1 = particles[i]
                p2 = particles[j]
                dx = p2.pos[0] - p1.pos[0]
                dy = p2.pos[1] - p1.pos[1]
                dist_sq = dx * dx + dy * dy
                min_dist_sq = (p1.size + p2.size) ** 2

                if dist_sq < min_dist_sq and dist_sq > 0.001:
                    dist = math.sqrt(dist_sq)
                    nx, ny = dx / dist, dy / dist
                    rv = (p2.vel[0] - p1.vel[0]) * nx + (p2.vel[1] - p1.vel[1]) * ny
                    if rv > 0:
                        continue
                    impulse = -1.65 * rv / 2.0
                    imp_vec = np.array([nx * impulse, ny * impulse])
                    p1.vel -= imp_vec
                    p2.vel += imp_vec
                    p1.collision_timer = p2.collision_timer = 3


# ── [FIX 3] update_bacteria_growth: 1 pasada única en lugar de 6 sum() ───────

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

    # ── [FIX 3] Una sola pasada para contar y recopilar posiciones ────────────
    total    = 0
    invaders = 0
    _found_key = None
    invader_pos_list = []

    for p in particles:
        if not p.is_bacteria:
            continue
        total += 1
        if p.microbe_key != microbe_key and p.state != "dead":
            invaders += 1
            invader_pos_list.append(p.pos)
            if _found_key is None:
                _found_key = p.microbe_key

    natives        = total - invaders
    invasion_ratio = invaders / total if total > 0 else 0.0
    invasion_active = invaders > 0

    if _found_key is not None:
        invasion_key = _found_key
    elif invaders == 0:
        invasion_key = None

    invader_positions = np.array(invader_pos_list) if invader_pos_list else None

    # ── Datos de ambos tipos ──────────────────────────────────────────────────
    data_native  = get_microbe_data(microbe_key)
    data_invader = get_microbe_data(invasion_key) if invasion_key else None
    if not data_native:
        return nutrients

    growth_native  = calculate_growth_rate(temp, humidity, ph, light, nutrients, microbe_key)
    growth_invader = calculate_growth_rate(temp, humidity, ph, light, nutrients, invasion_key) \
                     if invasion_key else 0.0

    nutrient_cost_native  = data_native.get("nutrient_consumption", 0.005)
    nutrient_cost_invader = (data_invader.get("nutrient_consumption", 0.005) * 3.0) \
                             if data_invader else 0.0

    TOXIN_RADIUS    = 55.0
    TOXIN_RADIUS_SQ = TOXIN_RADIUS ** 2
    TOXIN_PROB      = 0.012
    CASCADE_THRESH  = 0.40

    new_bacteria = []

    for p in particles:
        if not p.is_bacteria:
            continue

        is_invader = p.microbe_key != microbe_key
        data       = data_invader if is_invader else data_native

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

        # Toxinas
        if not is_invader and invader_positions is not None and len(invader_positions) > 0:
            diff     = invader_positions - p.pos
            dists_sq = (diff * diff).sum(axis=1)
            nearby   = np.any(dists_sq < TOXIN_RADIUS_SQ)
            if nearby and random.random() < TOXIN_PROB:
                p.stress_timer += 8
                p.state = "stressed"
                p.glow  = 0.6

        # Cascada de colapso
        if not is_invader and invasion_ratio >= CASCADE_THRESH:
            extra_stress = int((invasion_ratio - CASCADE_THRESH) * 20)
            p.stress_timer += extra_stress
            if p.stress_timer > 0:
                p.state = "stressed"

        if p.stress_timer > 180:
            p.state = "dead"
            continue

        # Reproducción
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
                            microbe_key=p.microbe_key
                        ))
                        nutrients -= cost

    particles[:] = [p for p in particles if p.state != "dead"]
    particles.extend(new_bacteria)
    return max(0.0, nutrients)


def contaminate(particles, current_w, current_h, invader_key, count=25):
    """Agrega bacterias invasoras en una zona aleatoria."""
    zone_x = random.randint(current_w // 5, current_w * 4 // 5)
    zone_y = random.randint(current_h // 5, current_h * 4 // 5)
    zone_r = 80

    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi)
        dist  = random.uniform(0, zone_r)
        x = zone_x + math.cos(angle) * dist
        y = zone_y + math.sin(angle) * dist

        p = Particle(x, y, is_bacteria=True, microbe_key=invader_key)
        p.vel   = np.array([random.uniform(-120, 120),
                            random.uniform(-120, 120)])
        p.glow  = 1.5
        p.state = "healthy"
        particles.append(p)

    create_explosion(particles, zone_x, zone_y,
                     count=18, intensity=0.5, microbe_key=invader_key)