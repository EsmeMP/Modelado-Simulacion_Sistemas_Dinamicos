# ========================
# ANALYSIS.PY
# Análisis matemático del crecimiento bacteriano
# Ecuaciones Diferenciales + Transformada de Laplace
# + Métodos Numéricos (Euler, Heun) + Comparación
# ========================

import numpy as np
import warnings
warnings.filterwarnings("ignore")

# ── Constante: frames por segundo de la simulación ──────────────────────────
FPS_SIM  = 60          # fps de pygame
DAYS_PER_FRAME = 1 / FPS_SIM   # cada frame = 1/60 de segundo (usamos "día" = 60 frames)


# ========================
# 0. CONVERSIÓN DE TASA
#    calculate_growth_rate devuelve probabilidad por FRAME (p_frame).
#    Para la ED logística necesitamos r en unidades de "días simulados"⁻¹.
#
#    Si en cada frame cada bacteria se reproduce con prob p:
#      dN/dt ≈ p · N   (en frames)
#    Convertido a días (1 día = 60 frames):
#      r = p · FPS_SIM
#
#    Pero como p ya incluye el factor de capacidad (la simulación
#    no permite > MAX_PARTICLES), estimamos r desde la tasa bruta:
#      r_dia = -ln(1 - p_frame) * FPS_SIM   ← conversión exacta
# ========================

def frame_rate_to_daily_r(p_frame: float, fps: int = FPS_SIM) -> float:
    """
    Convierte probabilidad de reproducción por frame a tasa diaria continua r.

    Relación exacta:
        P(reproducción en 1 frame) = 1 - e^{-r/fps}
        → r = -fps · ln(1 - p_frame)

    Args:
        p_frame: probabilidad por frame de calculate_growth_rate (0.008–0.13)
        fps:     frames por segundo de la simulación
    Returns:
        r: tasa de crecimiento en días⁻¹ (para la ED logística)
    """
    p_frame = float(np.clip(p_frame, 1e-6, 1 - 1e-6))
    return -fps * np.log(1.0 - p_frame)


# ========================
# 1. ECUACIÓN DIFERENCIAL — MODELO LOGÍSTICO
# ========================

def logistic_ode(N: float, t: float, r: float, K: float) -> float:
    """
    dN/dt = r · N · (1 - N/K)

    Ecuación logística de Verhulst.
    Equilibrios: N* = 0 (inestable) y N* = K (estable).

    Args:
        N: población actual
        t: tiempo (días simulados)
        r: tasa intrínseca de crecimiento (días⁻¹)
        K: capacidad de carga (MAX_PARTICLES)
    """
    if K <= 0:
        return 0.0
    return r * N * (1.0 - N / K)


# ========================
# 2. SOLUCIÓN ANALÍTICA EXACTA
# ========================

def analytic_solution(t_array: np.ndarray, N0: float,
                       r: float, K: float) -> np.ndarray:
    """
    Solución exacta de la ecuación logística por separación de variables:

        N(t) = K · N₀ / [N₀ + (K - N₀) · e^{-r·t}]

    Obtenida también por Transformada de Laplace sobre la ecuación
    linealizada u' = -r·u con u = 1/N - 1/K (sustitución de Bernoulli):

        U(s) = u₀ / (s + r)  →  u(t) = u₀·e^{-rt}  →  N(t) como arriba.

    Casos especiales:
        r = 0 → N(t) = N₀  (población constante)
        N₀ ≥ K → N(t) decrece hacia K
        N₀ = 0 → N(t) = 0
    """
    if r == 0 or N0 == 0:
        return np.full_like(t_array, float(N0))

    denom = N0 + (K - N0) * np.exp(-r * t_array)
    # Evitar división por cero numéricamente
    denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
    return (K * N0) / denom


# ========================
# 3. MÉTODO DE EULER (orden 1)
# ========================

def euler_method(N0: float, r: float, K: float,
                 t_array: np.ndarray) -> np.ndarray:
    """
    Euler explícito (diferencias finitas hacia adelante):

        N_{n+1} = N_n + h · f(N_n, t_n)
        f(N, t) = r · N · (1 - N/K)

    Error de truncamiento local:  O(h²)
    Error global acumulado:       O(h)

    Estabilidad: requiere h < 2/r para no diverger (condición de Courant).
    Para la ED logística, el criterio exacto depende de N, pero
    h < 1/r es suficientemente conservador.
    """
    N    = np.zeros(len(t_array))
    N[0] = float(N0)

    for i in range(len(t_array) - 1):
        h        = t_array[i + 1] - t_array[i]
        N[i + 1] = N[i] + h * logistic_ode(N[i], t_array[i], r, K)
        N[i + 1] = float(np.clip(N[i + 1], 0.0, K * 1.10))

    return N


# ========================
# 4. MÉTODO DE HEUN / RK2 (orden 2)
# ========================

def heun_method(N0: float, r: float, K: float,
                t_array: np.ndarray) -> np.ndarray:
    """
    Método de Heun — predictor-corrector (Runge-Kutta orden 2):

        k₁ = f(Nₙ,       tₙ)
        k₂ = f(Nₙ + h·k₁, tₙ₊₁)
        N_{n+1} = Nₙ + (h/2)·(k₁ + k₂)

    Error de truncamiento local:  O(h³)
    Error global acumulado:       O(h²)  → significativamente más preciso que Euler

    Mejora sobre Euler: usa la derivada al inicio Y al final del intervalo
    como estimación de la pendiente media (cuadratura trapecial).
    """
    N    = np.zeros(len(t_array))
    N[0] = float(N0)

    for i in range(len(t_array) - 1):
        h        = t_array[i + 1] - t_array[i]
        k1       = logistic_ode(N[i],          t_array[i],     r, K)
        k2       = logistic_ode(N[i] + h * k1, t_array[i + 1], r, K)
        N[i + 1] = N[i] + (h / 2.0) * (k1 + k2)
        N[i + 1] = float(np.clip(N[i + 1], 0.0, K * 1.10))

    return N


# ========================
# 5. TRANSFORMADA DE LAPLACE — LINEALIZACIÓN
# ========================

def laplace_linearized(t_array: np.ndarray, N0: float,
                        r: float, K: float) -> np.ndarray:
    """
    Linealización alrededor del equilibrio estable N* = K.

    Sea x(t) = N(t) - K  (perturbación pequeña respecto a K).
    Sustituyendo en la ED logística y linealizando:

        dx/dt = -r · x(t)         (ED lineal de primer orden)

    Aplicando Transformada de Laplace:

        s·X(s) - x₀ = -r·X(s)
        X(s) = x₀ / (s + r)       ← polo simple en s = -r

    Transformada inversa:
        x(t) = x₀·e^{-rt}

    Por tanto:
        N_L(t) = K + (N₀ - K)·e^{-rt}

    ⚠ VALIDEZ: Solo cuando |N₀ - K| / K << 1  (perturbación pequeña).
    Para N₀ << K la aproximación subestima el crecimiento inicial
    (no captura la fase exponencial), pero converge bien cerca de K.

    Indicador de error de linealización:
        ε_lin = |N₀ - K| / K  (mostrado en métricas)
    """
    x0 = float(N0) - float(K)
    return K + x0 * np.exp(-r * t_array)


# ========================
# 6. ERROR RELATIVO
# ========================

def relative_error(numerical: np.ndarray,
                   analytical: np.ndarray) -> np.ndarray:
    """
    Error relativo porcentual punto a punto:

        e(t) = |N_num(t) - N_ana(t)| / max(|N_ana(t)|, ε) · 100

    Donde ε = 1e-10 evita división por cero en t=0 si N₀≈0.
    """
    denom = np.where(np.abs(analytical) < 1e-10, 1e-10, np.abs(analytical))
    return np.abs(numerical - analytical) / denom * 100.0


# ========================
# 7. VALIDACIÓN DEL PASO h
# ========================

def check_stability(r: float, h: float) -> dict:
    """
    Verifica la estabilidad numérica de los métodos.

    Para Euler en la ED logística linealizada (cerca de K):
        Estabilidad requiere: |1 - r·h| ≤ 1
        → h < 2/r

    Para Heun (RK2): región de estabilidad más amplia,
        aproximadamente h < 2.5/r en la práctica.

    Returns:
        dict con {'euler_stable', 'heun_stable', 'h_max_euler', 'h_max_heun'}
    """
    h_max_euler = 2.0 / r if r > 0 else float('inf')
    h_max_heun  = 2.5 / r if r > 0 else float('inf')
    return {
        'euler_stable': h < h_max_euler,
        'heun_stable':  h < h_max_heun,
        'h_max_euler':  h_max_euler,
        'h_max_heun':   h_max_heun,
        'h_actual':     h,
    }


def _time_to_fraction(t_array: np.ndarray, N_array: np.ndarray,
                       K: float, fraction: float = 0.95) -> float:
    """Tiempo en que la población alcanza `fraction` de K."""
    threshold = fraction * K
    idx = np.argmax(N_array >= threshold)
    return float(t_array[idx]) if idx > 0 else float(t_array[-1])


# ========================
# 8. FUNCIÓN PRINCIPAL
# ========================

def show_analysis(N0, r_frame, K, t_max=30, steps=500,
                  simulation_history=None,
                  microbe_name="E. coli", factor_values=None):
    """
    Genera análisis matemático completo y guarda la figura como PNG.

    Args:
        N0               : población inicial (partículas actuales)
        r_frame          : tasa de calculate_growth_rate (prob/frame)
        K                : capacidad máxima (MAX_PARTICLES)
        t_max            : días simulados a modelar
        steps            : pasos de integración numérica
        simulation_history: historial real de población
        microbe_name     : nombre del microbio
        factor_values    : dict {temp, humidity, ph, light, nutrients}
    """
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import os
    from datetime import datetime

    # ── Selección de backend ──────────────────────────────────────────────
    for backend in ["TkAgg", "Qt5Agg", "GTK3Agg", "Agg"]:
        try:
            matplotlib.use(backend)
            plt.figure(); plt.close()
            print(f"[analysis] Backend matplotlib: {backend}")
            break
        except Exception:
            continue

    # ── Conversión de tasa: prob/frame → r días⁻¹ ────────────────────────
    r = frame_rate_to_daily_r(float(r_frame), fps=FPS_SIM)
    print(f"[analysis] r_frame={r_frame:.5f} → r_diario={r:.4f} días⁻¹")

    N0  = float(max(1, N0))
    K   = float(max(2, K))

    # N0_plot: si la población ya está cerca o sobre K usamos
    # un valor inicial pequeño para ver la curva S completa.
    if N0 >= K * 0.80:
        N0_plot = K * 0.05
        print(f"[analysis] N0={N0:.0f} ≥ 0.8·K → N0_plot={N0_plot:.1f} (curva S completa)")
    elif N0 >= K * 0.40:
        N0_plot = K * 0.10
        print(f"[analysis] N0={N0:.0f} ≥ 0.4·K → N0_plot={N0_plot:.1f} (curva S parcial)")
    else:
        N0_plot = N0

    # ── Vector de tiempo y paso h ─────────────────────────────────────────
    t = np.linspace(0, t_max, steps)
    h = t[1] - t[0]

    # ── Verificar estabilidad numérica ────────────────────────────────────
    stab = check_stability(r, h)
    if not stab['euler_stable']:
        print(f"[analysis] ⚠ Euler INESTABLE: h={h:.4f} > h_max={stab['h_max_euler']:.4f}")
        # Aumentar steps automáticamente para garantizar estabilidad
        steps_needed = int(np.ceil(t_max * r * 3))
        t = np.linspace(0, t_max, max(steps, steps_needed))
        h = t[1] - t[0]
        stab = check_stability(r, h)
        print(f"[analysis] Steps ajustados a {len(t)}, h={h:.4f}")

    # ── Calcular soluciones ───────────────────────────────────────────────
    N_ana     = analytic_solution(t, N0_plot, r, K)
    N_euler   = euler_method(N0_plot, r, K, t)
    N_heun    = heun_method(N0_plot, r, K, t)
    N_laplace = laplace_linearized(t, N0_plot, r, K)

    # Errores
    err_euler = relative_error(N_euler,   N_ana)
    err_heun  = relative_error(N_heun,    N_ana)
    err_lap   = relative_error(N_laplace, N_ana)

    # Derivada analítica
    dN_dt = r * N_ana * (1.0 - N_ana / K)

    # Indicador de validez de Laplace
    eps_lin = abs(N0_plot - K) / K

    # ── Métricas ──────────────────────────────────────────────────────────
    euler_max  = float(np.max(err_euler))
    heun_max   = float(np.max(err_heun))
    euler_mean = float(np.mean(err_euler))
    heun_mean  = float(np.mean(err_heun))
    mejora     = max(0.0, euler_mean - heun_mean)
    t95        = _time_to_fraction(t, N_ana, K, 0.95)
    t50        = _time_to_fraction(t, N_ana, K, 0.50)
    N_eq       = float(N_ana[-1])

    # ── Figura ────────────────────────────────────────────────────────────
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(17, 11), facecolor="#07070f")

    titulo_n0 = f"N₀={int(N0_plot)}" + (" (ajust.)" if N0_plot != N0 else "")
    dias_actuales = simulation_history[-1][0] if simulation_history and len(simulation_history) > 0 else 0.0

    fig.suptitle(
        f"Análisis Matemático — {microbe_name}\n"
        f"r={r:.4f} días⁻¹  (p_frame={r_frame:.5f})   K={int(K)}   {titulo_n0}   "
        f"h={h:.4f} días     ⏱ Día simulado: {dias_actuales:.2f}",
        fontsize=12, color="white", fontweight="bold", y=0.99
    )

    gs = gridspec.GridSpec(
        3, 3, figure=fig,
        hspace=0.50, wspace=0.38,
        left=0.07, right=0.97,
        top=0.93, bottom=0.06
    )

    C_ANA     = "#00ff88"
    C_EULER   = "#ff6644"
    C_HEUN    = "#44aaff"
    C_LAPLACE = "#ffdd44"
    C_REAL    = "#ff44ff"
    C_DERIV   = "#ff9900"
    C_STAB    = "#ff4466"

    def _ax_style(ax, title):
        ax.set_title(title, color="white", fontsize=10, pad=4)
        ax.tick_params(colors="lightgray", labelsize=8)
        ax.set_facecolor("#080818")
        for spine in ax.spines.values():
            spine.set_color("#2a2a4a")
        ax.grid(alpha=0.12, color="gray", linewidth=0.6)

    # ── Gráfica 1: Comparación principal ─────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.plot(t, N_ana,     color=C_ANA,     lw=2.2, label="Analítica exacta",   zorder=5)
    ax1.plot(t, N_euler,   color=C_EULER,   lw=1.6, label="Euler O(h)",   ls="--")
    ax1.plot(t, N_heun,    color=C_HEUN,    lw=1.6, label="Heun O(h²)",   ls="-.")
    ax1.plot(t, N_laplace, color=C_LAPLACE, lw=1.4, label=f"Laplace (ε={eps_lin:.2f})", ls=":", alpha=0.85)
    ax1.axhline(K,   color="gray",  lw=1.0, ls="--", alpha=0.5, label=f"K = {int(K)}")
    ax1.axhline(K/2, color="#555577", lw=0.8, ls=":", alpha=0.4, label=f"K/2 = {int(K/2)}")
    # Marcar t50 y t95
    ax1.axvline(t50, color=C_HEUN,  lw=0.8, ls=":", alpha=0.6)
    ax1.axvline(t95, color=C_EULER, lw=0.8, ls=":", alpha=0.6)
    ax1.text(t50 + 0.3, K * 0.05, f"t₅₀={t50:.1f}d", color=C_HEUN,  fontsize=7)
    ax1.text(t95 + 0.3, K * 0.05, f"t₉₅={t95:.1f}d", color=C_EULER, fontsize=7)

    # Indicador de validez Laplace
    validez = "válida" if eps_lin < 0.3 else "⚠ aprox. lejana"
    ax1.set_title(
        f"Comparación de Soluciones  —  Laplace {validez} (ε={eps_lin:.2f})",
        color="white", fontsize=10
    )
    ax1.set_xlabel("Tiempo (días simulados)", color="lightgray", fontsize=9)
    ax1.set_ylabel("Población N(t)",          color="lightgray", fontsize=9)
    ax1.legend(fontsize=8, loc="lower right",
               facecolor="#111122", edgecolor="#333355", framealpha=0.8)
    _ax_style(ax1, ax1.get_title())

    # ── Gráfica 2: Historia real vs modelo ───────────────────────────────
    ax2 = fig.add_subplot(gs[0, 2])
    if simulation_history and len(simulation_history) > 1:
        t_real = [s[0] for s in simulation_history]
        n_real = [s[1] for s in simulation_history]
        ax2.plot(t_real, n_real, color=C_REAL, lw=1.6,
                label="Simulación real", alpha=0.9)
        ax2.plot(t, N_ana, color=C_ANA, lw=1.4, ls="--", alpha=0.6,
                 label="Modelo logístico")
        ax2.axhline(K, color="gray", lw=0.8, ls="--", alpha=0.4)
        ax2.legend(fontsize=7, facecolor="#111122", edgecolor="#333355")
        t_end = max(t_real[-1] * 1.3, 2.0)   # 30% más allá del último dato
        ax2.set_xlim(0, t_end)  
    else:
        ax2.text(0.5, 0.5,
                 "Presiona M después\nde simular un rato\npara ver datos reales",
                 ha="center", va="center", color="#888",
                 transform=ax2.transAxes, fontsize=9)
    ax2.set_xlabel("Tiempo (días)", color="lightgray", fontsize=9)
    ax2.set_ylabel("Población",     color="lightgray", fontsize=9)
    _ax_style(ax2, "Simulación Real vs Modelo Logístico")

    # ── Gráfica 3: Error relativo Euler ──────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.fill_between(t, err_euler, alpha=0.25, color=C_EULER)
    ax3.plot(t, err_euler, color=C_EULER, lw=1.6)
    idx_max = int(np.argmax(err_euler))

    def fmt_err(v):
        return f"{v:.2e}%" if v < 0.01 else f"{v:.3f}%"

    ax3.annotate(fmt_err(err_euler[idx_max]),
                 xy=(t[idx_max], err_euler[idx_max]),
                 xytext=(t[idx_max] * 0.5 + t_max * 0.05,
                         err_euler[idx_max] * 0.75),
                 color=C_EULER, fontsize=8,
                 arrowprops=dict(arrowstyle="->", color=C_EULER, lw=1.2))
    # Línea de estabilidad
    if not stab['euler_stable']:
        ax3.axvline(0, color=C_STAB, lw=1, ls="--",
                    label=f"h > h_max={stab['h_max_euler']:.3f}")
        ax3.legend(fontsize=7)
    ax3.set_xlabel("Tiempo (días)", color="lightgray", fontsize=9)
    ax3.set_ylabel("Error %",       color="lightgray", fontsize=9)
    _ax_style(ax3, f"Error Relativo — Euler  (max={fmt_err(euler_max)})")

    # ── Gráfica 4: Error relativo Heun ───────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.fill_between(t, err_heun, alpha=0.25, color=C_HEUN)
    ax4.plot(t, err_heun, color=C_HEUN, lw=1.6)
    idx_max2 = int(np.argmax(err_heun))
    ax4.annotate(fmt_err(err_heun[idx_max2]),
                 xy=(t[idx_max2], err_heun[idx_max2]),
                 xytext=(t[idx_max2] * 0.5 + t_max * 0.05,
                         err_heun[idx_max2] * 0.75),
                 color=C_HEUN, fontsize=8,
                 arrowprops=dict(arrowstyle="->", color=C_HEUN, lw=1.2))
    ax4.set_xlabel("Tiempo (días)", color="lightgray", fontsize=9)
    ax4.set_ylabel("Error %",       color="lightgray", fontsize=9)
    _ax_style(ax4, f"Error Relativo — Heun  (max={fmt_err(heun_max)})")

    # ── Gráfica 5: Error Laplace ──────────────────────────────────────────
    ax5 = fig.add_subplot(gs[1, 2])
    ax5.fill_between(t, err_lap, alpha=0.25, color=C_LAPLACE)
    ax5.plot(t, err_lap, color=C_LAPLACE, lw=1.6, label="Error Laplace")
    # Zona de validez (primeros 30% del tiempo donde la linealización es razonable)
    t_valid = t_max * 0.3
    ax5.axvspan(0, t_valid, alpha=0.06, color=C_LAPLACE,
                label=f"Zona aprox. válida (t<{t_valid:.1f}d)")
    ax5.legend(fontsize=7, facecolor="#111122", edgecolor="#333355")
    ax5.set_xlabel("Tiempo (días)", color="lightgray", fontsize=9)
    ax5.set_ylabel("Error %",       color="lightgray", fontsize=9)
    _ax_style(ax5, f"Error Laplace (ε_lin={eps_lin:.2f})")

    # ── Gráfica 6: dN/dt — Tasa de cambio ────────────────────────────────
    # (ocupa la primera columna del renglón 3, pero la usamos completa abajo)

    # ── Panel inferior: métricas + ecuaciones + factores ─────────────────
    ax6 = fig.add_subplot(gs[2, :])
    ax6.set_facecolor("#05050f")
    ax6.axis("off")

    stab_euler = "✔ ESTABLE" if stab['euler_stable'] else "✗ INESTABLE"
    stab_heun  = "✔ ESTABLE" if stab['heun_stable']  else "✗ INESTABLE"

    metrics_text = (
        "  MÉTRICAS DE PRECISIÓN\n"
        f"  r (días⁻¹):   {r:.5f}   ←  convertido de p_frame={r_frame:.5f}\n"
        f"  h (paso):      {h:.5f}   h_max Euler: {stab['h_max_euler']:.5f}\n"
        f"  Euler  [{stab_euler}]  — Error máx: {euler_max:8.4f}%   medio: {euler_mean:8.4f}%\n"
        f"  Heun   [{stab_heun}]   — Error máx: {heun_max:8.4f}%   medio: {heun_mean:8.4f}%\n"
        f"  Mejora Heun/Euler: {mejora:.4f}% promedio\n"
        f"  Laplace  ε_lin={eps_lin:.3f}  ({'aprox. válida' if eps_lin<0.3 else 'aprox. lejana'})\n"
        f"  N(∞) ≈ {N_eq:.1f}   t₅₀ ≈ {t50:.2f}d   t₉₅ ≈ {t95:.2f}d"
    )

    eq_text = (
        "  MODELO MATEMÁTICO\n"
        "  ED:        dN/dt = r·N·(1 - N/K)\n"
        "  Analítica: N(t) = K·N₀ / [N₀+(K-N₀)·e^{-rt}]\n"
        "  Laplace:   X(s) = x₀/(s+r)  →  N≈K+(N₀-K)·e^{-rt}\n"
        "  Euler:     N_{n+1} = Nₙ + h·f(Nₙ)            O(h)\n"
        "  Heun:      N_{n+1} = Nₙ+h/2·[f(Nₙ)+f(Ñₙ₊₁)]  O(h²)\n"
        f"  Conv. r:   r = -fps·ln(1-p_frame)"
    )

    factors_text = ""
    if factor_values:
        factors_text = (
            "  CONDICIONES ACTUALES\n"
            f"  Temp:      {factor_values.get('temp', 0):.1f} °C\n"
            f"  Humedad:   {factor_values.get('humidity', 0):.0f} %\n"
            f"  pH:        {factor_values.get('ph', 0):.2f}\n"
            f"  Luz UV:    {factor_values.get('light', 0):.0f} %\n"
            f"  Nutrientes:{factor_values.get('nutrients', 0):.1f} %"
        )

    ax6.text(0.01, 0.98, metrics_text, transform=ax6.transAxes,
             color="#44ffaa", fontsize=8, va="top", fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#061206",
                       edgecolor="#1a4a1a", alpha=0.9))

    ax6.text(0.40, 0.98, eq_text, transform=ax6.transAxes,
             color="#aaddff", fontsize=8, va="top", fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#060612",
                       edgecolor="#1a1a44", alpha=0.9))

    if factors_text:
        ax6.text(0.76, 0.98, factors_text, transform=ax6.transAxes,
                 color="#ffdd88", fontsize=8, va="top", fontfamily="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="#141200",
                           edgecolor="#443a00", alpha=0.9))

    # ── Guardar ───────────────────────────────────────────────────────────
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(
        os.path.dirname(__file__), "data", f"analisis_{timestamp}.png"
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=130, bbox_inches="tight",
                facecolor="#07070f")
    plt.close()
    print(f"[analysis] Guardado en: {output_path}")
    import subprocess, sys
    try:
        if sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", output_path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", output_path])
        else:
            os.startfile(output_path)
    except Exception:
        pass