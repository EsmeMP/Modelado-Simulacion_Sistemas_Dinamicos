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


def frame_rate_to_daily_r(p_frame: float, fps: int = FPS_SIM) -> float:
    p_frame = float(np.clip(p_frame, 1e-6, 1 - 1e-6))
    return -fps * np.log(1.0 - p_frame)


def logistic_ode(N, t, r, K):
    if K <= 0:
        return 0.0
    return r * N * (1.0 - N / K)


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


def analytic_solution(t_array, N0, r, K):
    if r == 0 or N0 == 0:
        return np.full_like(t_array, float(N0))
    denom = N0 + (K - N0) * np.exp(-r * t_array)
    denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
    return (K * N0) / denom


def laplace_solution(t_array, N0, r, K):
    x0 = float(N0) - float(K)
    return K + x0 * np.exp(-r * t_array)


def laplace_error_region(t_array, N0, r, K, threshold=5.0):
    N_lap = laplace_solution(t_array, N0, r, K)
    N_ana = analytic_solution(t_array, N0, r, K)
    err   = np.abs(N_lap - N_ana) / np.where(N_ana < 1e-10, 1e-10, N_ana) * 100
    return err > threshold


def euler_method(N0, r, K, t_array):
    N = np.zeros(len(t_array)); N[0] = float(N0)
    for i in range(len(t_array) - 1):
        h = t_array[i+1] - t_array[i]
        N[i+1] = float(np.clip(N[i] + h * logistic_ode(N[i], t_array[i], r, K), 0.0, K * 1.10))
    return N


def heun_method(N0, r, K, t_array):
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
    import threading
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

    r  = frame_rate_to_daily_r(float(r_frame), fps=FPS_SIM)
    r2 = frame_rate_to_daily_r(float(r_frame_invader), fps=FPS_SIM) \
         if r_frame_invader else r * 0.85

    N0 = float(max(1, N0))
    K  = float(max(2, K))

    _has_real_native = (N0_native is not None and float(N0_native) > 0)
    if _has_real_native:
        N0_plot = float(N0_native)
    elif N0 >= K * 0.80:
        N0_plot = K * 0.05
    elif N0 >= K * 0.40:
        N0_plot = K * 0.10
    else:
        N0_plot = N0

    t    = np.linspace(0, t_max, steps)
    h    = t[1] - t[0]
    stab = check_stability(r, h)
    if not stab['euler_stable']:
        t    = np.linspace(0, t_max, max(steps, int(np.ceil(t_max * r * 3))))
        h    = t[1] - t[0]
        stab = check_stability(r, h)

    N_ana     = analytic_solution(t, N0_plot, r, K)
    N_euler   = euler_method(N0_plot, r, K, t)
    N_heun    = heun_method(N0_plot, r, K, t)
    N_laplace = laplace_solution(t, N0_plot, r, K)

    err_euler   = relative_error(N_euler,   N_ana)
    err_heun    = relative_error(N_heun,    N_ana)
    err_laplace = relative_error(N_laplace, N_ana)

    lap_max  = float(np.max(err_laplace))
    lap_mean = float(np.mean(err_laplace))
    t50 = _time_to_fraction(t, N_ana, K, 0.50)
    t95 = _time_to_fraction(t, N_ana, K, 0.95)
    euler_max  = float(np.max(err_euler))
    euler_mean = float(np.mean(err_euler))
    heun_max   = float(np.max(err_heun))
    heun_mean  = float(np.mean(err_heun))

    lv_active = invasion_active and (M0_invader is not None) and (M0_invader > 0)

    if lv_active:
        n0_nat = float(N0_native)
        m0_inv = float(M0_invader)
        ratio_r = r2 / r if r > 0 else 1.0
        K1 = K
        K2 = float(np.clip(K * ratio_r, K * 0.4, K * 1.4))
        alpha12 = float(np.clip(r2 / r,  0.30, 2.50))
        alpha21 = float(np.clip(r  / r2, 0.30, 2.50))
        if abs(alpha12 - 1.0) < 0.05:
            alpha12 = 1.10; alpha21 = 0.90
        N_eu_lv, M_eu_lv = euler_lv(n0_nat, m0_inv, r, r2, K1, K2, alpha12, alpha21, t)
        N_hu_lv, M_hu_lv = heun_lv( n0_nat, m0_inv, r, r2, K1, K2, alpha12, alpha21, t)
        N_star, M_star, eigenvalues = lv_equilibrium(r, r2, K1, K2, alpha12, alpha21)
        lv_eq_exists = N_star is not None
        err_lv_N = relative_error(N_eu_lv, N_hu_lv)
        err_lv_M = relative_error(M_eu_lv, M_hu_lv)

    C_ANA   = "#00ff88"
    C_EULER = "#ff6644"
    C_HEUN  = "#44aaff"
    C_LAP   = "#cc88ff"
    C_NAT   = "#00ff88"
    C_INV   = "#ff4455"

    # ── CAMBIO 1: fuentes más grandes ────────────────────────────────────
    FS_TITLE  = 13    # título de cada gráfica
    FS_LABEL  = 11    # etiquetas de ejes
    FS_TICK   = 10    # números de los ejes
    FS_LEGEND = 10    # leyenda
    FS_ANNOT  = 10    # anotaciones y cajas de fórmulas
    FS_BOX    = 10    # cuadro inferior de parámetros
    FS_SUP    = 13    # suptitle

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

    # ── CAMBIO 2: layout con invasión ANTES del cuadro de datos ──────────
    # Sin invasión:  2 filas — (gráf1 | gráf2) / (cuadro ancho)
    # Con invasión:  3 filas — (gráf1 | gráf2) / (gráf3 | gráf4) / (cuadro ancho)
    if lv_active:
        n_rows         = 3
        height_ratios  = [1.0, 1.0, 0.60]   # gráf / gráf-lv / cuadro
        row_lv         = 1
        row_info       = 2
    else:
        n_rows         = 2
        height_ratios  = [1.0, 0.60]         # gráf / cuadro
        row_lv         = None
        row_info       = 1

    fig_h = sum(height_ratios) * 6.0
    fig = plt.figure(figsize=(16, fig_h), facecolor="#07070f")

    dias_act = (simulation_history[-1][0]
                if simulation_history and len(simulation_history) > 0 else 0.0)

    fig.suptitle(
        f"Análisis de Crecimiento Bacteriano — {microbe_name}"
        + (f"  vs  {invader_name}" if lv_active else "")
        + f"\nr = {r:.4f} días⁻¹   K = {int(K)}   h = {h:.4f} días   "
        + f"Día simulado: {dias_act:.2f}",
        fontsize=FS_SUP, color="white", fontweight="bold", y=0.998
    )

    gs = gridspec.GridSpec(
        n_rows, 2, figure=fig,
        hspace=0.50, wspace=0.30,
        left=0.07, right=0.97,
        top=0.96, bottom=0.04,
        height_ratios=height_ratios
    )

    # ── Gráfica 1: Curva S ────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(t, N_ana,     color=C_ANA,   lw=2.5,
             label="Analítica (solución exacta)", zorder=5)
    ax1.plot(t, N_euler,   color=C_EULER, lw=1.8, ls="--",  label="Euler")
    ax1.plot(t, N_heun,    color=C_HEUN,  lw=1.8, ls="-.",
             label="Heun (Euler mejorado)")
    ax1.plot(t, N_laplace, color=C_LAP,   lw=1.8, ls=":",
             label="Laplace (lineal.)")

    invalid = laplace_error_region(t, N0_plot, r, K, threshold=5.0)
    if invalid.any():
        ax1.fill_between(t, 0, K * 1.05, where=invalid,
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
    ax1.text(0.02, 0.97, "dN/dt = r · N · (1 − N/K)",
             transform=ax1.transAxes, color="#aaddff", fontsize=FS_ANNOT,
             va="top", fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.35", facecolor="#06061a",
                       edgecolor="#2a2a60", alpha=0.88))
    _legend(ax1)
    _ax(ax1, "Crecimiento Logístico — Euler vs Heun vs Analítica",
        ylabel="Población N(t)")

    # ── Gráfica 2: Errores ────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.fill_between(t, err_euler,   alpha=0.15, color=C_EULER)
    ax2.plot(t, err_euler,   color=C_EULER, lw=2.0,
             label=f"Euler  — máx {_fmt(euler_max)}, prom {_fmt(euler_mean)}")
    ax2.fill_between(t, err_heun,    alpha=0.15, color=C_HEUN)
    ax2.plot(t, err_heun,    color=C_HEUN,  lw=2.0,
             label=f"Heun   — máx {_fmt(heun_max)}, prom {_fmt(heun_mean)}")
    ax2.fill_between(t, err_laplace, alpha=0.12, color=C_LAP)
    ax2.plot(t, err_laplace, color=C_LAP,   lw=1.8, ls=":",
             label=f"Laplace — máx {_fmt(lap_max)}, prom {_fmt(lap_mean)}")

    idx_eu = int(np.argmax(err_euler))
    ax2.annotate(_fmt(euler_max),
                 xy=(t[idx_eu], euler_max),
                 xytext=(t[idx_eu]*0.4 + t_max*0.05, euler_max*0.65),
                 color=C_EULER, fontsize=FS_ANNOT,
                 arrowprops=dict(arrowstyle="->", color=C_EULER, lw=1.2))
    stab_txt = "✔ estable" if stab['euler_stable'] else "✗ inestable"
    ax2.text(0.02, 0.97,
             f"Euler {stab_txt}\nHeun ✔ más preciso\nLaplace ✔ exacta cerca de K",
             transform=ax2.transAxes, color="#ccddff", fontsize=FS_ANNOT,
             va="top", fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=0.35", facecolor="#06061a",
                       edgecolor="#2a2a60", alpha=0.88))
    _legend(ax2)
    _ax(ax2, "Error de Aproximación — Euler vs Heun vs Laplace",
        ylabel="Error relativo (%)")

    # ── Gráficas LV (fila 1, solo si invasión) ────────────────────────────
    if lv_active:
        ax3 = fig.add_subplot(gs[row_lv, 0])
        ax3.plot(t, N_eu_lv, color=C_EULER,  lw=1.5, ls="--",
                 label=f"Euler — Nativas ({microbe_name})")
        ax3.plot(t, N_hu_lv, color=C_NAT,    lw=2.2,
                 label="Heun  — Nativas")
        ax3.plot(t, M_eu_lv, color="#cc3322", lw=1.5, ls="--",
                 label=f"Euler — Invasoras ({invader_name})")
        ax3.plot(t, M_hu_lv, color=C_INV,    lw=2.2,
                 label="Heun  — Invasoras")
        if lv_eq_exists:
            ax3.axhline(N_star, color=C_NAT, lw=0.8, ls=":", alpha=0.4,
                        label=f"Eq. N*={N_star:.0f}")
            ax3.axhline(M_star, color=C_INV, lw=0.8, ls=":", alpha=0.4,
                        label=f"Eq. M*={M_star:.0f}")
        if invasion_history and len(invasion_history) > 1:
            t_ih = [s[0] for s in invasion_history]
            ax3.plot(t_ih, [s[1] for s in invasion_history],
                     color="#ccffcc", lw=1.3, alpha=0.55,
                     marker=".", markersize=2, label="Real — nativas")
            ax3.plot(t_ih, [s[2] for s in invasion_history],
                     color="#ffbbbb", lw=1.3, alpha=0.55,
                     marker=".", markersize=2, label="Real — invasoras")
        ax3.text(0.02, 0.97,
                 "dN/dt = r₁·N·(1−(N+α₁₂·M)/K₁)\ndM/dt = r₂·M·(1−(M+α₂₁·N)/K₂)",
                 transform=ax3.transAxes, color="#aaddff", fontsize=FS_ANNOT,
                 va="top", fontfamily="monospace",
                 bbox=dict(boxstyle="round,pad=0.35", facecolor="#06061a",
                           edgecolor="#2a2a60", alpha=0.88))
        ax3.legend(fontsize=FS_LEGEND - 1, ncol=2, facecolor="#111122",
                   edgecolor="#333355", framealpha=0.85)
        _ax(ax3,
            f"Competencia Lotka-Volterra — Euler vs Heun\n"
            f"Nativas ({microbe_name}: {int(n0_nat)})  vs  "
            f"Invasoras ({invader_name}: {int(m0_inv)})",
            ylabel="Población")

        ax4 = fig.add_subplot(gs[row_lv, 1])
        ax4.fill_between(t, err_lv_N, alpha=0.15, color=C_NAT)
        ax4.plot(t, err_lv_N, color=C_NAT, lw=2.0,
                 label=f"Error nativas    (máx {_fmt(np.max(err_lv_N))})")
        ax4.fill_between(t, err_lv_M, alpha=0.15, color=C_INV)
        ax4.plot(t, err_lv_M, color=C_INV, lw=2.0,
                 label=f"Error invasoras  (máx {_fmt(np.max(err_lv_M))})")
        ax4.text(0.02, 0.97,
                 "Error = |Euler − Heun| / Heun × 100%\n"
                 "Error bajo = ambos métodos coinciden",
                 transform=ax4.transAxes, color="#ccddff", fontsize=FS_ANNOT,
                 va="top", fontfamily="monospace",
                 bbox=dict(boxstyle="round,pad=0.35", facecolor="#06061a",
                           edgecolor="#2a2a60", alpha=0.88))
        _legend(ax4)
        _ax(ax4, "Error entre Euler y Heun — Invasión\nNativas vs Invasoras",
            ylabel="Error relativo (%)")

    # ── Cuadro de parámetros — siempre en la ÚLTIMA fila ─────────────────
    ax_info = fig.add_subplot(gs[row_info, :])
    ax_info.set_facecolor("#050510")
    ax_info.axis("off")

    mejora = max(0.0, euler_mean - heun_mean)

    if lv_active:
        _n0_label = (f"  N₀ nativas   = {int(N0_plot)}\n"
                     f"  N₀ invasoras = {int(m0_inv)}")
    else:
        _n0_label = (f"  N₀ = {int(N0_plot)}"
                     + ("  (curva completa)" if N0_plot != N0 else ""))

    col_params = (
        "  PARÁMETROS\n"
        f"  {'─'*30}\n"
        f"  r = {r:.5f}  días⁻¹\n"
        f"  K = {int(K)}  bacterias\n"
        f"  h = {h:.5f}  días (paso)\n"
        f"{_n0_label}\n\n"
        f"  EULER\n"
        f"  {'─'*30}\n"
        f"  {'✔ estable' if stab['euler_stable'] else '✗ inestable'}\n"
        f"  Error máx:   {_fmt(euler_max)}\n"
        f"  Error prom:  {_fmt(euler_mean)}\n\n"
        f"  HEUN\n"
        f"  {'─'*30}\n"
        f"  ✔ siempre estable\n"
        f"  Error máx:   {_fmt(heun_max)}\n"
        f"  Error prom:  {_fmt(heun_mean)}\n\n"
        f"  Heun mejora {mejora:.4f}%\n"
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
        "    k₁   = f(Nₙ)\n"
        "    k₂   = f(Nₙ + h·k₁)\n"
        "    Nₙ₊₁ = Nₙ + h/2 · (k₁ + k₂)\n\n"
        "  Laplace (linealización x = N−K):\n"
        "    dx/dt = −r·x\n"
        "    X(s) = x₀ / (s + r)\n"
        "    N(t) ≈ K + (N₀−K)·e^{−rt}\n"
        "    ✔ exacta cerca de K,  ✗ lejos de K"
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
    if lv_active and lv_eq_exists:
        col_env += (
            f"\n\n  LOTKA-VOLTERRA\n"
            f"  {'─'*30}\n"
            f"  α₁₂={alpha12:.2f}  α₂₁={alpha21:.2f}\n"
            f"  N*={N_star:.0f}   M*={M_star:.0f}\n"
            f"  λ₁={eigenvalues[0].real:+.3f}  λ₂={eigenvalues[1].real:+.3f}\n"
            + ("  Eq. ESTABLE ✔" if np.all(eigenvalues.real < 0)
               else "  Eq. INESTABLE ✗")
        )

    box_kw = dict(va="top", fontfamily="monospace", fontsize=FS_BOX)

    ax_info.text(0.01, 0.97, col_params, transform=ax_info.transAxes,
                 color="#88ffcc", **box_kw,
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#051208",
                           edgecolor="#1a4a25", alpha=0.92))
    ax_info.text(0.36, 0.97, col_formulas, transform=ax_info.transAxes,
                 color="#aaddff", **box_kw,
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#06061a",
                           edgecolor="#2a2a55", alpha=0.92))
    if col_env:
        ax_info.text(0.70, 0.97, col_env, transform=ax_info.transAxes,
                     color="#ffdd99", **box_kw,
                     bbox=dict(boxstyle="round,pad=0.5", facecolor="#141000",
                               edgecolor="#443800", alpha=0.92))

    # ── CAMBIO 3: nombre único con timestamp (nunca sobreescribe) ─────────
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix      = "invasion_" if lv_active else ""
    nombre      = f"analisis_{suffix}{timestamp}.png"
    output_path = os.path.join(os.path.dirname(__file__), "data", nombre)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=130, bbox_inches="tight", facecolor="#07070f")
    plt.close("all")
    print(f"[analysis] Listo → {output_path}")

    global analysis_ready, analysis_path
    with _analysis_lock:
        analysis_path  = output_path
        analysis_ready = True