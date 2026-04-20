# ========================
# MICROBES.PY - Base de datos mejorada con múltiples factores
# ========================

microbes_db = {
    "E. coli": {
        "name": "Escherichia coli",
        "type": "bacteria",
        "optimal_temp": 37.0,
        "temp_range": (10.0, 45.0),
        "optimal_humidity": 80.0,
        "optimal_ph": 7.0,
        "ph_range": (4.5, 9.0),
        "light_sensitivity": 0.3,        # 0 = no le afecta la luz, 1 = muy sensible
        "base_rate": 0.038,
        "color": (70, 255, 100),
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
        "base_rate": 0.033,
        "color": (255, 180, 60),
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
        "base_rate": 0.029,
        "color": (255, 90, 90),
        "description": "Infecciones de piel"
    },
    "Influenza": {
        "name": "Virus Influenza",
        "type": "virus",
        "optimal_temp": 15.0,
        "temp_range": (5.0, 25.0),
        "optimal_humidity": 25.0,       # Baja humedad favorece virus
        "optimal_ph": 7.0,
        "ph_range": (6.0, 8.0),
        "light_sensitivity": 0.85,      # Muy sensible a luz UV
        "base_rate": 0.019,
        "color": (100, 200, 255),
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
        "base_rate": 0.035,
        "color": (0, 255, 200),
        "description": "Común en hospitales"
    }
}

def get_all_microbes():
    return list(microbes_db.keys())

def get_microbe_data(key: str):
    return microbes_db.get(key)

def calculate_growth_rate(temp: float, humidity: float, ph: float, light: float, microbe_key: str) -> float:
    """
    Calcula tasa de crecimiento considerando 4 factores
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

    # Factor Luz (UV)
    light_factor = 1.0 - (light * data["light_sensitivity"] * 0.9)

    # Tasa final
    rate = data["base_rate"] * temp_factor * hum_factor * ph_factor * light_factor * 2.8
    
    return max(0.008, min(0.13, rate))   # Limitamos entre 0.8% y 13% por frame