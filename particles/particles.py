import numpy as np
import random

MIN_PARTICLES = 50
MAX_PARTICLES = 1000

sim_width  = 900
sim_height = 700

num_particles  = 600
particles      = None
velocities     = None
prev_positions = None
pcolors        = None
grabbed        = None
trail          = None

def init(n=600):
    global num_particles, particles, velocities, prev_positions, pcolors, grabbed, trail
    num_particles  = n
    particles      = np.random.rand(n, 2) * [sim_width, sim_height]
    velocities     = np.zeros((n, 2))
    prev_positions = particles.copy()
    pcolors        = [(random.randint(150,255), random.randint(150,255), random.randint(150,255))
                      for _ in range(n)]
    grabbed        = [False] * n
    trail          = np.zeros((sim_height, sim_width, 3), dtype=np.uint8)

def set_count(new_n):
    global num_particles, particles, velocities, prev_positions, pcolors, grabbed, trail
    new_n = int(np.clip(new_n, MIN_PARTICLES, MAX_PARTICLES))
    if new_n == num_particles:
        return
    if new_n > num_particles:
        extra   = new_n - num_particles
        extra_p = np.random.rand(extra, 2) * [sim_width, sim_height]
        extra_v = np.zeros((extra, 2))
        particles      = np.vstack([particles, extra_p])
        velocities     = np.vstack([velocities, extra_v])
        prev_positions = np.vstack([prev_positions, extra_p])
        pcolors += [(random.randint(150,255), random.randint(150,255), random.randint(150,255))
                    for _ in range(extra)]
        grabbed += [False] * extra
    else:
        particles      = particles[:new_n]
        velocities     = velocities[:new_n]
        prev_positions = prev_positions[:new_n]
        pcolors        = pcolors[:new_n]
        grabbed        = grabbed[:new_n]
    num_particles = new_n
    trail[:] = 0