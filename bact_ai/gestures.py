# ========================
# GESTURES.PY - detección y manejo de gestos con MediaPipe
# Mejorado: anti-perfil, sensibilidad ajustada, gestos más estables
# + hand_states: indica qué parámetro controla cada mano
# + GESTO REINICIO: manos cruzadas en X mantenidas 1.5s → reset dramático
# ========================

import cv2
import mediapipe as mp
import numpy as np
import pygame
import math
from config import *
from microbes import get_all_microbes

# ── Colores BGR para OpenCV overlay (B, G, R) ─────────────────────
_CV_COLORS = {
    "Temperatura":  (0,   200, 255),
    "Humedad":      (255, 200,  50),
    "pH":           (255,  80, 180),
    "Luz UV":       (50,  180, 255),
    "Nutrientes":   (80,  220,  80),
    "—":            (160, 160, 160),
}

RESET_HOLD_MS = 1500   # ms que hay que mantener las manos cruzadas


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
        self.gesture_cooldown      = 350

        self._smooth_temp     = 25.0
        self._smooth_humidity = 50.0
        self._smooth_ph       = 7.0
        self._smooth_light    = 30.0
        self._smooth_nutrients = 50.0
        self._alpha           = 0.15

        self._dedos_history   = []
        self._history_len     = 4
        self.pause_triggered  = False

        # Estado por mano: {"left": {...}, "right": {...}}
        self.hand_states = {}

        # ── Gesto reinicio ────────────────────────────────────────
        self._reset_start_ms  = None   # momento en que empezaron las manos cruzadas
        self.reset_triggered  = False  # main.py lo lee y resetea
        self.reset_progress   = 0.0   # 0.0 → 1.0 para la animación

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _smooth(self, current, target):
        return current + self._alpha * (target - current)

    def _is_hand_frontal(self, hand_landmarks):
        p5  = hand_landmarks.landmark[5]
        p17 = hand_landmarks.landmark[17]
        p0  = hand_landmarks.landmark[0]
        p9  = hand_landmarks.landmark[9]
        ancho = abs(p5.x - p17.x)
        alto  = abs(p0.y - p9.y)
        if alto < 0.001:
            return False
        return (ancho / alto) > 0.28

    def _count_fingers(self, hand_landmarks):
        dedos = 0
        for tip_id, pip_id in [(8, 6), (12, 10), (16, 14), (20, 18)]:
            tip = hand_landmarks.landmark[tip_id]
            pip = hand_landmarks.landmark[pip_id]
            if tip.y < pip.y - 0.04:
                dedos += 1
        return dedos

    def _stable_finger_count(self, count):
        self._dedos_history.append(count)
        if len(self._dedos_history) > self._history_len:
            self._dedos_history.pop(0)
        if not self._dedos_history:
            return count
        return max(set(self._dedos_history), key=self._dedos_history.count)

    def _are_crossed(self, landmarks_by_side):
        """
        Manos cruzadas en X: la muñeca 'left' está a la DERECHA
        de la muñeca 'right' en coordenadas de imagen (ya flippeadas).
        El margen de 0.05 evita falsos positivos al pasar las manos cerca.
        Requiere ambas manos detectadas.
        """
        if "left" not in landmarks_by_side or "right" not in landmarks_by_side:
            return False
        lx = landmarks_by_side["left"].landmark[0].x
        rx = landmarks_by_side["right"].landmark[0].x
        return lx > rx + 0.05

    # ── Métodos públicos ──────────────────────────────────────────────────────

    def get_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return None, None
        frame  = cv2.flip(frame, 1)
        rgb    = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self.hands_detector.process(rgb)
        return frame, result

    def draw_landmarks(self, frame, result):
        if result.multi_hand_landmarks:
            for hand_landmarks in result.multi_hand_landmarks:
                self.mp_draw.draw_landmarks(
                    frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
        return frame

    # ── Overlay CV2 ──────────────────────────────────────────────────────────

    def draw_hand_overlay_cv2(self, frame, result):
        """
        Dibuja sobre el frame de OpenCV:
          · Recuadro por mano con parámetro, valor y barra de dedos
          · Durante gesto de reinicio: barra de carga en el centro
        """
        fh, fw = frame.shape[:2]

        # ── Overlay de reinicio ──────────────────────────────────────
        if self.reset_progress > 0.0:
            self._draw_reset_overlay_cv2(frame, fw, fh)

        if not self.hand_states:
            return frame

        for side, state in self.hand_states.items():
            param     = state.get("param", "—")
            color_bgr = _CV_COLORS.get(param, _CV_COLORS["—"])

            # Durante reinicio: color rojo pulsante
            if self.reset_progress > 0.0:
                pulse     = abs(math.sin(pygame.time.get_ticks() * 0.008))
                color_bgr = (int(50 * pulse), int(50 * pulse), int(200 + 55 * pulse))

            wx = int(state["wrist_x"] * fw)
            wy = int(state["wrist_y"] * fh)

            box_w, box_h = 190, 68
            bx = max(0, min(fw - box_w, wx - box_w // 2))
            by = max(0, min(fh - box_h, wy - box_h - 18))

            ov = frame.copy()
            cv2.rectangle(ov, (bx, by), (bx + box_w, by + box_h), (15, 15, 25), -1)
            cv2.addWeighted(ov, 0.72, frame, 0.28, 0, frame)

            cv2.rectangle(frame, (bx, by), (bx + box_w, by + box_h), color_bgr, 2)
            cv2.line(frame, (bx + 2, by + 2), (bx + box_w - 2, by + 2), color_bgr, 2)

            side_label = state.get("side_label", "?")

            if self.reset_progress > 0.0:
                cv2.putText(frame, f"{side_label} CRUZADA",
                            (bx + 8, by + 22),
                            cv2.FONT_HERSHEY_DUPLEX, 0.55, color_bgr, 1, cv2.LINE_AA)
                pct = int(self.reset_progress * 100)
                cv2.putText(frame, f"REINICIO {pct}%",
                            (bx + 8, by + 48),
                            cv2.FONT_HERSHEY_DUPLEX, 0.55, (80, 80, 255), 1, cv2.LINE_AA)
            else:
                cv2.putText(frame, side_label,
                            (bx + 8, by + 22),
                            cv2.FONT_HERSHEY_DUPLEX, 0.6, color_bgr, 1, cv2.LINE_AA)
                cv2.line(frame, (bx + 50, by + 6), (bx + 50, by + box_h - 6), (80, 80, 90), 1)
                cv2.putText(frame, param,
                            (bx + 58, by + 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, (220, 220, 220), 1, cv2.LINE_AA)
                val_text = state.get("value", "")
                cv2.putText(frame, val_text,
                            (bx + 58, by + 48),
                            cv2.FONT_HERSHEY_DUPLEX, 0.65, color_bgr, 1, cv2.LINE_AA)

            # Mini-barra de dedos
            dedos  = state.get("dedos", 0)
            bar_x0 = bx + 8
            bar_y0 = by + box_h - 14
            for d in range(5):
                dx   = bar_x0 + d * 12
                fill = color_bgr if d < dedos else (55, 55, 65)
                cv2.rectangle(frame, (dx, bar_y0), (dx + 9, bar_y0 + 8), fill, -1)

            cv2.line(frame, (bx + box_w // 2, by + box_h), (wx, wy), color_bgr, 1, cv2.LINE_AA)
            cv2.circle(frame, (wx, wy), 6, color_bgr, -1)
            cv2.circle(frame, (wx, wy), 8, (255, 255, 255), 1)

        return frame

    def _draw_reset_overlay_cv2(self, frame, fw, fh):
        """Barra de carga circular en el centro del frame CV2 con X animada."""
        cx, cy = fw // 2, fh // 2
        radius = 52
        t      = pygame.time.get_ticks()

        # Fondo oscuro semitransparente
        ov = frame.copy()
        cv2.circle(ov, (cx, cy), radius + 18, (10, 5, 5), -1)
        cv2.addWeighted(ov, 0.65, frame, 0.35, 0, frame)

        # Arco de progreso
        angle_end = int(360 * self.reset_progress)
        cv2.ellipse(frame, (cx, cy), (radius, radius),
                    -90, 0, angle_end, (60, 60, 220), 6, cv2.LINE_AA)

        # Borde base gris
        cv2.circle(frame, (cx, cy), radius, (60, 60, 80), 2, cv2.LINE_AA)

        # Pulso interior
        pulse_r = int(radius * 0.55 * (0.8 + 0.2 * abs(math.sin(t * 0.006))))
        pulse_a = int(120 * self.reset_progress)
        ov2 = frame.copy()
        cv2.circle(ov2, (cx, cy), pulse_r, (40, 40, 200), -1)
        cv2.addWeighted(ov2, pulse_a / 255, frame, 1 - pulse_a / 255, 0, frame)

        # X animada en el centro
        arm = int(radius * 0.45)
        pulse_col = (
            int(100 + 120 * abs(math.sin(t * 0.006))),
            int(100 + 120 * abs(math.sin(t * 0.006))),
            255
        )
        cv2.line(frame, (cx - arm, cy - arm), (cx + arm, cy + arm), pulse_col, 3, cv2.LINE_AA)
        cv2.line(frame, (cx + arm, cy - arm), (cx - arm, cy + arm), pulse_col, 3, cv2.LINE_AA)

        # Texto de porcentaje
        pct  = int(self.reset_progress * 100)
        txt  = f"{pct}%"
        size = cv2.getTextSize(txt, cv2.FONT_HERSHEY_DUPLEX, 0.9, 2)[0]
        cv2.putText(frame, txt,
                    (cx - size[0] // 2, cy + size[1] // 2),
                    cv2.FONT_HERSHEY_DUPLEX, 0.9, (120, 120, 255), 2, cv2.LINE_AA)

        label = "CRUZAR Y MANTENER..."
        ls    = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)[0]
        cv2.putText(frame, label,
                    (cx - ls[0] // 2, cy + radius + 28),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 220), 1, cv2.LINE_AA)

    # ── Proceso de gestos ─────────────────────────────────────────────────────

    def process_gestures(self, result, current_w, current_h,
                     temp, humidity, ph, light, nutrients, current_microbe):
        hand_forces    = []
        vortex_centers = []
        gesture_text   = "Esperando manos..."
        current_time   = pygame.time.get_ticks()

        self.hand_states     = {}
        self.reset_triggered = False

        if not result.multi_hand_landmarks:
            self._dedos_history.clear()
            self._reset_start_ms = None
            self.reset_progress  = 0.0
            return hand_forces, vortex_centers, temp, humidity, ph, light, \
       nutrients, current_microbe, gesture_text

        # ── Leer handedness ───────────────────────────────────────────
        handedness_list = []
        if result.multi_handedness:
            for h in result.multi_handedness:
                handedness_list.append(h.classification[0].label.lower())
        else:
            handedness_list = ["right"] * len(result.multi_hand_landmarks)

        # ── Mapear landmarks por lado ─────────────────────────────────
        landmarks_by_side = {}
        for idx, hand_landmarks in enumerate(result.multi_hand_landmarks):
            side = handedness_list[idx] if idx < len(handedness_list) else "right"
            landmarks_by_side[side] = hand_landmarks

        # ── Detectar cruce de manos ───────────────────────────────────
        crossed = self._are_crossed(landmarks_by_side)

        if crossed:
            if self._reset_start_ms is None:
                self._reset_start_ms = current_time
            elapsed = current_time - self._reset_start_ms
            self.reset_progress = min(1.0, elapsed / RESET_HOLD_MS)
            if elapsed >= RESET_HOLD_MS:
                self.reset_triggered = True
                self._reset_start_ms = None
                self.reset_progress  = 0.0
                return hand_forces, vortex_centers, temp, humidity, ph, light, \
       nutrients, current_microbe, "¡REINICIO!"
            gesture_text = f"REINICIO... {int(self.reset_progress * 100)}%"
        else:
            self._reset_start_ms = None
            self.reset_progress  = 0.0

        # ── Procesar gestos normales ──────────────────────────────────
        for idx, hand_landmarks in enumerate(result.multi_hand_landmarks):

            side       = handedness_list[idx] if idx < len(handedness_list) else "right"
            side_label = "IZQ" if side == "left" else "DER"

            if not self._is_hand_frontal(hand_landmarks):
                gesture_text = "Mano de perfil — gira hacia la cámara"
                self.hand_states[side] = {
                    "side_label": side_label,
                    "param":      "—",
                    "value":      "perfil",
                    "dedos":      0,
                    "wrist_x":    hand_landmarks.landmark[0].x,
                    "wrist_y":    hand_landmarks.landmark[0].y,
                }
                continue

            # Si las manos están cruzadas, mostrar estado pero no procesar parámetros
            if crossed:
                self.hand_states[side] = {
                    "side_label": side_label,
                    "param":      "—",
                    "value":      f"CRUCE {int(self.reset_progress * 100)}%",
                    "dedos":      0,
                    "wrist_x":    hand_landmarks.landmark[0].x,
                    "wrist_y":    hand_landmarks.landmark[0].y,
                }
                continue

            palm     = hand_landmarks.landmark[0]
            hx       = int(palm.x * current_w)
            hy       = int(palm.y * current_h)
            hand_pos = np.array([hx, hy], dtype=float)

            raw_count    = self._count_fingers(hand_landmarks)
            dedos_arriba = self._stable_finger_count(raw_count)

            dist_thumb_index = abs(
                hand_landmarks.landmark[4].x -
                hand_landmarks.landmark[8].x) * 130

            param_name  = "—"
            param_value = ""

            if dedos_arriba == 1:
                normalized_y = 1.0 - (hy / current_h)
                if hx < current_w // 2:
                    target = float(np.clip(normalized_y * 60, 0, 60))
                    self._smooth_temp = self._smooth(self._smooth_temp, target)
                    temp = self._smooth_temp
                    gesture_text = f"Temp: {temp:.1f}°C"
                    param_name  = "Temperatura"
                    param_value = f"{temp:.1f} C"
                else:
                    target = float(np.clip(normalized_y * 95 + 5, 5, 100))
                    self._smooth_humidity = self._smooth(self._smooth_humidity, target)
                    humidity = self._smooth_humidity
                    gesture_text = f"Humedad: {humidity:.0f}%"
                    param_name  = "Humedad"
                    param_value = f"{humidity:.0f} %"

            elif dedos_arriba == 3:
                normalized_y = 1.0 - (hy / current_h)
                target = float(np.clip(normalized_y * 100, 0, 100))
                self._smooth_nutrients = self._smooth(self._smooth_nutrients, target)
                nutrients = self._smooth_nutrients         
                gesture_text = f"Nutrientes: {nutrients:.1f}%"
                param_name  = "Nutrientes"
                param_value = f"{nutrients:.0f} %"

            elif dedos_arriba == 4:
                normalized_y = 1.0 - (hy / current_h)
                if hx < current_w // 2:
                    target = float(np.clip(normalized_y * 5 + 4, 4.0, 9.0))
                    self._smooth_ph = self._smooth(self._smooth_ph, target)
                    ph = self._smooth_ph
                    gesture_text = f"pH: {ph:.2f}"
                    param_name  = "pH"
                    param_value = f"{ph:.2f}"
                else:
                    target = float(np.clip(normalized_y * 100, 0, 100))
                    self._smooth_light = self._smooth(self._smooth_light, target)
                    light = self._smooth_light
                    gesture_text = f"Luz UV: {light:.0f}%"
                    param_name  = "Luz UV"
                    param_value = f"{light:.0f} %"

            elif dedos_arriba == 5:
                normalized_y = 1.0 - (hy / current_h)
                if hx < current_w // 2:
                    target = float(np.clip(normalized_y * 5 + 4, 4.0, 9.0))
                    self._smooth_ph = self._smooth(self._smooth_ph, target)
                    ph = self._smooth_ph
                    gesture_text = f"pH: {ph:.2f}"
                    param_name  = "pH"
                    param_value = f"{ph:.2f}"
                else:
                    target = float(np.clip(normalized_y * 100, 0, 100))
                    self._smooth_light = self._smooth(self._smooth_light, target)
                    light = self._smooth_light
                    gesture_text = f"Luz UV: {light:.0f}%"
                    param_name  = "Luz UV"
                    param_value = f"{light:.0f} %"

            self.hand_states[side] = {
                "side_label": side_label,
                "param":      param_name,
                "value":      param_value,
                "dedos":      dedos_arriba,
                "wrist_x":    palm.x,
                "wrist_y":    palm.y,
            }

            is_attract = dedos_arriba >= 1
            hand_forces.append((hand_pos, is_attract, dist_thumb_index))

        return hand_forces, vortex_centers, temp, humidity, ph, light, \
       nutrients, current_microbe, gesture_text

    def release(self):
        if self.cap is not None:
            self.cap.release()