# ========================
# GESTURES.PY - detección y manejo de gestos con MediaPipe
# Mejorado: anti-perfil, sensibilidad ajustada, gestos más estables
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
            min_detection_confidence=0.80,   
            min_tracking_confidence=0.75,    
            model_complexity=1               
        )
        self.mp_draw        = mp.solutions.drawing_utils
        self.cap            = cv2.VideoCapture(0)

        self.current_microbe_index = 0
        self.microbe_list          = get_all_microbes()
        self.last_gesture_time     = 0
        self.gesture_cooldown      = 350     # ms entre gestos

        # Suavizado de valores — evita saltos bruscos
        self._smooth_temp     = 25.0
        self._smooth_humidity = 50.0
        self._smooth_ph       = 7.0
        self._smooth_light    = 30.0
        self._alpha           = 0.15   # factor de suavizado (0=nada, 1=instantáneo)

        # Historial de dedos para estabilizar el conteo
        self._dedos_history   = []
        self._history_len     = 4       # frames para votar el gesto
        self.pause_triggered = False

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _smooth(self, current, target):
        """Exponential moving average para suavizar valores."""
        return current + self._alpha * (target - current)

    def _is_hand_frontal(self, hand_landmarks):
        """
        Detecta si la mano está de perfil.
        Compara el ancho visible de la palma — si es muy estrecha
        (relación ancho/alto < 0.3) probablemente es un perfil.
        Retorna True si la mano está de frente (válida).
        """
        # Puntos de referencia: base del meñique (17) y base del índice (5)
        p5  = hand_landmarks.landmark[5]
        p17 = hand_landmarks.landmark[17]
        p0  = hand_landmarks.landmark[0]   # muñeca
        p9  = hand_landmarks.landmark[9]   # medio de la palma

        ancho = abs(p5.x - p17.x)
        alto  = abs(p0.y - p9.y)

        if alto < 0.001:
            return False

        ratio = ancho / alto
        # Si la mano es muy estrecha → perfil → ignorar
        return ratio > 0.28

    def _count_fingers(self, hand_landmarks):
        """
        Cuenta dedos levantados con umbral más estricto.
        Requiere que el dedo esté claramente por encima de su nudillo.
        """
        dedos = 0
        # Índice, medio, anular, meñique
        for tip_id, pip_id in [(8, 6), (12, 10), (16, 14), (20, 18)]:
            tip = hand_landmarks.landmark[tip_id]
            pip = hand_landmarks.landmark[pip_id]
            # Umbral más estricto: 0.04 en vez de 0.02
            if tip.y < pip.y - 0.04:
                dedos += 1
        return dedos

    def _stable_finger_count(self, count):
        """
        Vota el conteo de dedos con historial para evitar flickering.
        Solo cambia el gesto si el mismo conteo aparece N veces seguidas.
        """
        self._dedos_history.append(count)
        if len(self._dedos_history) > self._history_len:
            self._dedos_history.pop(0)

        # Retornar el valor más frecuente en el historial
        if not self._dedos_history:
            return count
        return max(set(self._dedos_history),
                   key=self._dedos_history.count)

    # ── Métodos públicos ──────────────────────────────────────────────────────

    def get_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None, None
        frame = cv2.flip(frame, 1)
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.hands_detector.process(rgb)
        return frame, result

    def draw_landmarks(self, frame, result):
        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(
                    frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
        return frame

    def process_gestures(self, result, current_w, current_h,
                         temp, humidity, ph, light, current_microbe):
        hand_forces    = []
        vortex_centers = []
        gesture_text   = "Esperando manos..."
        current_time   = pygame.time.get_ticks()

        if not result.multi_hand_landmarks:
            self._dedos_history.clear()
            return hand_forces, vortex_centers, temp, humidity, ph, light, \
                   current_microbe, gesture_text

        for hand_landmarks in result.multi_hand_landmarks:

            # ── Anti-perfil: ignorar manos de costado ──
            if not self._is_hand_frontal(hand_landmarks):
                gesture_text = "Mano de perfil — gira hacia la cámara"
                continue

            palm     = hand_landmarks.landmark[0]
            hx       = int(palm.x * current_w)
            hy       = int(palm.y * current_h)
            hand_pos = np.array([hx, hy], dtype=float)

            # Conteo estable de dedos
            raw_count  = self._count_fingers(hand_landmarks)
            dedos_arriba = self._stable_finger_count(raw_count)

            # Pulgar — más estricto
            thumb_tip  = hand_landmarks.landmark[4]
            thumb_ip   = hand_landmarks.landmark[3]
            thumb_mcp  = hand_landmarks.landmark[2]
            thumb_up_strict = (
                thumb_tip.y < thumb_mcp.y - 0.14   
                and dedos_arriba == 0              
                and thumb_tip.y < thumb_ip.y       
            )

            dist_thumb_index = abs(
                hand_landmarks.landmark[4].x -
                hand_landmarks.landmark[8].x) * 130

            # ── GESTOS ──────────────────────────────────────────────────────

            if dedos_arriba == 1:
                normalized_y = 1.0 - (hy / current_h)
                if hx < current_w // 2:
                    # Izquierda → Temperatura
                    target = float(np.clip(normalized_y * 60, 0, 60))
                    self._smooth_temp = self._smooth(self._smooth_temp, target)
                    temp = self._smooth_temp
                    gesture_text = f"Temp: {temp:.1f}°C"
                else:
                    # Derecha → Humedad
                    target = float(np.clip(normalized_y * 95 + 5, 5, 100))
                    self._smooth_humidity = self._smooth(self._smooth_humidity, target)
                    humidity = self._smooth_humidity
                    gesture_text = f"Humedad: {humidity:.0f}%"

            elif dedos_arriba == 3:
                # 3 dedos → Nutrientes (ambas manos)
                normalized_y = 1.0 - (hy / current_h)
                target = float(np.clip(normalized_y * 100, 0, 100))
                gesture_text = f"Nutrientes: {target:.0f}%"
                # Retornamos el valor directo via nutrients (necesita variable externa)
                # Lo manejamos devolviendo en gesture_text con prefijo especial
                gesture_text = f"Nutrientes:{target:.1f}"

            elif dedos_arriba == 4:
                normalized_y = 1.0 - (hy / current_h)
                if hx < current_w // 2:
                    # 4 izquierda → pH
                    target = float(np.clip(normalized_y * 5 + 4, 4.0, 9.0))
                    self._smooth_ph = self._smooth(self._smooth_ph, target)
                    ph = self._smooth_ph
                    gesture_text = f"pH: {ph:.2f}"
                else:
                    # 4 derecha → pH también (consistencia)
                    target = float(np.clip(normalized_y * 100, 0, 100))   # ← rango de luz
                    self._smooth_light = self._smooth(self._smooth_light, target)  # ← actualiza light
                    light = self._smooth_light
                    gesture_text = f"Luz UV: {light:.0f}%"

            elif dedos_arriba == 5:
                normalized_y = 1.0 - (hy / current_h)
                if hx < current_w // 2:
                    # 5 izquierda → pH
                    target = float(np.clip(normalized_y * 5 + 4, 4.0, 9.0))
                    self._smooth_ph = self._smooth(self._smooth_ph, target)
                    ph = self._smooth_ph
                    gesture_text = f"pH: {ph:.2f}"
                else:
                    # 5 derecha → Luz UV
                    target = float(np.clip(normalized_y * 100, 0, 100))
                    self._smooth_light = self._smooth(self._smooth_light, target)
                    light = self._smooth_light
                    gesture_text = f"Luz UV: {light:.0f}%"
            is_attract = dedos_arriba >= 1
            hand_forces.append((hand_pos, is_attract, dist_thumb_index))

        return hand_forces, vortex_centers, temp, humidity, ph, light, \
               current_microbe, gesture_text

    def release(self):
        if self.cap is not None:
            self.cap.release()