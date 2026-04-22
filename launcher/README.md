# GestBact Launcher

Launcher Flask para el proyecto `bact_ai` (y los que vengan después).

## Estructura final

```
matematicas/                        ← tu raíz
├── bact_ai/                        ← SIN CAMBIOS (tu git)
│   ├── main.py
│   ├── gestures.py
│   ├── config.py
│   └── ...
├── launcher/                       ← SOLO ESTO ES NUEVO
│   ├── app.py
│   ├── requirements_launcher.txt
│   └── templates/
│       └── index.html
├── bacterias2.py
├── bacterias3.py
└── venv/
```

## Instalación

```bash
cd ~/Documentos/8-IDGS/matematicas
source venv/bin/activate
pip install flask
```

## Uso

```bash
# Siempre desde matematicas/ con el venv activo:
cd ~/Documentos/8-IDGS/matematicas
source venv/bin/activate
python launcher/app.py
```

Abre: **http://localhost:5000**

## Cómo funciona el lanzado de bact_ai

`app.py` hace exactamente esto cuando presionas ▶ Iniciar:

```python
subprocess.Popen(
    [sys.executable, "bact_ai/main.py"],
    cwd="bact_ai/"         # ← directorio de trabajo = bact_ai/
)
```

Esto es equivalente a:
```bash
cd bact_ai
python main.py
```

Por eso los imports relativos de `main.py` (`from config import *`, etc.) funcionan sin modificar nada.

## Agregar los proyectos 2 y 3

Cuando tengas tus otros dos proyectos, edita el diccionario `PROYECTOS` en `launcher/app.py`:

```python
"proyecto2": {
    "nombre":      "Mi Proyecto 2",
    "descripcion": "Descripción aquí.",
    "icono":       "🔬",
    "script":      "ruta/al/script.py",   # relativo a matematicas/
    "cwd":         "ruta/al/",            # directorio de trabajo
    "tags":        ["MediaPipe", "..."],
},
```

Si el script vive directo en `matematicas/` (ej. `bacterias5.py`):
```python
"script": "bacterias5.py",
"cwd":    None,    # None = usa matematicas/ como cwd
```

## .gitignore sugerido

Agrega esto a tu `.gitignore` para no subir el launcher si no quieres:
```
launcher/
```

O súbelo sin problema, no toca nada de `bact_ai/`.
