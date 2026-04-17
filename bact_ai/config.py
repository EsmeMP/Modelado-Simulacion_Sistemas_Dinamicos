# Constantes, colores, tamaño de ventana, etc.

# ========================
# config inicial

import pygame

# ------------------- ventana -------------------
WIDTH, HEIGHT = 1280, 820
FPS = 60

# ------------------- colores -------------------
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
RED = (255, 70, 70)
GREEN = (70, 255, 70)
YELLOW = (255, 255, 100)
PURPLE = (200, 100, 255)
ORANGE = (255, 165, 0)
BLUE = (70, 130, 255)
GRAY = (100, 100, 100)
LIGHT_GRAY = (180, 180, 180)

# ------------------- parametros de simulación -------------------
MAX_PARTICLES = 1800
INITIAL_PARTICLES = 480
DAMPING = 0.955
DT = 0.016

# ------------------- Gestos -------------------
MIN_DETECTION_CONFIDENCE = 0.78
MIN_TRACKING_CONFIDENCE = 0.78

# ------------------- UI -------------------
FONT_SIZE = 22
BIG_FONT_SIZE = 32
INFO_X = 25
INFO_Y_START = 80
LINE_SPACING = 40

# inicializa pygame (se llama solo una vez)
pygame.init()
font = pygame.font.SysFont("Arial", FONT_SIZE)
big_font = pygame.font.SysFont("Arial", BIG_FONT_SIZE)