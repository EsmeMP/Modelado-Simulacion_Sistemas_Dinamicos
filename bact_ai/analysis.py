# ========================
# ANALYSIS.PY
# Análisis matemático del crecimiento bacteriano
# Ecuaciones Diferenciales + Transformada de Laplace
# + Métodos Numéricos (Euler, Heun) + Comparación
# ========================

import numpy as np
import matplotlib
# matplotlib.use("TkAgg")          # backend compatible con pygame simultáneo
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
import warnings
warnings.filterwarnings("ignore")


# ========================
# 1. ECUACIÓN DIFERENCIAL — MODELO LOGÍSTICO
# ========================

def logistic_ode(N, t, r, K):
    """
    dN/dt = r * N * (1 - N/K)
    Ecuación logística de Verhulst.
    N = población actual
    r = tasa de crecimiento (de calculate_growth_rate)
    K = capacidad máxima (MAX_PARTICLES)
    """
    return r * N * (1.0 - N / K)


# ========================
# 2. SOLUCIÓN ANALÍTICA EXACTA
# ========================

def analytic_solution(t_array, N0, r, K):
    """
    Solución exacta de la ecuación logística:
    N(t) = K * N0 / (N0 + (K - N0) * e^(-r*t))

    Derivada de la Transformada de Laplace aplicada
    a la linealización por sustitución u = 1/N.
    """
    if r == 0:
        return np.full_like(t_array, float(N0))
    denom = N0 + (K - N0) * np.exp(-r * t_array)
    # Evitar división por cero
    denom = np.where(np.abs(denom) < 1e-10, 1e-10, denom)
    return (K * N0) / denom


# ========================
# 3. MÉTODO DE EULER (orden 1)
# ========================

def euler_method(N0, r, K, t_array):
    """
    Euler explícito:
    N_{n+1} = N_n + h * f(N_n, t_n)

    Error de truncamiento local: O(h²)
    Error global: O(h)
    """
    N = np.zeros(len(t_array))
    N[0] = N0
    for i in range(len(t_array) - 1):
        h = t_array[i + 1] - t_array[i]
        N[i + 1] = N[i] + h * logistic_ode(N[i], t_array[i], r, K)
        N[i + 1] = max(0.0, min(N[i + 1], K * 1.05))  # clamp
    return N


# ========================
# 4. MÉTODO DE HEUN (Euler mejorado, orden 2)
# ========================

def heun_method(N0, r, K, t_array):
    """
    Euler mejorado (Heun / RK2):
    k1 = f(N_n, t_n)
    k2 = f(N_n + h*k1, t_{n+1})
    N_{n+1} = N_n + h/2 * (k1 + k2)

    Error de truncamiento local: O(h³)
    Error global: O(h²)  — más preciso que Euler
    """
    N = np.zeros(len(t_array))
    N[0] = N0
    for i in range(len(t_array) - 1):
        h  = t_array[i + 1] - t_array[i]
        k1 = logistic_ode(N[i], t_array[i], r, K)
        k2 = logistic_ode(N[i] + h * k1, t_array[i + 1], r, K)
        N[i + 1] = N[i] + (h / 2.0) * (k1 + k2)
        N[i + 1] = max(0.0, min(N[i + 1], K * 1.05))
    return N


# ========================
# 5. ERROR RELATIVO
# ========================

def relative_error(numerical, analytical):
    """
    Error relativo porcentual:
    e(t) = |N_num(t) - N_ana(t)| / N_ana(t) * 100
    """
    ana = np.where(np.abs(analytical) < 1e-10, 1e-10, analytical)
    return np.abs(numerical - analytical) / np.abs(ana) * 100.0


# ========================
# 6. TRANSFORMADA DE LAPLACE — ANÁLISIS LINEALIZADO
# ========================

def laplace_linearized(t_array, N0, r, K):
    """
    Linealización alrededor del equilibrio N* = K:
    Sea x(t) = N(t) - K  (perturbación)
    dx/dt ≈ -r * x

    Transformada de Laplace:
    s·X(s) - x(0) = -r·X(s)
    X(s) = x(0) / (s + r)

    Transformada inversa:
    x(t) = x(0)·e^{-rt}

    Por tanto:
    N_laplace(t) = K + (N0 - K)·e^{-rt}

    Válido para perturbaciones pequeñas alrededor de K.
    """
    x0 = N0 - K          # perturbación inicial
    return K + x0 * np.exp(-r * t_array)


# ========================
# 7. FUNCIÓN PRINCIPAL — GENERAR TODAS LAS GRÁFICAS
# ========================

def show_analysis(N0, r, K, t_max=30, steps=500, simulation_history=None,
                  microbe_name="E. coli", factor_values=None):
    
    # N0_display = min(N0, K * 0.1)   # mostrar desde 10% de K para ver la curva S
    # print(f"[analysis] N0 real={N0:.0f} > K={K}, usando N0={N0_display:.0f} para visualización")

    # # Calcular con N0_display para las curvas teóricas
    # N_ana     = analytic_solution(t, N0_display, r, K)
    # N_euler   = euler_method(N0_display, r, K, t)
    # N_heun    = heun_method(N0_display, r, K, t)
    # N_laplace = laplace_linearized(t, N0_display, r, K)

    """
    Genera ventana matplotlib con 5 gráficas:
    1. Comparación de soluciones (analítica, Euler, Heun, Laplace)
    2. Error relativo de Euler vs analítica
    3. Error relativo de Heun vs analítica
    4. Derivada dN/dt (tasa de cambio)
    5. Historia real de la simulación (si se pasa)

    Parámetros:
        N0               : población inicial
        r                : tasa de crecimiento (de calculate_growth_rate)
        K                : capacidad máxima (MAX_PARTICLES)
        t_max            : tiempo máximo en días
        steps            : número de pasos de integración
        simulation_history: lista de poblaciones reales del simulador
        microbe_name     : nombre del microbio actual
        factor_values    : dict con temp, humidity, ph, light, nutrients
    """

    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec

    # Intentar backends en orden hasta que uno funcione
    for backend in ["TkAgg", "Qt5Agg", "GTK3Agg", "Agg"]:
        try:
            matplotlib.use(backend)
            import matplotlib.pyplot as plt
            plt.figure()          # probar que funciona
            plt.close()
            print(f"[analysis] Backend: {backend}")
            break
        except Exception:
            continue

    if N0 > K * 0.5:
        N0_display = K * 0.1
        print(f"[analysis] N0 real={N0:.0f} > K={K}, usando N0={N0_display:.0f} para visualización")
    else:
        N0_display = N0

    t = np.linspace(0, t_max, steps)
    N0 = float(N0)
    r  = float(r)
    K  = float(K)

    # Calcular todas las soluciones
    N_ana    = analytic_solution(t, N0, r, K)
    N_euler  = euler_method(N0, r, K, t)
    N_heun   = heun_method(N0, r, K, t)
    N_laplace= laplace_linearized(t, N0, r, K)

    # Errores
    err_euler = relative_error(N_euler, N_ana)
    err_heun  = relative_error(N_heun,  N_ana)

    # Derivada (tasa de cambio)
    dN_dt = r * N_ana * (1.0 - N_ana / K)

    # ── Estilo oscuro ──
    plt.style.use("dark_background")
    fig = plt.figure(figsize=(16, 10), facecolor="#0a0a1a")
    fig.suptitle(
        f"Análisis Matemático — {microbe_name}   "
        f"(r={r:.4f}, K={int(K)}, N₀={int(N0)})",
        fontsize=14, color="white", fontweight="bold", y=0.98
    )

    gs = gridspec.GridSpec(3, 3, figure=fig,
                           hspace=0.45, wspace=0.35,
                           left=0.07, right=0.97,
                           top=0.93, bottom=0.07)

    # Colores consistentes
    C_ANA     = "#00ff88"
    C_EULER   = "#ff6644"
    C_HEUN    = "#44aaff"
    C_LAPLACE = "#ffdd44"
    C_REAL    = "#ff44ff"
    C_DERIV   = "#ff9900"

    # ── Gráfica 1: Comparación principal (ocupa 2 columnas) ──
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.plot(t, N_ana,     color=C_ANA,     lw=2.5, label="Analítica exacta",        zorder=5)
    ax1.plot(t, N_euler,   color=C_EULER,   lw=1.8, label="Euler (orden 1)",   ls="--")
    ax1.plot(t, N_heun,    color=C_HEUN,    lw=1.8, label="Heun (orden 2)",    ls="-.")
    ax1.plot(t, N_laplace, color=C_LAPLACE, lw=1.5, label="Laplace (lineal)",  ls=":",  alpha=0.8)
    ax1.axhline(K, color="gray", lw=1, ls="--", alpha=0.5, label=f"Capacidad K={int(K)}")
    # ax1.set_title("Comparación de Soluciones", color="white", fontsize=11)
    ax1.set_title(
        f"Comparación de Soluciones"
        f"{' (N₀ ajustado para visualización)' if N0 > K * 0.5 else ''}",
        color="white", fontsize=11
    )
    ax1.set_xlabel("Tiempo (días)", color="lightgray")
    ax1.set_ylabel("Población N(t)", color="lightgray")
    ax1.legend(fontsize=8, loc="lower right",
               facecolor="#111122", edgecolor="#333355")
    ax1.tick_params(colors="lightgray")
    ax1.set_facecolor("#080818")
    ax1.spines[:].set_color("#333355")
    ax1.grid(alpha=0.15, color="gray")

    # ── Gráfica 2: Historia real del simulador ──
    ax2 = fig.add_subplot(gs[0, 2])
    if simulation_history and len(simulation_history) > 1:
        t_sim = np.linspace(0, t_max, len(simulation_history))
        ax2.plot(t_sim, simulation_history, color=C_REAL, lw=1.8,
                 label="Simulación real")
        ax2.plot(t, N_ana, color=C_ANA, lw=1.5, ls="--", alpha=0.6,
                 label="Modelo teórico")
        ax2.legend(fontsize=7, facecolor="#111122", edgecolor="#333355")
    else:
        ax2.text(0.5, 0.5, "Ejecuta la simulación\npara ver datos reales",
                 ha="center", va="center", color="gray",
                 transform=ax2.transAxes, fontsize=9)
    ax2.set_title("Simulación Real vs Modelo", color="white", fontsize=11)
    ax2.set_xlabel("Tiempo (días)", color="lightgray")
    ax2.set_ylabel("Población", color="lightgray")
    ax2.tick_params(colors="lightgray")
    ax2.set_facecolor("#080818")
    ax2.spines[:].set_color("#333355")
    ax2.grid(alpha=0.15, color="gray")

    # ── Gráfica 3: Error relativo Euler ──
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.fill_between(t, err_euler, alpha=0.3, color=C_EULER)
    ax3.plot(t, err_euler, color=C_EULER, lw=1.8)
    ax3.set_title("Error Relativo — Euler", color="white", fontsize=11)
    ax3.set_xlabel("Tiempo (días)", color="lightgray")
    ax3.set_ylabel("Error %", color="lightgray")
    ax3.tick_params(colors="lightgray")
    ax3.set_facecolor("#080818")
    ax3.spines[:].set_color("#333355")
    ax3.grid(alpha=0.15, color="gray")
    # Anotar error máximo
    idx_max = np.argmax(err_euler)
    def fmt_err(v):
        return f"{v:.2e}%" if v < 0.01 else f"{v:.3f}%"
    ax3.annotate(fmt_err(err_euler[idx_max]),
                 xy=(t[idx_max], err_euler[idx_max]),
                 xytext=(t[idx_max] * 0.6, err_euler[idx_max] * 0.8),
                 color=C_EULER, fontsize=8,
                 arrowprops=dict(arrowstyle="->", color=C_EULER))

    # ── Gráfica 4: Error relativo Heun ──
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.fill_between(t, err_heun, alpha=0.3, color=C_HEUN)
    ax4.plot(t, err_heun, color=C_HEUN, lw=1.8)
    ax4.set_title("Error Relativo — Heun", color="white", fontsize=11)
    ax4.set_xlabel("Tiempo (días)", color="lightgray")
    ax4.set_ylabel("Error %", color="lightgray")
    ax4.tick_params(colors="lightgray")
    ax4.set_facecolor("#080818")
    ax4.spines[:].set_color("#333355")
    ax4.grid(alpha=0.15, color="gray")
    idx_max2 = np.argmax(err_heun)
    ax4.annotate(fmt_err(err_heun[idx_max2]),
                 xy=(t[idx_max2], err_heun[idx_max2]),
                 xytext=(t[idx_max2] * 0.6, err_heun[idx_max2] * 0.8),
                 color=C_HEUN, fontsize=8,
                 arrowprops=dict(arrowstyle="->", color=C_HEUN))

    # ── Gráfica 5: Derivada dN/dt ──
    ax5 = fig.add_subplot(gs[1, 2])
    ax5.plot(t, dN_dt, color=C_DERIV, lw=2.0)
    ax5.fill_between(t, dN_dt, alpha=0.2, color=C_DERIV)
    ax5.axhline(0, color="gray", lw=0.8, ls="--")
    idx_peak = np.argmax(dN_dt)
    ax5.axvline(t[idx_peak], color=C_DERIV, lw=1, ls=":", alpha=0.7)
    ax5.annotate(f"pico t={t[idx_peak]:.1f}d",
                 xy=(t[idx_peak], dN_dt[idx_peak]),
                 xytext=(t[idx_peak] + t_max * 0.05, dN_dt[idx_peak] * 0.85),
                 color=C_DERIV, fontsize=8,
                 arrowprops=dict(arrowstyle="->", color=C_DERIV))
    ax5.set_title("Tasa de Cambio dN/dt", color="white", fontsize=11)
    ax5.set_xlabel("Tiempo (días)", color="lightgray")
    ax5.set_ylabel("dN/dt", color="lightgray")
    ax5.tick_params(colors="lightgray")
    ax5.set_facecolor("#080818")
    ax5.spines[:].set_color("#333355")
    ax5.grid(alpha=0.15, color="gray")

    # ── Panel inferior: tabla de métricas y ecuaciones ──
    ax6 = fig.add_subplot(gs[2, :])
    ax6.set_facecolor("#05050f")
    ax6.axis("off")

    # Métricas numéricas
    euler_max  = np.max(err_euler)
    heun_max   = np.max(err_heun)
    euler_mean = np.mean(err_euler)
    heun_mean  = np.mean(err_heun)
    N_eq       = N_ana[-1]

    metrics_text = (
        f"  MÉTRICAS DE PRECISIÓN\n"
        f"  Euler    — Error máx: {euler_max:7.3f}%   Error medio: {euler_mean:7.3f}%\n"
        f"  Heun     — Error máx: {heun_max:7.3f}%   Error medio: {heun_mean:7.3f}%\n"
        f"  Mejora de Heun sobre Euler: {max(0, euler_mean - heun_mean):.3f}% promedio\n"
        f"  Población de equilibrio N(∞) ≈ {N_eq:.1f}   "
        f"Tiempo al 95% de K: t₉₅ ≈ {_time_to_95(t, N_ana, K):.1f} días"
    )

    eq_text = (
        "  ECUACIONES DEL MODELO\n"
        "  ED:       dN/dt = r·N·(1 - N/K)\n"
        "  Analítica: N(t) = K·N₀ / [N₀ + (K-N₀)·e^{-rt}]\n"
        "  Laplace (lineal): X(s) = x₀/(s+r)  →  N(t) ≈ K + (N₀-K)·e^{-rt}\n"
        "  Euler:    N_{n+1} = Nₙ + h·f(Nₙ)                    O(h)\n"
        "  Heun:     N_{n+1} = Nₙ + h/2·[f(Nₙ) + f(Nₙ+h·f(Nₙ))]  O(h²)"
    )

    # Factores ambientales
    factors_text = ""
    if factor_values:
        factors_text = (
            f"  CONDICIONES ACTUALES\n"
            f"  Temp: {factor_values.get('temp', 0):.1f}°C   "
            f"Humedad: {factor_values.get('humidity', 0):.0f}%   "
            f"pH: {factor_values.get('ph', 0):.2f}   "
            f"Luz UV: {factor_values.get('light', 0):.0f}%   "
            f"Nutrientes: {factor_values.get('nutrients', 0):.1f}%"
        )

    # Dibujar los tres bloques de texto
    ax6.text(0.01, 0.95, metrics_text, transform=ax6.transAxes,
             color="#44ffaa", fontsize=8.5, va="top",
             fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#0a1a0a",
                       edgecolor="#224422", alpha=0.8))

    ax6.text(0.38, 0.95, eq_text, transform=ax6.transAxes,
             color="#aaddff", fontsize=8.5, va="top",
             fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="#0a0a1a",
                       edgecolor="#222244", alpha=0.8))

    if factors_text:
        ax6.text(0.75, 0.95, factors_text, transform=ax6.transAxes,
                 color="#ffdd88", fontsize=8.5, va="top",
                 fontfamily="monospace",
                 bbox=dict(boxstyle="round,pad=0.4", facecolor="#1a1500",
                           edgecolor="#443300", alpha=0.8))

    import os
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(os.path.dirname(__file__), "data", f"analisis_{timestamp}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=120, bbox_inches="tight", facecolor="#0a0a1a")
    plt.close()
    print(f"[analysis] Guardado en: {output_path}")
    os.system(f"xdg-open '{output_path}' &")

def _time_to_95(t_array, N_array, K):
    """Tiempo en que la población alcanza el 95% de K."""
    threshold = 0.95 * K
    idx = np.argmax(N_array >= threshold)
    if idx == 0:
        return t_array[-1]
    return float(t_array[idx])


# cv2 --- opencv