# ========================
# MICROBES.PY - Base de datos con 5 factores + bacterias custom
# ========================

import json
import os

# FIX: MAX_NUTRIENTS definido aquí mismo para no depender de config
# (config importa pygame, lo que puede causar problemas de orden de importación)
_MAX_NUTRIENTS = 100.0

CUSTOM_PATH = os.path.join(os.path.dirname(__file__), "data", "custom_microbes.json")

microbes_db = {
    "E. coli": {
        "name": "Escherichia coli",
        "type": "bacteria",
        "optimal_temp": 37.0,
        "temp_range": (10.0, 45.0),
        "optimal_humidity": 80.0,
        "optimal_ph": 7.0,
        "ph_range": (4.5, 9.0),
        "light_sensitivity": 0.3,
        "nutrient_consumption": 0.008,
        "base_rate": 0.038,
        "color": (70, 255, 100),
        "shape": "bacilo_peritrico",
        "description": "Bacteria intestinal común"
    },
    "Salmonella": {
        "name": "Salmonella enterica",
        "type": "bacteria",
        "optimal_temp": 37.0,
        "temp_range": (8.0, 45.0),
        "optimal_humidity": 75.0,
        "optimal_ph": 7.2,
        "ph_range": (4.0, 9.5),
        "light_sensitivity": 0.4,
        "nutrient_consumption": 0.007,
        "base_rate": 0.033,
        "color": (255, 180, 60),
        "shape": "bacilo_peritrico",
        "description": "Intoxicación alimentaria"
    },
    "Staphylococcus": {
        "name": "Staphylococcus aureus",
        "type": "bacteria",
        "optimal_temp": 37.0,
        "temp_range": (15.0, 45.0),
        "optimal_humidity": 65.0,
        "optimal_ph": 7.0,
        "ph_range": (5.0, 9.0),
        "light_sensitivity": 0.2,
        "nutrient_consumption": 0.005,
        "base_rate": 0.029,
        "color": (255, 90, 90),
        "shape": "coco",
        "description": "Infecciones de piel"
    },
    "Influenza": {
        "name": "Virus Influenza",
        "type": "virus",
        "optimal_temp": 15.0,
        "temp_range": (5.0, 25.0),
        "optimal_humidity": 25.0,
        "optimal_ph": 7.0,
        "ph_range": (6.0, 8.0),
        "light_sensitivity": 0.85,
        "nutrient_consumption": 0.003,
        "base_rate": 0.019,
        "color": (100, 200, 255),
        "shape": "virus",   
        "description": "Virus respiratorio"
    },
    "Pseudomonas": {
        "name": "Pseudomonas aeruginosa",
        "type": "bacteria",
        "optimal_temp": 30.0,
        "temp_range": (10.0, 42.0),
        "optimal_humidity": 85.0,
        "optimal_ph": 7.0,
        "ph_range": (5.0, 8.5),
        "light_sensitivity": 0.5,
        "nutrient_consumption": 0.009,
        "base_rate": 0.035,
        "color": (0, 255, 200),
        "shape": "bacilo_polar", 
        "description": "Común en hospitales"
    }
}


def get_all_microbes():
    return list(microbes_db.keys())


def get_microbe_data(key: str):
    data = microbes_db.get(key)
    if data is None:
        return None
    # Garantizar que color, temp_range y ph_range sean siempre tuplas
    # sin importar si vinieron de JSON o de la DB hardcodeada
    if isinstance(data.get("color"), list):
        data["color"] = tuple(data["color"])
    if isinstance(data.get("temp_range"), list):
        data["temp_range"] = tuple(data["temp_range"])
    if isinstance(data.get("ph_range"), list):
        data["ph_range"] = tuple(data["ph_range"])
    return data


def calculate_growth_rate(temp: float, humidity: float, ph: float,
                          light: float, nutrients: float, microbe_key: str) -> float:
    """
    Calcula tasa de crecimiento considerando 5 factores:
    Temperatura, Humedad, pH, Luz UV y Nutrientes
    """
    data = get_microbe_data(microbe_key)
    if not data:
        return 0.01

    # Factor Temperatura
    opt_temp = data["optimal_temp"]
    temp_factor = max(0.0, 1.0 - abs(temp - opt_temp) / 40.0)

    # Factor Humedad
    opt_hum = data["optimal_humidity"]
    hum_factor = max(0.0, 1.0 - abs(humidity - opt_hum) / 70.0)

    # Factor pH
    opt_ph = data["optimal_ph"]
    ph_factor = max(0.0, 1.0 - abs(ph - opt_ph) / 5.0)

    # Factor Luz UV — FIX: normalizado correctamente, nunca negativo
    light_factor = max(0.0, 1.0 - (light / 100.0) * data["light_sensitivity"])

    # Factor Nutrientes — FIX: usa _MAX_NUTRIENTS local, no depende de config
    nutrient_factor = nutrients / _MAX_NUTRIENTS

    rate = (data["base_rate"]
            * temp_factor
            * hum_factor
            * ph_factor
            * light_factor
            * nutrient_factor
            * 2.8)

    return max(0.008, min(0.13, rate))


# ========================
# BACTERIAS CUSTOM (JSON)
# ========================

def load_custom_microbes():
    """Carga bacterias custom del JSON y las mezcla con la DB en memoria"""
    if os.path.exists(CUSTOM_PATH):
        try:
            with open(CUSTOM_PATH, "r") as f:
                custom = json.load(f)
            # Convertir listas a tuplas para temp_range y ph_range
            for key, data in custom.items():
                if "temp_range" in data and isinstance(data["temp_range"], list):
                    data["temp_range"] = tuple(data["temp_range"])
                if "ph_range" in data and isinstance(data["ph_range"], list):
                    data["ph_range"] = tuple(data["ph_range"])
                if "color" in data and isinstance(data["color"], list):
                    data["color"] = tuple(data["color"])
                # Asegurar que tiene nutrient_consumption
                data.setdefault("nutrient_consumption", 0.005)
            microbes_db.update(custom)
            print(f"[microbes] {len(custom)} microbio(s) custom cargado(s)")
        except Exception as e:
            print(f"[microbes] Error al cargar custom_microbes.json: {e}")


def save_custom_microbe(key: str, data: dict):
    """Guarda un nuevo microbio en el JSON y lo agrega en memoria"""
    os.makedirs(os.path.dirname(CUSTOM_PATH), exist_ok=True)
    existing = {}
    if os.path.exists(CUSTOM_PATH):
        try:
            with open(CUSTOM_PATH, "r") as f:
                existing = json.load(f)
        except Exception:
            pass

    # Convertir tuplas a listas para que JSON pueda serializarlas
    serializable = dict(data)
    if isinstance(serializable.get("temp_range"), tuple):
        serializable["temp_range"] = list(serializable["temp_range"])
    if isinstance(serializable.get("ph_range"), tuple):
        serializable["ph_range"] = list(serializable["ph_range"])
    if isinstance(serializable.get("color"), tuple):
        serializable["color"] = list(serializable["color"])

    existing[key] = serializable
    with open(CUSTOM_PATH, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    # También agregar en memoria con tuplas correctas
    microbes_db[key] = data
    print(f"[microbes] Microbio '{key}' guardado correctamente")

def _sanitize_microbe(key, data):
    """Corrige o descarta datos fuera de rango al cargar del JSON"""
    errors = []

    # Color — clampear a 0-255
    if "color" in data:
        c = data["color"]
        data["color"] = tuple(max(0, min(255, int(v))) for v in c)

    # Rangos — convertir listas a tuplas
    if "temp_range" in data:
        tr = data["temp_range"]
        data["temp_range"] = (float(tr[0]), float(tr[1]))

    if "ph_range" in data:
        pr = data["ph_range"]
        data["ph_range"] = (float(pr[0]), float(pr[1]))

    # base_rate — clampear a rango válido
    if "base_rate" in data:
        data["base_rate"] = max(0.001, min(0.1, float(data["base_rate"])))

    # light_sensitivity — clampear 0-1
    if "light_sensitivity" in data:
        data["light_sensitivity"] = max(0.0, min(1.0, float(data["light_sensitivity"])))

    # optimal_humidity — clampear 0-100
    if "optimal_humidity" in data:
        data["optimal_humidity"] = max(0.0, min(100.0, float(data["optimal_humidity"])))

    # nutrient_consumption — valor por defecto si no existe
    data.setdefault("nutrient_consumption", 0.005)

    return data


def load_custom_microbes():
    if os.path.exists(CUSTOM_PATH):
        try:
            with open(CUSTOM_PATH, "r") as f:
                custom = json.load(f)
            loaded = 0
            for key, data in custom.items():
                try:
                    clean = _sanitize_microbe(key, data)
                    microbes_db[key] = clean
                    loaded += 1
                except Exception as e:
                    print(f"[microbes] Saltando '{key}' por datos inválidos: {e}")
            print(f"[microbes] {loaded} microbio(s) custom cargado(s)")
        except Exception as e:
            print(f"[microbes] Error al cargar custom_microbes.json: {e}")


# Se ejecuta al importar el módulo
load_custom_microbes()