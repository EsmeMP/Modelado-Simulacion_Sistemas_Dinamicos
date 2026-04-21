# ========================
# GESTURES.PY - deteccion y manejo de gestos con MediaPipe
# ========================

import cv2
import mediapipe as mp
import numpy as np
import pygame
from config import *
from microbes import get_all_microbes


class GestureController:
    def __init__(self):
        self.mp_hands = mp.solutions.hands
        self.hands_detector = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=MIN_DETECTION_CONFIDENCE,
            min_tracking_confidence=MIN_TRACKING_CONFIDENCE,
            model_complexity=0
        )
        self.mp_draw = mp.solutions.drawing_utils
        self.cap = cv2.VideoCapture(0)
        
        # variables de estado
        self.current_microbe_index = 0
        self.microbe_list = get_all_microbes()
        
        # para evitar toggles rápidos
        self.last_gesture_time = 0
        self.gesture_cooldown = 300  # milisegundos

    def get_frame(self):
        """captura y procesa un frame de la camara"""
        ret, frame = self.cap.read()
        if not ret:
            return None, None
        
        frame = cv2.flip(frame, 1)  # espejo
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.hands_detector.process(rgb)
        
        return frame, result

    def draw_landmarks(self, frame, result):
        """dibuja los landmarks en el frame de la camara"""
        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(
                    frame, 
                    hand_landmarks, 
                    self.mp_hands.HAND_CONNECTIONS
                )
        return frame

    def process_gestures(self, result, current_w, current_h, temp, humidity, ph, light, current_microbe):
        hand_forces = []
        vortex_centers = []
        gesture_text = "Esperando manos..."

        current_time = pygame.time.get_ticks()

        if not result.multi_hand_landmarks:
            return hand_forces, vortex_centers, temp, humidity, ph, light, current_microbe, gesture_text

        for hand_landmarks in result.multi_hand_landmarks:
            palm = hand_landmarks.landmark[0]
            hx = int(palm.x * current_w)
            hy = int(palm.y * current_h)
            hand_pos = np.array([hx, hy], dtype=float)

            dedos_arriba = sum(1 for i in [8, 12, 16, 20]
                            if hand_landmarks.landmark[i].y < hand_landmarks.landmark[i-2].y - 0.02)

            thumb_up = hand_landmarks.landmark[4].y < hand_landmarks.landmark[2].y - 0.08
            dist_thumb_index = abs(hand_landmarks.landmark[4].x - hand_landmarks.landmark[8].x) * 130

            # =================== GESTOS ===================

            if dedos_arriba == 1:
                # Posición Y normalizada: arriba = 1.0, abajo = 0.0
                normalized_y = 1.0 - (hy / current_h)

                if hx < current_w // 2:          # mano izquierda → Temperatura
                    temp = np.clip(normalized_y * 60, 0, 60)
                    gesture_text = f"🌡 Temp: {temp:.1f}°C"
                else:                             # mano derecha → Humedad
                    humidity = np.clip(normalized_y * 95 + 5, 5, 100)
                    gesture_text = f"💧 Humedad: {humidity:.0f}%"

            elif dedos_arriba == 2:                     # 2 dedos → Vórtice
                vortex_centers.append(hand_pos)
                gesture_text = "VÓRTICE ACTIVADO"

            elif dedos_arriba == 3:               # 3 dedos → pH
                normalized_y = 1.0 - (hy / current_h)
                ph = np.clip(normalized_y * 5 + 4, 4.0, 9.0)   # mapea 0-1 → 4.0-9.0
                gesture_text = f"⚗ pH: {ph:.2f}  (sube/baja mano)"

            elif dedos_arriba == 4:                     # 4 dedos → Luz UV
                # altura de la mano controla la luz: arriba = más luz
                normalized_y = 1.0 - (hy / current_h)
                light = np.clip(normalized_y * 100, 0, 100)
                gesture_text = f"☀ Luz UV: {light:.0f}%  (sube/baja mano)"

            elif thumb_up and dedos_arriba <= 1:        # Pulgar → +1 Día
                if current_time - self.last_gesture_time > self.gesture_cooldown:
                    gesture_text = "¡+1 Día simulado!"
                    self.last_gesture_time = current_time

            elif dedos_arriba == 0:                     # Puño → Repulsión
                gesture_text = "Repulsión activa"

            is_attract = dedos_arriba >= 1
            hand_forces.append((hand_pos, is_attract, dist_thumb_index))

        return hand_forces, vortex_centers, temp, humidity, ph, light, current_microbe, gesture_text

    def release(self):
        """Libera la camara"""
        if self.cap is not None:
            self.cap.release()