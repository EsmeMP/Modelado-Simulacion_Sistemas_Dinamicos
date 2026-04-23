# ========================
# SIMULATION.PY - Lógica de partículas y crecimiento con 5 factores
# ========================

import pygame
import math
import random
import numpy as np
from config import *
from microbes import calculate_growth_rate, get_microbe_data


class Particle:
    def __init__(self, x, y, is_bacteria=False, microbe_key="E. coli"):
        self.pos          = np.array([float(x), float(y)])
        self.vel          = np.array([random.uniform(-90, 90), random.uniform(-90, 90)])
        self.state        = "healthy" if is_bacteria else "normal"
        self.age          = 0
        self.collision_timer = 0
        self.glow         = 0.0
        self.stress_timer = 0

        data = get_microbe_data(microbe_key)
        self.color       = data["color"] if data and is_bacteria else CYAN
        self.size        = 6.8 if is_bacteria else 4.5
        self.is_bacteria = is_bacteria
        self.microbe_key = microbe_key

    def update(self, force, dt, damping=DAMPING):
        self.vel += force * dt
        self.vel *= damping
        self.pos += self.vel * dt
        self.age += 1

        if self.collision_timer > 0:
            self.collision_timer -= 1
        if self.glow > 0:
            self.glow *= 0.92

    def draw(self, surface):
        if self.state == "dead":
            return

        # ── Color y parpadeo según estado ──
        if self.state == "stressed":
            color = ORANGE if (self.age // 8) % 2 == 0 else RED
        else:
            color = self.color

        # Colisión: aclarar levemente el color, no amarillo puro
        if self.collision_timer > 0:
            color = tuple(min(255, c + 40) for c in color[:3])

        # ── Tamaño según estado ──
        size = max(2.5, self.size * 0.75) if self.state == "stressed" else self.size
        ix, iy = int(self.pos[0]), int(self.pos[1])

        # ── Glow al reproducirse ──
        if self.glow > 0.08:
            glow_r = int(size * 2.5)
            gs = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*color[:3], int(55 * self.glow)),
                               (glow_r, glow_r), glow_r)
            surface.blit(gs, (ix - glow_r, iy - glow_r))

        # ── Forma de cápsula rotada según velocidad ──
        speed = np.linalg.norm(self.vel)
        angle_rad = np.arctan2(self.vel[1], self.vel[0]) if speed > 1 else 0.0

        cap_w = int(size * 2.6)
        cap_h = int(size * 1.2)

        cap_surf = pygame.Surface((cap_w + 4, cap_h + 4), pygame.SRCALPHA)
        cx = (cap_w + 4) // 2
        cy = (cap_h + 4) // 2
        cap_rect = pygame.Rect(cx - cap_w // 2, cy - cap_h // 2, cap_w, cap_h)

        # Cuerpo principal
        pygame.draw.rect(cap_surf, color, cap_rect,
                         border_radius=int(cap_h // 2))

        # Borde según estado
        if self.state == "healthy":
            border_col = tuple(min(255, c + 70) for c in color[:3])
            pygame.draw.rect(cap_surf, border_col, cap_rect,
                             1, border_radius=int(cap_h // 2))
        else:
            pygame.draw.rect(cap_surf, RED, cap_rect,
                             2, border_radius=int(cap_h // 2))

        # Highlight interior — efecto 3D
        hl_rect = pygame.Rect(cx - cap_w // 2 + 2,
                              cy - cap_h // 2 + 1,
                              cap_w - 4,
                              max(2, cap_h // 3))
        highlight_col = tuple(min(255, c + 90) for c in color[:3])
        hl_surf = pygame.Surface((hl_rect.width, hl_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(hl_surf, (*highlight_col, 80),
                         hl_surf.get_rect(),
                         border_radius=int(cap_h // 3))
        cap_surf.blit(hl_surf, (hl_rect.x, hl_rect.y))

        # Punto de brillo central
        dot_surf = pygame.Surface((4, 4), pygame.SRCALPHA)
        pygame.draw.circle(dot_surf, (255, 255, 255, 60), (2, 2), 2)
        cap_surf.blit(dot_surf, (cx - 2, cy - 2))

        # Rotar y dibujar
        angle_deg = -np.degrees(angle_rad)
        rotated = pygame.transform.rotate(cap_surf, angle_deg)
        surface.blit(rotated, rotated.get_rect(center=(ix, iy)))


# ========================
# FUNCIONES DE SIMULACIÓN
# ========================

def create_explosion(particles_list, x, y, count=35, intensity=1.0):
    """Crea partículas de explosión con brillo"""
    for _ in range(count):
        p = Particle(x, y, is_bacteria=False)
        p.vel = np.array([
            random.uniform(-300, 300) * intensity,
            random.uniform(-300, 300) * intensity
        ])
        p.glow = 1.3
        p.size = random.uniform(3.5, 8.0)
        particles_list.append(p)


def handle_collisions(particles, max_checks=700):
    """Colisiones optimizadas con collision_timer reducido"""
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

                # FIX: reducido de 6 a 3 para menos amarillo en pantalla
                p1.collision_timer = p2.collision_timer = 3


def update_bacteria_growth(particles, temp, humidity, ph, light, nutrients,
                           microbe_key, max_particles):
    """
    Actualiza crecimiento bacteriano con 5 factores.
    Devuelve el nivel de nutrientes actualizado.
    """
    if not particles:
        return nutrients

    growth_rate  = calculate_growth_rate(temp, humidity, ph, light, nutrients, microbe_key)
    data         = get_microbe_data(microbe_key)
    if not data:
        return nutrients

    new_bacteria  = []
    nutrient_cost = data.get("nutrient_consumption", 0.005)

    for p in particles:
        if not p.is_bacteria:
            continue

        # Verificar condiciones límite de temperatura y pH
        temp_ok = data["temp_range"][0] <= temp <= data["temp_range"][1]
        ph_ok   = data["ph_range"][0]   <= ph   <= data["ph_range"][1]

        if not temp_ok or not ph_ok:
            p.stress_timer += 1
            p.state = "stressed"
        else:
            p.stress_timer = max(0, p.stress_timer - 2)
            if p.stress_timer == 0:
                p.state = "healthy"

        # Muere tras ~3 segundos de estrés continuo (180 frames a 60fps)
        if p.stress_timer > 180:
            p.state = "dead"
            continue

        # Sin nutrientes → estrés aunque las condiciones sean buenas
        if nutrients <= 5.0:
            p.stress_timer += 1
            p.state = "stressed"
            continue

        # Reproducción solo si healthy y hay espacio
        if p.state == "healthy":
            if len(particles) + len(new_bacteria) < max_particles:
                if len(new_bacteria) < 12:
                    if random.random() < growth_rate:
                        new_bacteria.append(Particle(
                            p.pos[0] + random.uniform(-25, 25),
                            p.pos[1] + random.uniform(-25, 25),
                            is_bacteria=True,
                            microbe_key=microbe_key
                        ))
                        nutrients -= nutrient_cost

    # Eliminar muertas y agregar nuevas — fuera del for
    particles[:] = [p for p in particles if p.state != "dead"]
    particles.extend(new_bacteria)

    return max(0.0, nutrients)