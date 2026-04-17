# ========================
# GESTURES.PY - deteccion y manejo de gestos con MediaPipe
# ========================

import cv2
import mediapipe as mp
import numpy as np
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

    def process_gestures(self, result, current_w, current_h, temp, humidity, current_microbe):
        """
        Procesa todos los gestos y devuelve:
        - hand_forces (para fisica)
        - nuevos valores de temp, humidity, microbe
        - gesture_text
        - vortex_centers
        """
        hand_forces = []
        vortex_centers = []
        gesture_text = "Esperando manos..."
        
        current_time = pygame.time.get_ticks()
        
        if not result.multi_hand_landmarks:
            return hand_forces, vortex_centers, temp, humidity, current_microbe, gesture_text

        for hand_landmarks in result.multi_hand_landmarks:
            # posicion de la palma
            palm = hand_landmarks.landmark[0]
            hx = int(palm.x * current_w)
            hy = int(palm.y * current_h)
            hand_pos = np.array([hx, hy], dtype=float)

            # conteo de dedos levantados
            dedos = sum(1 for i in [8, 12, 16, 20] 
                       if hand_landmarks.landmark[i].y < hand_landmarks.landmark[i-2].y)
            
            thumb_up = hand_landmarks.landmark[4].y < hand_landmarks.landmark[2].y - 0.05
            dist_thumb_index = abs(hand_landmarks.landmark[4].x - hand_landmarks.landmark[8].x) * 120

            is_attract = True

            # ======================== GESTOS PRINCIPALES ========================
            
            if dedos == 4 and thumb_up:                  # mano abierta + pulgar arriba → Cambiar microbio
                if current_time - self.last_gesture_time > self.gesture_cooldown:
                    self.current_microbe_index = (self.current_microbe_index + 1) % len(self.microbe_list)
                    current_microbe = self.microbe_list[self.current_microbe_index]
                    gesture_text = f"Microbio: {current_microbe}"
                    self.last_gesture_time = current_time

            elif dedos == 3:                             # 3 dedos → toggle modo bacterias (se maneja en main)
                gesture_text = "Modo Bacterias (toggle en main)"

            elif dedos == 2:                             # victoria → Vortice
                vortex_centers.append(hand_pos)
                gesture_text = "¡VÓRTICE ACTIVADO!"

            elif dedos == 1:                             # solo indice → Ajustar Temp / Humedad
                if hx < current_w // 2:                  # mano izquierda de la pantalla = Temperatura
                    temp = np.clip(temp + (dist_thumb_index - 35) * 0.085, 0, 55)
                    gesture_text = f"Temperatura: {temp:.1f}°C"
                else:                                    # Mano derecha = Humedad
                    humidity = np.clip(humidity + (dist_thumb_index - 35) * 0.18, 10, 100)
                    gesture_text = f"Humedad: {humidity:.0f}%"

            elif thumb_up and dedos <= 1:                # Pulgar arriba (casi puño) → +1 Dia
                if current_time - self.last_gesture_time > self.gesture_cooldown:
                    gesture_text = "¡+1 Día simulado!"
                    self.last_gesture_time = current_time
                    # El +1 día se maneja en main.py

            elif dedos == 0 and not thumb_up:            # Puño cerrado → Repulsion + Explosion
                is_attract = False
                gesture_text = "Repulsión + Onda"
            
            elif dedos == 4:                             # Mano casi abierta → Atraccion fuerte
                is_attract = True
                gesture_text = "Atracción + Glow"

            # Añadir fuerza de esta mano
            hand_forces.append((hand_pos, is_attract, dist_thumb_index))

        return hand_forces, vortex_centers, temp, humidity, current_microbe, gesture_text

    def release(self):
        """Libera la camara"""
        if self.cap is not None:
            self.cap.release()