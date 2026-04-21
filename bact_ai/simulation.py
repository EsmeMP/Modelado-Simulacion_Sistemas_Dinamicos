# ========================
# SIMULATION.PY - Lógica de partículas y crecimiento con 4 factores
# ========================

import pygame
import math
import random
import numpy as np
from config import *
from microbes import calculate_growth_rate, get_microbe_data


class Particle:
    def __init__(self, x, y, is_bacteria=False, microbe_key="E. coli"):
        self.pos = np.array([float(x), float(y)])
        self.vel = np.array([random.uniform(-90, 90), random.uniform(-90, 90)])
        self.state = "healthy" if is_bacteria else "normal"
        self.age = 0
        self.collision_timer = 0
        self.glow = 0.0
        self.stress_timer = 0 

        # Configuración según microbio
        data = get_microbe_data(microbe_key)
        self.color = data["color"] if data and is_bacteria else CYAN
        self.size = 5.8 if is_bacteria else 4.5
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
    # Estado dead no se dibuja
        if self.state == "dead":
            return

        # Color según estado
        if self.state == "stressed":
            color = ORANGE
        elif self.collision_timer > 0:
            color = YELLOW
        else:
            color = self.color

        # Glow effect
        if self.glow > 0.08:
            glow_size = int(self.size * 2.4)
            glow_surf = pygame.Surface((glow_size*2, glow_size*2), pygame.SRCALPHA)
            alpha = int(48 * self.glow)
            pygame.draw.circle(glow_surf, (*color[:3], alpha), (glow_size, glow_size), glow_size)
            surface.blit(glow_surf, (int(self.pos[0]) - glow_size, int(self.pos[1]) - glow_size))

        pygame.draw.circle(surface, color, (int(self.pos[0]), int(self.pos[1])), int(self.size))

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
    """Colisiones optimizadas"""
    n = len(particles)
    if n > max_checks:
        return

    for i in range(n):
        for j in range(i + 1, n):
            p1 = particles[i]
            p2 = particles[j]

            dx = p2.pos[0] - p1.pos[0]
            dy = p2.pos[1] - p1.pos[1]
            dist_sq = dx*dx + dy*dy
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

                p1.collision_timer = p2.collision_timer = 6


def update_bacteria_growth(particles, temp, humidity, ph, light, microbe_key, max_particles):
    if not particles:
        return

    growth_rate = calculate_growth_rate(temp, humidity, ph, light, microbe_key)
    data = get_microbe_data(microbe_key)
    if not data:
        return

    new_bacteria = []

    for p in particles:
        if not p.is_bacteria:
            continue

        # Verificar condiciones límite
        temp_ok = data["temp_range"][0] <= temp <= data["temp_range"][1]
        ph_ok   = data["ph_range"][0]   <= ph   <= data["ph_range"][1]

        if not temp_ok or not ph_ok:
            p.stress_timer += 1
            p.state = "stressed"
        else:
            p.stress_timer = max(0, p.stress_timer - 2)  # se recupera más rápido de lo que se estresa
            if p.stress_timer == 0:
                p.state = "healthy"

        # Muere tras ~3 segundos en estrés continuo (180 frames a 60fps)
        if p.stress_timer > 180:
            p.state = "dead"
            continue

        # Solo se reproduce si está healthy y hay espacio
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

    # Eliminar muertas y agregar nuevas
    particles[:] = [p for p in particles if p.state != "dead"]
    particles.extend(new_bacteria)