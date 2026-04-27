# ========================
# ANALYSIS.PY — Visualización simplificada para proyecto universitario
# Layout limpio: pocas gráficas, fáciles de explicar
# ========================

import matplotlib
matplotlib.use("Agg")

import numpy as np
import warnings
import threading
from datetime import datetime
warnings.filterwarnings("ignore")

analysis_ready  = False
analysis_path   = ""
_analysis_lock  = threading.Lock()

FPS_SIM        = 60
DAYS_PER_FRAME = 1 / FPS_SIM


# ========================
# CONVERSIÓN DE TASA
# ========================

def frame_rate_to_daily_r(p_frame: float, fps: int = FPS_SIM) -> float:
    p_frame = float(np.clip(p_frame, 1e-6, 1 - 1e-6))
    return -fps * np.log(1.0 - p_frame)


# ========================
# ECUACIÓN DIFERENCIAL — MODELO LOGÍSTICO
# ========================

def logistic_ode(N, t, r, K):
    """dN/dt = r · N · (1 - N/K)"""
    if K <= 0:
        return 0.0
    return r * N * (1.0 - N / K)


# ========================
# LOTKA-VOLTERRA COMPETITIVO
# ========================

def lv_odes(state, t, r1, r2, K1, K2, alpha12, alpha21):
    N, M = max(0.0, state[0]), max(0.0, state[1])
    dN = r1 * N * (1.0 - (N + alpha12 * M) / K1)
    dM = r2 * M * (1.0 - (M + alpha21 * N) / K2)
    return np.array([dN, dM])


def lv_equilibrium(r1, r2, K1, K2, alpha12, alpha21):
    denom = 1.0 - alpha12 * alpha21
    if abs(denom) < 1e-9:
        return None, None, None
    N_star = K1 * (1.0 - alpha12) / denom
    M_star = K2 * (1.0 - alpha21) / denom
    if N_star < 0 or M_star < 0:
        return None, None, None
    J = np.array([
        [r1 * (1 - 2*N_star/K1 - alpha12*M_star/K1), -r1 * alpha12 * N_star / K1],
        [-r2 * alpha21 * M_star / K2,                  r2 * (1 - 2*M_star/K2 - alpha21*N_star/K2)]
    ])
    return N_star, M_star, np.linalg.eigvals(J)


# ========================
# SOLUCIÓN ANALÍTICA
# ========================

def analytic_solution(t_array, N0, r, K):
    """N(t) = K·N₀ / [N₀ + (K-N₀)·e^{-rt}]"""
    if r == 0 or N0 == 0:
        return np.full_like(t_array, float(N0))
    denom = N0 + (K - N0) * np.exp(-r * t_array)
    denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
    return (K * N0) / denom


# ========================
# TRANSFORMADA DE LAPLACE (linealización)
# ========================

def laplace_solution(t_array, N0, r, K):
    """
    Linealización cerca del equilibrio K:
      Sea x = N - K  →  dx/dt = -r·x

    Transformada de Laplace:
      s·X(s) - x₀ = -r·X(s)
      X(s) = x₀ / (s + r)      ← función de transferencia

    Transformada inversa:
      x(t) = x₀·e^{-rt}
      N(t) ≈ K + (N₀ - K)·e^{-rt}

    Válida cerca de t→∞ (N≈K). Error mayor en fase de crecimiento rápido.
    """
    x0 = float(N0) - float(K)
    return K + x0 * np.exp(-r * t_array)


def laplace_error_region(t_array, N0, r, K, threshold=5.0):
    """
    Devuelve máscara donde Laplace tiene error > threshold%.
    Útil para sombrear la zona de 'linealización inválida'.
    """
    N_lap = laplace_solution(t_array, N0, r, K)
    N_ana = analytic_solution(t_array, N0, r, K)
    err   = np.abs(N_lap - N_ana) / np.where(N_ana < 1e-10, 1e-10, N_ana) * 100
    return err > threshold


# ========================
# MÉTODOS NUMÉRICOS
# ========================

def euler_method(N0, r, K, t_array):
    """Euler explícito  O(h)"""
    N = np.zeros(len(t_array)); N[0] = float(N0)
    for i in range(len(t_array) - 1):
        h = t_array[i+1] - t_array[i]
        N[i+1] = float(np.clip(N[i] + h * logistic_ode(N[i], t_array[i], r, K), 0.0, K * 1.10))
    return N


def heun_method(N0, r, K, t_array):
    """Heun / Euler mejorado  O(h²)"""
    N = np.zeros(len(t_array)); N[0] = float(N0)
    for i in range(len(t_array) - 1):
        h  = t_array[i+1] - t_array[i]
        k1 = logistic_ode(N[i],      t_array[i],   r, K)
        k2 = logistic_ode(N[i]+h*k1, t_array[i+1], r, K)
        N[i+1] = float(np.clip(N[i] + (h/2.0)*(k1+k2), 0.0, K * 1.10))
    return N


def euler_lv(N0, M0, r1, r2, K1, K2, alpha12, alpha21, t_array):
    N = np.zeros(len(t_array)); N[0] = float(N0)
    M = np.zeros(len(t_array)); M[0] = float(M0)
    for i in range(len(t_array) - 1):
        h = t_array[i+1] - t_array[i]
        d = lv_odes(np.array([N[i], M[i]]), t_array[i], r1, r2, K1, K2, alpha12, alpha21)
        N[i+1] = float(np.clip(N[i] + h * d[0], 0, K1 * 1.1))
        M[i+1] = float(np.clip(M[i] + h * d[1], 0, K2 * 1.1))
    return N, M


def heun_lv(N0, M0, r1, r2, K1, K2, alpha12, alpha21, t_array):
    N = np.zeros(len(t_array)); N[0] = float(N0)
    M = np.zeros(len(t_array)); M[0] = float(M0)
    for i in range(len(t_array) - 1):
        h  = t_array[i+1] - t_array[i]
        s0 = np.array([N[i], M[i]])
        k1 = lv_odes(s0,      t_array[i],   r1, r2, K1, K2, alpha12, alpha21)
        k2 = lv_odes(s0+h*k1, t_array[i+1], r1, r2, K1, K2, alpha12, alpha21)
        s1 = s0 + (h/2.0)*(k1+k2)
        N[i+1] = float(np.clip(s1[0], 0, K1 * 1.1))
        M[i+1] = float(np.clip(s1[1], 0, K2 * 1.1))
    return N, M


# ========================
# UTILIDADES
# ========================

def relative_error(numerical, reference):
    denom = np.where(np.abs(reference) < 1e-10, 1e-10, np.abs(reference))
    return np.abs(numerical - reference) / denom * 100.0


def check_stability(r, h):
    h_max = 2.0 / r if r > 0 else float('inf')
    return {'euler_stable': h < h_max, 'h_max_euler': h_max, 'h_actual': h}


def _time_to_fraction(t_array, N_array, K, fraction):
    idx = np.argmax(N_array >= fraction * K)
    return float(t_array[idx]) if idx > 0 else float(t_array[-1])


def _fmt(v):
    return f"{v:.2e}%" if v < 0.01 else f"{v:.3f}%"


# ========================
# TABLA NUMÉRICA — Euler vs Heun paso a paso
# ========================

def _build_step_table(t_array, N_ana, N_euler, N_heun, r, K, h_step,
                      max_rows=12):
    """
    Construye la tabla paso a paso con un subconjunto pedagógico de filas.
    Devuelve (header, rows) donde rows es una lista de strings formateados.

    IMPORTANTE: N_euler y N_heun deben haber sido calculados con el MISMO
    t_array que se pasa aquí (mismo h_step), para que la tabla sea consistente
    con la gráfica de errores.
    """
    steps = len(t_array) - 1

    t50_i = int(np.argmax(N_ana >= 0.50 * N_ana[-1]))
    t95_i = int(np.argmax(N_ana >= 0.95 * N_ana[-1]))
    show  = sorted(set(
        list(range(min(6, steps + 1))) +
        [max(0, t50_i - 1), t50_i, min(steps, t50_i + 1)] +
        [max(0, t95_i - 1), t95_i, min(steps, t95_i + 1)] +
        list(range(max(0, steps - 2), steps + 1))
    ))
    show = [i for i in show if i <= steps][:max_rows]

    # Predictor Euler: recalculado desde el yn de la tabla (no desde N_euler[i+1])
    # Para ODE autónoma f(N) no depende de t, por eso t=0 está bien.
    def euler_pred(yn):
        return yn + h_step * logistic_ode(yn, 0, r, K)

    sep = "  " + "─" * 130
    hdr = (
        f"  {'n':>4}  {'Xn':>7}  {'Y exacta':>10}  "
        f"{'Yn Euler':>10}  {'Yn+1* pred':>11}  {'Yn+1 Euler':>11}  "
        f"{'Ea Euler':>10}  {'Er Euler':>10}  {'Er% Euler':>10}  "
        f"{'Yn Heun':>10}  {'Yn+1 Heun':>10}  "
        f"{'Ea Heun':>9}  {'Er Heun':>9}  {'Er% Heun':>9}"
    )

    rows = [sep, hdr, sep]
    prev_i = -2
    for i in show:
        if i > prev_i + 1:
            rows.append("  " + "·" * 130)
        prev_i = i

        xn      = t_array[i]
        yn_ex   = N_ana[i]
        yn_eu   = N_euler[i]
        yn_he   = N_heun[i]
        ynp1_eu = N_euler[i + 1] if i < steps else float("nan")
        ynp1_he = N_heun[i + 1]  if i < steps else float("nan")
        ypred   = euler_pred(yn_eu)

        yn_ex_next = N_ana[i + 1] if i < steps else float("nan")

        ea_eu = abs(ynp1_eu - yn_ex_next) if not np.isnan(ynp1_eu) else float("nan")
        ea_he = abs(ynp1_he - yn_ex_next) if not np.isnan(ynp1_he) else float("nan")

        denom_next = abs(yn_ex_next) if (not np.isnan(yn_ex_next) and abs(yn_ex_next) > 1e-10) else 1e-10
        er_eu  = ea_eu  / denom_next if not np.isnan(ea_eu)  else float("nan")
        er_he  = ea_he  / denom_next if not np.isnan(ea_he)  else float("nan")
        erp_eu = er_eu  * 100        if not np.isnan(er_eu)  else float("nan")
        erp_he = er_he  * 100        if not np.isnan(er_he)  else float("nan")

        def fv(v, w=10, d=4):
            if np.isnan(v): return f"{'—':>{w}}"
            if abs(v) < 0.001 and v != 0: return f"{v:{w}.3e}"
            return f"{v:{w}.{d}f}"

        def fp(v, w=10):
            if np.isnan(v): return f"{'—':>{w}}"
            return f"{v:{w}.4f}%"

        marker = ""
        if i == t50_i: marker = " ←t50"
        if i == t95_i: marker = " ←t95"

        rows.append(
            f"  {i:>4}  {xn:>7.3f}  {fv(yn_ex)}  "
            f"{fv(yn_eu)}  {fv(ypred, 11)}  {fv(ynp1_eu, 11)}  "
            f"{fv(ea_eu)}  {fv(er_eu)}  {fp(erp_eu)}  "
            f"{fv(yn_he)}  {fv(ynp1_he)}  "
            f"{fv(ea_he, 9)}  {fv(er_he, 9)}  {fp(erp_he, 9)}"
            f"{marker}"
        )

    rows.append(sep)
    return rows


# ========================
# FUNCIÓN PRINCIPAL
# ========================

def show_analysis(N0, r_frame, K, t_max=30, steps=500,
                  simulation_history=None,
                  microbe_name="E. coli", factor_values=None,
                  invasion_active=False,
                  invader_name="Invasor",
                  N0_native=None,
                  M0_invader=None,
                  r_frame_invader=None,
                  invasion_history=None):
    t = threading.Thread(
        target=_run_analysis,
        args=(N0, r_frame, K, t_max, steps,
              simulation_history, microbe_name, factor_values,
              invasion_active, invader_name, N0_native, M0_invader,
              r_frame_invader, invasion_history),
        daemon=True
    )
    t.start()


def _run_analysis(N0, r_frame, K, t_max=30, steps=500,
                  simulation_history=None,
                  microbe_name="E. coli", factor_values=None,
                  invasion_active=False,
                  invader_name="Invasor",
                  N0_native=None,
                  M0_invader=None,
                  r_frame_invader=None,
                  invasion_history=None):
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import os

    # ── Tasas ──────────────────────────────────────────────────────────────
    r  = frame_rate_to_daily_r(float(r_frame), fps=FPS_SIM)
    r2 = frame_rate_to_daily_r(float(r_frame_invader), fps=FPS_SIM) \
         if r_frame_invader else r * 0.85

    N0 = float(max(1, N0))
    K  = float(max(2, K))

    # ── N0 pedagógico ──────────────────────────────────────────────────────
    # FIX #4: Si N0 real es alto (>15% de K), se usa N0_ped = 1% de K como
    # N0_plot para mostrar la sigmoide completa. Así los errores en la fase
    # de crecimiento rápido son visibles y reales.
    _has_real_native = (N0_native is not None and float(N0_native) > 0)
    if _has_real_native:
        N0_plot = float(N0_native)
    else:
        # Siempre usar N0 bajo para gráfica pedagógica cuando la real es alta
        N0_plot = K * 0.01 if N0 >= K * 0.15 else N0

    N0_real = N0   # conservar para tabla y etiquetas

    # ── Vector de tiempo: UN SOLO h para gráfica y errores ─────────────────
    # FIX #3: Eliminamos la distinción "h grueso" vs "h fino" en la gráfica
    # principal. Usamos h_demo (paso grande, pedagógico) tanto para las curvas
    # como para la gráfica de errores. El "h fino" solo se usa para la
    # comparación de convergencia dentro de la gráfica 2.
    h_demo = min(1.5 / r, t_max / 8)
    # Asegurar que h_demo sea estable para Euler: h < 2/r
    h_max_stable = (2.0 / r) * 0.90   # 90% del límite teórico
    h_demo = min(h_demo, h_max_stable)

    t_demo = np.arange(0, t_max + h_demo * 0.001, h_demo)
    t_demo = t_demo[t_demo <= t_max + 1e-9]
    h_actual = float(t_demo[1] - t_demo[0])  # h real del array

    # Vector denso solo para la curva analítica de referencia visual suave
    t_dense = np.linspace(0, t_max, 1000)

    # Vector fino para comparación de convergencia (Gráfica 2)
    # FIX #3: Se etiqueta explícitamente como "h/5 (convergencia)"
    t_fine = np.arange(0, t_max + h_demo / 5 * 0.001, h_demo / 5)
    t_fine = t_fine[t_fine <= t_max + 1e-9]
    h_fine = float(t_fine[1] - t_fine[0])

    stab      = check_stability(r, h_actual)
    stab_fine = check_stability(r, h_fine)

    # ── Soluciones — todas con el MISMO h_demo para consistencia ───────────
    # FIX #1 y #2: N_euler_demo y N_heun_demo son los que se grafican Y los
    # que se usan para calcular errores. No hay discrepancia de h entre ellos.
    N_ana_demo   = analytic_solution(t_demo, N0_plot, r, K)
    N_euler_demo = euler_method(N0_plot, r, K, t_demo)
    N_heun_demo  = heun_method(N0_plot, r, K, t_demo)

    # Solución analítica densa (solo para la curva suave en gráfica 1)
    N_ana_dense  = analytic_solution(t_dense, N0_plot, r, K)
    N_lap_dense  = laplace_solution(t_dense, N0_plot, r, K)

    # Euler fino para comparación de convergencia
    N_euler_fine = euler_method(N0_plot, r, K, t_fine)
    N_ana_fine   = analytic_solution(t_fine, N0_plot, r, K)
    N_heun_fine  = heun_method(N0_plot, r, K, t_fine)

    # ── Errores — calculados sobre h_demo (consistentes con la gráfica) ────
    # FIX #1: err_euler y err_heun ahora usan el mismo t_demo que las curvas
    # de la Gráfica 1. Los valores del panel de parámetros y la gráfica 2
    # se refieren todos al mismo h.
    err_euler_demo = relative_error(N_euler_demo, N_ana_demo)
    err_heun_demo  = relative_error(N_heun_demo,  N_ana_demo)

    # Laplace sobre t_dense (es continua, no depende de h)
    err_laplace    = relative_error(N_lap_dense, N_ana_dense)

    # Errores finos para comparación de convergencia en Gráfica 2
    err_euler_fine = relative_error(N_euler_fine, N_ana_fine)
    err_heun_fine  = relative_error(N_heun_fine,  N_ana_fine)

    # ── Estadísticas de error ──────────────────────────────────────────────
    euler_max       = float(np.max(err_euler_demo))
    euler_mean      = float(np.mean(err_euler_demo))
    heun_max        = float(np.max(err_heun_demo))
    heun_mean       = float(np.mean(err_heun_demo))
    euler_fine_max  = float(np.max(err_euler_fine))
    euler_fine_mean = float(np.mean(err_euler_fine))
    heun_fine_max   = float(np.max(err_heun_fine))
    heun_fine_mean  = float(np.mean(err_heun_fine))
    lap_max         = float(np.max(err_laplace))
    lap_mean        = float(np.mean(err_laplace))

    t50 = _time_to_fraction(t_demo, N_ana_demo, K, 0.50)
    t95 = _time_to_fraction(t_demo, N_ana_demo, K, 0.95)

    # ── TABLA paso a paso ─────────────────────────────────────────────────
    # FIX #2: La tabla usa EXACTAMENTE los mismos arrays (t_demo, N_euler_demo,
    # N_heun_demo, N_ana_demo) que la gráfica 1. Los valores de la tabla
    # coinciden punto a punto con las curvas visibles.
    table_rows = _build_step_table(
        t_demo, N_ana_demo, N_euler_demo, N_heun_demo,
        r, K, h_step=h_actual
    )

    # ── Colores ────────────────────────────────────────────────────────────
    C_ANA   = "#00ff88"
    C_EULER = "#ff6644"
    C_HEUN  = "#44aaff"
    C_LAP   = "#cc88ff"

    # ── Tamaños de fuente ──────────────────────────────────────────────────
    FS_TITLE  = 13
    FS_LABEL  = 11
    FS_TICK   = 10
    FS_LEGEND = 10
    FS_ANNOT  = 10
    FS_BOX    = 9
    FS_SUP    = 13

    def _ax(ax, title="", xlabel="Tiempo (días)", ylabel=""):
        if title:
            ax.set_title(title, color="white", fontsize=FS_TITLE,
                         pad=6, fontweight="bold")
        ax.set_facecolor("#080818")
        ax.tick_params(colors="lightgray", labelsize=FS_TICK)
        for sp in ax.spines.values():
            sp.set_color("#2a2a4a")
        ax.grid(alpha=0.13, color="gray", linewidth=0.6, linestyle="--")
        if xlabel: ax.set_xlabel(xlabel, color="#aaaacc", fontsize=FS_LABEL)
        if ylabel: ax.set_ylabel(ylabel, color="#aaaacc", fontsize=FS_LABEL)

    def _legend(ax, **kw):
        ax.legend(fontsize=FS_LEGEND, facecolor="#111122",
                  edgecolor="#333355", framealpha=0.85, **kw)

    plt.style.use("dark_background")

    # ── Layout ─────────────────────────────────────────────────────────────
    n_rows        = 2
    height_ratios = [1.0, 1.60]
    row_info      = 1

    fig_h = sum(height_ratios) * 6.0
    fig   = plt.figure(figsize=(16, fig_h), facecolor="#07070f")

    dias_act = (simulation_history[-1][0]
                if simulation_history and len(simulation_history) > 0 else 0.0)

    # FIX #3: El título ahora indica claramente qué h se usa en la gráfica
    fig.suptitle(
        f"Análisis de Crecimiento Bacteriano — {microbe_name}"
        + f"\nr = {r:.4f} días⁻¹   K = {int(K)}   "
        + f"h (gráfica) = {h_actual:.4f} días   "
        + f"h (convergencia) = {h_fine:.4f} días   "
        + f"Día simulado: {dias_act:.2f}",
        fontsize=FS_SUP, color="white", fontweight="bold", y=1.0
    )

    gs = gridspec.GridSpec(
        n_rows, 2, figure=fig,
        hspace=0.60, wspace=0.30,
        left=0.07, right=0.97,
        top=0.91, bottom=0.04,
        height_ratios=height_ratios
    )

    # ══════════════════════════════════════════════════════════════════════
    # GRÁFICA 1 — Curva S pedagógica
    # ══════════════════════════════════════════════════════════════════════
    ax1 = fig.add_subplot(gs[0, 0])

    # Curva analítica densa (suave, referencia visual)
    ax1.plot(t_dense, N_ana_dense, color=C_ANA, lw=2.5, zorder=5,
             label="Analítica (referencia exacta)")

    # Euler y Heun con h_demo — marcadores en los mismos puntos que la tabla
    ax1.plot(t_demo, N_euler_demo, color=C_EULER, lw=1.6,
             ls="--", marker="o", markersize=5, markerfacecolor="none",
             markeredgewidth=1.4, zorder=4,
             label=f"Euler  h={h_actual:.3f} d")
    ax1.plot(t_demo, N_heun_demo, color=C_HEUN, lw=1.6,
             ls="-", marker="*", markersize=6, zorder=4,
             label=f"Heun   h={h_actual:.3f} d")
    ax1.plot(t_dense, N_lap_dense, color=C_LAP, lw=1.5, ls=":",
             label="Laplace (lineal.)")

    invalid = laplace_error_region(t_dense, N0_plot, r, K, threshold=5.0)
    if invalid.any():
        ax1.fill_between(t_dense, 0, K * 1.05, where=invalid,
                         alpha=0.07, color=C_LAP,
                         label="Zona Laplace inválida (err>5%)")

    ax1.axhline(K,   color="#888888", lw=1.0, ls="--", alpha=0.55,
                label=f"K = {int(K)}")
    ax1.axhline(K/2, color="#555566", lw=0.7, ls=":",  alpha=0.35)
    ax1.axvline(t50, color=C_HEUN,  lw=0.9, ls=":", alpha=0.6)
    ax1.axvline(t95, color=C_EULER, lw=0.9, ls=":", alpha=0.6)
    ax1.text(t50 + t_max*0.01, K*0.03, f"t₅₀={t50:.1f}d",
             color=C_HEUN,  fontsize=FS_ANNOT)
    ax1.text(t95 + t_max*0.01, K*0.03, f"t₉₅={t95:.1f}d",
             color=C_EULER, fontsize=FS_ANNOT)

    # Nota: N0 usado en la gráfica vs N0 real de la simulación
    n0_note = (f"N₀ gráfica = {int(N0_plot)} (forma S)"
               if N0_plot != N0_real
               else f"N₀ = {int(N0_plot)}")
    ax1.text(0.02, 0.97,
             f"dN/dt = r · N · (1 − N/K)\n"
             f"{n0_note}\n"
             f"h = {h_actual:.4f} d  →  mismo h en tabla y error",
             transform=ax1.transAxes, color="#aaddff", fontsize=FS_ANNOT,
             va="top", fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.35", facecolor="#06061a",
                       edgecolor="#2a2a60", alpha=0.88))

    _legend(ax1, loc="lower right")
    _ax(ax1, "Crecimiento Logístico — Euler vs Heun vs Analítica",
        ylabel="Población N(t)")

    # ══════════════════════════════════════════════════════════════════════
    # GRÁFICA 2 — Errores
    # FIX #1 y #3: Ahora hay DOS pares de curvas claramente etiquetados:
    #   • h_demo (el paso que ves en la Gráfica 1 y en la tabla)
    #   • h/5    (paso fino, solo para mostrar convergencia al reducir h)
    # Ambos se calcularon con euler_method/heun_method sobre sus propios
    # t_demo / t_fine, así que los valores son honestos y consistentes.
    # ══════════════════════════════════════════════════════════════════════
    ax2 = fig.add_subplot(gs[0, 1])

    # Euler h_demo (mismo que gráfica 1 y tabla)
    ax2.fill_between(t_demo, err_euler_demo, alpha=0.15, color=C_EULER)
    ax2.plot(t_demo, err_euler_demo, color=C_EULER, lw=2.2,
             label=(f"Euler  h={h_actual:.3f} d "
                    f"[máx {_fmt(euler_max)}, prom {_fmt(euler_mean)}]"))

    # Euler fino (convergencia)
    ax2.plot(t_fine, err_euler_fine, color=C_EULER, lw=1.2, ls="--", alpha=0.55,
             label=(f"Euler  h={h_fine:.4f} d [convergencia] "
                    f"[máx {_fmt(euler_fine_max)}, prom {_fmt(euler_fine_mean)}]"))

    # Heun h_demo (mismo que gráfica 1 y tabla)
    ax2.fill_between(t_demo, err_heun_demo, alpha=0.15, color=C_HEUN)
    ax2.plot(t_demo, err_heun_demo, color=C_HEUN, lw=2.2,
             label=(f"Heun   h={h_actual:.3f} d "
                    f"[máx {_fmt(heun_max)}, prom {_fmt(heun_mean)}]"))

    # Heun fino (convergencia)
    ax2.plot(t_fine, err_heun_fine, color=C_HEUN, lw=1.2, ls="--", alpha=0.55,
             label=(f"Heun   h={h_fine:.4f} d [convergencia] "
                    f"[máx {_fmt(heun_fine_max)}, prom {_fmt(heun_fine_mean)}]"))

    # Laplace (continua, no depende de h)
    ax2.fill_between(t_dense, err_laplace, alpha=0.12, color=C_LAP)
    ax2.plot(t_dense, err_laplace, color=C_LAP, lw=1.8, ls=":",
             label=f"Laplace  [máx {_fmt(lap_max)}, prom {_fmt(lap_mean)}]")

    # Anotación del pico de Euler
    idx_eu = int(np.argmax(err_euler_demo))
    ax2.annotate(_fmt(euler_max),
                 xy=(t_demo[idx_eu], euler_max),
                 xytext=(t_demo[idx_eu]*0.4 + t_max*0.05, euler_max*0.65),
                 color=C_EULER, fontsize=FS_ANNOT,
                 arrowprops=dict(arrowstyle="->", color=C_EULER, lw=1.2))

    stab_txt = "✔ estable" if stab['euler_stable'] else "✗ inestable"
    ax2.text(0.02, 0.97,
             f"Línea gruesa = h usado en Gráfica 1\n"
             f"Línea punteada = h/5 (solo convergencia)\n"
             f"Euler {stab_txt}  |  Heun ✔ O(h²)\n"
             f"Laplace ✔ exacta cerca de K",
             transform=ax2.transAxes, color="#ccddff", fontsize=FS_ANNOT,
             va="top", fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.35", facecolor="#06061a",
                       edgecolor="#2a2a60", alpha=0.88))

    _legend(ax2)
    _ax(ax2, "Error de Aproximación — Euler vs Heun vs Laplace",
        ylabel="Error relativo (%)")

    # ══════════════════════════════════════════════════════════════════════
    # CUADRO DE PARÁMETROS, FÓRMULAS, CONDICIONES Y TABLA — última fila
    # ══════════════════════════════════════════════════════════════════════
    ax_info = fig.add_subplot(gs[row_info, :])
    ax_info.set_facecolor("#050510")
    ax_info.axis("off")

    mejora = max(0.0, euler_mean - heun_mean)

    col_params = (
        "  PARÁMETROS\n"
        f"  {'─'*30}\n"
        f"  r = {r:.5f}  días⁻¹\n"
        f"  K = {int(K)}  bacterias\n"
        f"  N₀ gráfica = {int(N0_plot)}\n"
        f"  N₀ real    = {int(N0_real)}\n\n"
        f"  h (gráfica 1 + tabla) = {h_actual:.5f} d\n"
        f"  h (convergencia)      = {h_fine:.5f} d\n\n"
        f"  EULER  (h = {h_actual:.4f} d)\n"
        f"  {'─'*30}\n"
        f"  {'✔ estable' if stab['euler_stable'] else '✗ inestable'}\n"
        f"  Error máx:   {_fmt(euler_max)}\n"
        f"  Error prom:  {_fmt(euler_mean)}\n\n"
        f"  EULER  (h/5 = {h_fine:.4f} d, convergencia)\n"
        f"  {'─'*30}\n"
        f"  {'✔ estable' if stab_fine['euler_stable'] else '✗ inestable'}\n"
        f"  Error máx:   {_fmt(euler_fine_max)}\n"
        f"  Error prom:  {_fmt(euler_fine_mean)}\n\n"
        f"  HEUN  (h = {h_actual:.4f} d)\n"
        f"  {'─'*30}\n"
        f"  ✔ siempre más preciso que Euler\n"
        f"  Error máx:   {_fmt(heun_max)}\n"
        f"  Error prom:  {_fmt(heun_mean)}\n\n"
        f"  Heun mejora vs Euler: {mejora:.4f}%\n"
        f"  t₅₀ ≈ {t50:.2f} d\n"
        f"  t₉₅ ≈ {t95:.2f} d\n\n"
        f"  LAPLACE\n"
        f"  {'─'*30}\n"
        f"  Error máx:   {_fmt(lap_max)}\n"
        f"  Error prom:  {_fmt(lap_mean)}\n"
        f"  (lineal. cerca de K)"
    )

    col_formulas = (
        "  MODELO MATEMÁTICO\n"
        f"  {'─'*30}\n"
        "  Ecuación diferencial:\n"
        "    dN/dt = r · N · (1 − N/K)\n\n"
        "  Solución analítica (exacta):\n"
        "    N(t) = K·N₀ / [N₀ + (K−N₀)·e^{−rt}]\n\n"
        "  Euler  [O(h)]:\n"
        "    Nₙ₊₁ = Nₙ + h · f(Nₙ)\n\n"
        "  Heun / Euler mejorado  [O(h²)]:\n"
        "    k₁   = f(Xₙ, Yₙ)\n"
        "    Y*ₙ₊₁ = Yₙ + h·k₁          ← predictor\n"
        "    Xₙ₊₁ = Xₙ + h\n"
        "    k₂   = f(Xₙ₊₁, Y*ₙ₊₁)\n"
        "    Yₙ₊₁ = Yₙ + h/2·(k₁+k₂)   ← corrector\n\n"
        "  Laplace (linealización x = N−K):\n"
        "    dx/dt = −r·x\n"
        "    X(s) = x₀ / (s + r)\n"
        "    N(t) ≈ K + (N₀−K)·e^{−rt}\n"
        "    ✔ exacta cerca de K,  ✗ lejos de K\n\n"
        "  Errores:\n"
        "    Eₐ  = |Yₙ₊₁ − Y_exacta|\n"
        "    Er  = Eₐ / |Y_exacta|\n"
        "    Er% = Er × 100"
    )

    col_env = ""
    if factor_values:
        col_env = (
            "  CONDICIONES ACTUALES\n"
            f"  {'─'*30}\n"
            f"  Temperatura:  {factor_values.get('temp', 0):.1f} °C\n"
            f"  Humedad:      {factor_values.get('humidity', 0):.0f} %\n"
            f"  pH:           {factor_values.get('ph', 0):.2f}\n"
            f"  Luz UV:       {factor_values.get('light', 0):.0f} %\n"
            f"  Nutrientes:   {factor_values.get('nutrients', 0):.1f} %\n\n"
            f"  Microbio: {microbe_name}"
        )

    box_kw = dict(va="top", fontfamily="monospace", fontsize=FS_BOX)

    # Tabla numérica (encabezado explica qué h usa)
    tbl_header = (
        "  TABLA NUMÉRICA — Euler vs Heun  "
        f"(h = {h_actual:.4f} días — MISMO paso que Gráfica 1)\n"
        f"  Eₐ = error absoluto  |  Er = error relativo  |  Er% = error porcentual  "
        f"|  Y*ₙ₊₁ = predictor Euler (corrector no aplicado)"
    )
    tbl_text = tbl_header + "\n" + "\n".join(table_rows)

    ax_info.text(0.00, 0.99, tbl_text, transform=ax_info.transAxes,
                 color="#ddddee", fontsize=FS_BOX, va="top",
                 fontfamily="monospace",
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#080818",
                           edgecolor="#2a2a4a", alpha=0.95))

    ax_info.text(0.00, 0.42, col_params, transform=ax_info.transAxes,
                 color="#88ffcc", **box_kw,
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#051208",
                           edgecolor="#1a4a25", alpha=0.92))
    ax_info.text(0.23, 0.42, col_formulas, transform=ax_info.transAxes,
                 color="#aaddff", **box_kw,
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#06061a",
                           edgecolor="#2a2a55", alpha=0.92))
    if col_env:
        ax_info.text(0.52, 0.42, col_env, transform=ax_info.transAxes,
                     color="#ffdd99", **box_kw,
                     bbox=dict(boxstyle="round,pad=0.5", facecolor="#141000",
                               edgecolor="#443800", alpha=0.92))

    # ── Guardar ────────────────────────────────────────────────────────────
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre      = f"analisis_{timestamp}.png"
    output_path = os.path.join(os.path.dirname(__file__), "data", nombre)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=130, bbox_inches="tight", facecolor="#07070f")
    plt.close("all")
    print(f"[analysis] Listo → {output_path}")

    global analysis_ready, analysis_path
    with _analysis_lock:
        analysis_path  = output_path
        analysis_ready = True