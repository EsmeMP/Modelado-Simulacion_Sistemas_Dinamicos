
# SIMULATION.PY - logica de particulas y crecimiento bacteriano
# =========================

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

        # config segun microbio
        data = get_microbe_data(microbe_key)
        self.color = data["color"] if data and is_bacteria else CYAN
        self.size = 5.5 if is_bacteria else 4.5
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
        color = RED if self.state == "infected" else self.color
        if self.collision_timer > 0:
            color = YELLOW

        # Glow effect
        if self.glow > 0.08:
            glow_size = int(self.size * 2.4)
            glow_surf = pygame.Surface((glow_size*2, glow_size*2), pygame.SRCALPHA)
            alpha = int(45 * self.glow)
            pygame.draw.circle(glow_surf, (*color[:3], alpha), (glow_size, glow_size), glow_size)
            surface.blit(glow_surf, (int(self.pos[0]) - glow_size, int(self.pos[1]) - glow_size))

        # Partícula principal
        pygame.draw.circle(surface, color, (int(self.pos[0]), int(self.pos[1])), int(self.size))


# ========================
# FUNCIONES DE SIMULACIÓN
# ========================

def create_explosion(particles_list, x, y, count=35, intensity=1.0):
    """Crea partículas de explosión con mucho brillo"""
    for _ in range(count):
        p = Particle(x, y, is_bacteria=False)
        p.vel = np.array([
            random.uniform(-300, 300) * intensity,
            random.uniform(-300, 300) * intensity
        ])
        p.glow = 1.2
        p.size = random.uniform(3.5, 7.5)
        particles_list.append(p)


def handle_collisions(particles, max_checks=700):
    """colisiones optimizadas: solo cuando hay pocas particulas"""
    n = len(particles)
    if n > max_checks:
        return  # se salta colisiones cuando hay muchas (prioridades en crecimiento)

    for i in range(n):
        for j in range(i + 1, n):   # se evita comprobar dos veces la misma pareja
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

                impulse = -1.6 * rv / 2.0
                p1.vel -= impulse * np.array([nx, ny])
                p2.vel += impulse * np.array([nx, ny])

                p1.collision_timer = p2.collision_timer = 5


def update_bacteria_growth(particles, temp, humidity, microbe_key, max_particles):
    """añade nuevas bacterias segun tasa de crecimiento realista"""
    if not particles:
        return

    growth_rate = calculate_growth_rate(temp, humidity, microbe_key)

    # probabilidad por particula bacteriana
    for p in particles:
        if p.is_bacteria and random.random() < growth_rate:
            if len(particles) >= max_particles:
                break
            # Crear bacteria hija cerca de la madre
            offset_x = random.uniform(-22, 22)
            offset_y = random.uniform(-22, 22)
            
            new_p = Particle(
                p.pos[0] + offset_x,
                p.pos[1] + offset_y,
                is_bacteria=True,
                microbe_key=microbe_key
            )
            particles.append(new_p)