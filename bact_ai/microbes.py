# Base de datos de bacterias y virus + parámetros

# ========================
# BASE DE DATOS DE MICROORGANISMOS
# ========================

microbes_db = {
    "E. coli": {
        "name": "Escherichia coli",
        "type": "bacteria",
        "optimal_temp": 37.0,
        "temp_range": (10.0, 45.0),
        "humidity_pref": "alta",        # alta = >70%
        "base_rate": 0.038,             # tasa de crecimiento base
        "color": (70, 255, 100),
        "description": "Bacteria común en intestinos y alimentos"
    },
    "Salmonella": {
        "name": "Salmonella enterica",
        "type": "bacteria",
        "optimal_temp": 37.0,
        "temp_range": (8.0, 45.0),
        "humidity_pref": "alta",
        "base_rate": 0.033,
        "color": (255, 180, 60),
        "description": "Causante de intoxicaciones alimentarias"
    },
    "Staphylococcus": {
        "name": "Staphylococcus aureus",
        "type": "bacteria",
        "optimal_temp": 37.0,
        "temp_range": (15.0, 45.0),
        "humidity_pref": "media-alta",
        "base_rate": 0.029,
        "color": (255, 90, 90),
        "description": "Muy resistente, común en piel"
    },
    "Influenza": {
        "name": "Virus de la Influenza",
        "type": "virus",
        "optimal_temp": 15.0,
        "temp_range": (5.0, 25.0),
        "humidity_pref": "baja",        # baja humedad favorece
        "base_rate": 0.019,
        "color": (100, 200, 255),
        "description": "Virus respiratorio estacional"
    },
    "Pseudomonas": {
        "name": "Pseudomonas aeruginosa",
        "type": "bacteria",
        "optimal_temp": 30.0,
        "temp_range": (10.0, 42.0),
        "humidity_pref": "alta",
        "base_rate": 0.035,
        "color": (0, 255, 200),
        "description": "Común en ambientes húmedos y hospitales"
    }
}

def get_microbe_data(key: str):
    """Devuelve los datos de un microorganismo o None si no existe"""
    return microbes_db.get(key)

def get_all_microbes():
    """Devuelve lista de nombres de microorganismos disponibles"""
    return list(microbes_db.keys())

def calculate_growth_rate(temp: float, humidity: float, microbe_key: str) -> float:
    """
    Calcula la tasa de crecimiento realista segun temperatura y humedad
    retorna valor entre 0.0 y 1.0 (aprox)
    """
    data = get_microbe_data(microbe_key)
    if not data:
        return 0.01

    # factor de temperatura (curva en forma de campana)
    opt = data["optimal_temp"]
    temp_factor = max(0.0, 1.0 - abs(temp - opt) / 40.0)

    # factor de humedad según preferencia
    if data["humidity_pref"] == "alta":
        hum_factor = min(1.0, humidity / 85.0)
    elif data["humidity_pref"] == "baja":
        hum_factor = min(1.0, (100 - humidity) / 85.0)
    else:  # media-alta
        hum_factor = min(1.0, humidity / 65.0)

    # tasa final
    rate = data["base_rate"] * temp_factor * hum_factor * 2.2
    return max(0.008, min(0.12, rate))  # se limita entre 0.8% y 12% por frame