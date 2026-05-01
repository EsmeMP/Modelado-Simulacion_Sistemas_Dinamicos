# ========================
# MICROBES.PY - Base de datos con 5 factores + shape visual
# ========================

import json
import os


_MAX_NUTRIENTS = 100.0

CUSTOM_PATH = os.path.join(os.path.dirname(__file__), "data", "custom_microbes.json")

microbes_db = {
    "E. coli": {
        "name": "Escherichia coli",
        "type": "bacteria",
        "shape": "bacilo_peritrico",    
        "optimal_temp": 37.0,
        "temp_range": (10.0, 45.0),
        "optimal_humidity": 80.0,
        "optimal_ph": 7.0,
        "ph_range": (4.5, 9.0),
        "light_sensitivity": 0.3,
        "nutrient_consumption": 0.008,
        "base_rate": 0.038,
        "color": (70, 255, 100),
        "description": "Bacteria intestinal común"
    },
    "Salmonella": {
        "name": "Salmonella enterica",
        "type": "bacteria",
        "shape": "bacilo_peritrico",     
        "optimal_temp": 37.0,
        "temp_range": (8.0, 45.0),
        "optimal_humidity": 75.0,
        "optimal_ph": 7.2,
        "ph_range": (4.0, 9.5),
        "light_sensitivity": 0.4,
        "nutrient_consumption": 0.007,
        "base_rate": 0.033,
        "color": (255, 180, 60),
        "description": "Intoxicación alimentaria"
    },
    "Staphylococcus": {
        "name": "Staphylococcus aureus",
        "type": "bacteria",
        "shape": "coco",                 
        "optimal_temp": 37.0,
        "temp_range": (15.0, 45.0),
        "optimal_humidity": 65.0,
        "optimal_ph": 7.0,
        "ph_range": (5.0, 9.0),
        "light_sensitivity": 0.2,
        "nutrient_consumption": 0.005,
        "base_rate": 0.029,
        "color": (255, 90, 90),
        "description": "Infecciones de piel"
    },
    "Influenza": {
        "name": "Virus Influenza",
        "type": "virus",
        "shape": "virus",              
        "optimal_temp": 15.0,
        "temp_range": (5.0, 25.0),
        "optimal_humidity": 25.0,
        "optimal_ph": 7.0,
        "ph_range": (6.0, 8.0),
        "light_sensitivity": 0.85,
        "nutrient_consumption": 0.003,
        "base_rate": 0.019,
        "color": (100, 200, 255),
        "description": "Virus respiratorio"
    },
    "Pseudomonas": {
        "name": "Pseudomonas aeruginosa",
        "type": "bacteria",
        "shape": "bacilo_polar",        
        "optimal_temp": 30.0,
        "temp_range": (10.0, 42.0),
        "optimal_humidity": 85.0,
        "optimal_ph": 7.0,
        "ph_range": (5.0, 8.5),
        "light_sensitivity": 0.5,
        "nutrient_consumption": 0.009,
        "base_rate": 0.035,
        "color": (0, 255, 200),
        "description": "Común en hospitales"
    }
}


def get_all_microbes():
    return list(microbes_db.keys())


def get_microbe_data(key: str):
    data = microbes_db.get(key)
    if data is None:
        return None
    # Garantizar tipos correctos siempre
    if isinstance(data.get("color"), list):
        data["color"] = tuple(data["color"])
    if isinstance(data.get("temp_range"), list):
        data["temp_range"] = tuple(data["temp_range"])
    if isinstance(data.get("ph_range"), list):
        data["ph_range"] = tuple(data["ph_range"])
    return data


def calculate_growth_rate(temp, humidity, ph, light, nutrients, microbe_key):
    data = get_microbe_data(microbe_key)
    if not data:
        return 0.01

    opt_temp = data["optimal_temp"]
    temp_factor = max(0.0, 1.0 - abs(temp - opt_temp) / 40.0)

    opt_hum = data["optimal_humidity"]
    hum_factor = max(0.0, 1.0 - abs(humidity - opt_hum) / 70.0)

    opt_ph = data["optimal_ph"]
    ph_factor = max(0.0, 1.0 - abs(ph - opt_ph) / 5.0)

    light_factor = max(0.0, 1.0 - (light / 100.0) * data["light_sensitivity"])

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

def _sanitize_microbe(key, data):
    if "color" in data:
        data["color"] = tuple(max(0, min(255, int(v))) for v in data["color"])
    if "temp_range" in data:
        data["temp_range"] = tuple(float(v) for v in data["temp_range"])
    if "ph_range" in data:
        data["ph_range"] = tuple(float(v) for v in data["ph_range"])
    if "base_rate" in data:
        data["base_rate"] = max(0.001, min(0.1, float(data["base_rate"])))
    if "light_sensitivity" in data:
        data["light_sensitivity"] = max(0.0, min(1.0, float(data["light_sensitivity"])))
    if "optimal_humidity" in data:
        data["optimal_humidity"] = max(0.0, min(100.0, float(data["optimal_humidity"])))
    data.setdefault("nutrient_consumption", 0.005)
    data.setdefault("shape", "bacilo_peritrico")  
    return data


def load_custom_microbes():
    if os.path.exists(CUSTOM_PATH):
        try:
            with open(CUSTOM_PATH, "r") as f:
                custom = json.load(f)
            loaded = 0
            for key, data in custom.items():
                try:
                    microbes_db[key] = _sanitize_microbe(key, data)
                    loaded += 1
                except Exception as e:
                    print(f"[microbes] Saltando '{key}': {e}")
            print(f"[microbes] {loaded} microbio(s) custom cargado(s)")
        except Exception as e:
            print(f"[microbes] Error al cargar: {e}")


def save_custom_microbe(key, data):
    os.makedirs(os.path.dirname(CUSTOM_PATH), exist_ok=True)
    existing = {}
    if os.path.exists(CUSTOM_PATH):
        try:
            with open(CUSTOM_PATH) as f:
                existing = json.load(f)
        except Exception:
            pass

    serializable = dict(data)
    for field in ("temp_range", "ph_range", "color"):
        if isinstance(serializable.get(field), tuple):
            serializable[field] = list(serializable[field])

    existing[key] = serializable
    with open(CUSTOM_PATH, "w") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    microbes_db[key] = data
    print(f"[microbes] Microbio '{key}' guardado")

_INVADER_MAP = {
    "E. coli":      "Staphylococcus",
    "Salmonella":   "Pseudomonas",
    "Staphylococcus": "E. coli",
    "Pseudomonas":  "Salmonella",
    "Influenza":    "Staphylococcus",
}

def get_invader(current_microbe: str) -> str:
    """Devuelve el microbio invasor para el microbio actual."""
    return _INVADER_MAP.get(current_microbe, "Staphylococcus")


load_custom_microbes()