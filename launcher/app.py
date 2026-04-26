"""
launcher/app.py
===============
Lanzador Flask para los proyectos de matematicas/

Uso:
    cd ~/Documentos/8-IDGS/matematicas
    source venv/bin/activate
    python launcher/app.py

Luego abre: http://localhost:5000
"""

import os
import sys
import subprocess
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# ─────────────────────────────────────────────────────────────
#  RUTAS BASE
#  BASE_DIR apunta a  matematicas/   (un nivel arriba de launcher/)
# ─────────────────────────────────────────────────────────────
BASE_DIR    = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PYTHON      = sys.executable   # usa el mismo python/venv con que corres Flask

# ─────────────────────────────────────────────────────────────
#  REGISTRO DE PROYECTOS
#  script  → relativo a BASE_DIR  (matematicas/)
#  cwd     → directorio de trabajo al lanzar el script
#            bact_ai/main.py necesita cwd=bact_ai/ para que
#            sus imports relativos funcionen
# ─────────────────────────────────────────────────────────────
PROYECTOS = {
    "bact_ai": {
        "nombre":      "GestBact AI",
        "descripcion": "Simulador de bacterias con 5 factores científicos controlados por gestos de mano.",
        "icono":       "🦠",
        "script":      "bact_ai/main.py",          # relativo a BASE_DIR
        "cwd":         "bact_ai",                  # relativo a BASE_DIR  ← IMPORTANTE
        
    },
    "proyecto2": {
        "nombre":      "Proyecto 2",
        "descripcion": "Próximamente — agrega aquí tu segundo proyecto.",
        "icono":       "🛻",
        "script":      None,                       # None = aún no disponible
        "cwd":         None,
       
    },
    "proyecto3": {
        "nombre":      "Proyecto 3",
        "descripcion": "Simulación interactiva de partículas con amortiguamiento y ruido en tiempo real.",
        "icono":       "🪄",
        "script":      "particles/file.py",
        "cwd":         "particles",
       
    },
}

# Registro de procesos activos  { proyecto_id: subprocess.Popen }
_procesos: dict[str, subprocess.Popen] = {}


# ─────────────────────────────────────────────────────────────
#  RUTAS FLASK
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", proyectos=PROYECTOS)


@app.route("/iniciar/<pid>")
def iniciar(pid: str):
    if pid not in PROYECTOS:
        return jsonify(ok=False, msg="Proyecto no encontrado"), 404

    p = PROYECTOS[pid]

    if p["script"] is None:
        return jsonify(ok=False, msg="Este proyecto aún no está disponible")

    # ¿Ya está corriendo?
    if pid in _procesos and _procesos[pid].poll() is None:
        return jsonify(ok=False, msg=f"{p['nombre']} ya está en ejecución")

    script_abs = os.path.join(BASE_DIR, p["script"])
    cwd_abs    = os.path.join(BASE_DIR, p["cwd"]) if p["cwd"] else BASE_DIR

    if not os.path.isfile(script_abs):
        return jsonify(ok=False, msg=f"No encontré el script: {p['script']}")

    try:
        proc = subprocess.Popen(
            [PYTHON, script_abs],
            cwd=cwd_abs,            # ← bact_ai/ para que config.py se importe bien
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _procesos[pid] = proc
        return jsonify(ok=True, msg=f"✅ {p['nombre']} iniciado")
    except Exception as e:
        return jsonify(ok=False, msg=str(e))


@app.route("/detener/<pid>")
def detener(pid: str):
    proc = _procesos.get(pid)
    if proc and proc.poll() is None:
        proc.terminate()
        return jsonify(ok=True, msg="⏹ Proceso detenido")
    return jsonify(ok=False, msg="No hay proceso activo")


@app.route("/estado/<pid>")
def estado(pid: str):
    proc = _procesos.get(pid)
    activo = proc is not None and proc.poll() is None
    return jsonify(activo=activo)


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"\n🚀  Launcher corriendo  →  http://localhost:5000")
    print(f"📁  BASE_DIR            →  {BASE_DIR}")
    print(f"🐍  Python              →  {PYTHON}\n")
    app.run(debug=False, port=5000)
