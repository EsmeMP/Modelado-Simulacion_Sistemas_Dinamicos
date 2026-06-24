import queue
import threading
import numpy as np
from sklearn.linear_model import SGDRegressor

class PredictorBridge:
    def __init__(self, capacity=500):
        self.q = queue.Queue(maxsize=2)
        self.capacity = capacity
        self._model = self._init_model()
        self._lock = threading.Lock()

    def _init_model(self):
        model = SGDRegressor(learning_rate='constant', eta0=0.001)
        # Warm-up con datos sintéticos para evitar NotFittedError
        X = np.random.rand(20, 5)
        y = np.random.rand(20) * 0.1
        model.partial_fit(X, y)
        return model

    def push(self, state: dict):
        """Llamar cada frame desde main.py. No bloqueante."""
        try:
            self.q.put_nowait(state)
        except queue.Full:
            self.q.get_nowait()   # descarta el frame viejo
            self.q.put_nowait(state)

    def pop(self) -> dict | None:
        """Llamar desde predictor_window.py. Retorna None si no hay dato nuevo."""
        try:
            return self.q.get_nowait()
        except queue.Empty:
            return None

    def update_model(self, X_row, y_val):
        """Entrenamiento online incremental (llámalo desde el hilo del predictor)."""
        with self._lock:
            self._model.partial_fit(np.array([X_row]), [y_val])

    def predict_rate(self, X_row) -> float:
        with self._lock:
            return float(self._model.predict(np.array([X_row]))[0])