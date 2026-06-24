# ========================
# ANALYSIS.PY — Visualización para proyecto universitario
# Layout: 1 gráfica + panel (parámetros | fórmulas | condiciones)
# ========================

import matplotlib
matplotlib.use("Agg")

import numpy as np
import warnings
import threading
from datetime import datetime

warnings.filterwarnings("ignore")

analysis_ready = False
analysis_path  = ""
_analysis_lock = threading.Lock()

FPS_SIM = 60


def frame_rate_to_daily_r(p_frame: float, fps: int = FPS_SIM) -> float:
    p_frame = float(np.clip(p_frame, 1e-6, 1 - 1e-6))
    return -fps * np.log(1.0 - p_frame)


def logistic_ode(N, t, r, K):
    if K <= 0:
        return 0.0
    return r * N * (1.0 - N / K)


def analytic_solution(t_array, N0, r, K):
    if r == 0 or N0 == 0:
        return np.full_like(t_array, float(N0))
    denom = N0 + (K - N0) * np.exp(-r * t_array)
    denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
    return (K * N0) / denom


def laplace_solution(t_array, N0, r, K):
    return K + (float(N0) - float(K)) * np.exp(-r * t_array)


def laplace_error_region(t_array, N0, r, K, threshold=5.0):
    N_lap = laplace_solution(t_array, N0, r, K)
    N_ana = analytic_solution(t_array, N0, r, K)
    err   = np.abs(N_lap - N_ana) / np.where(N_ana < 1e-10, 1e-10, N_ana) * 100
    return err > threshold


def euler_method(N0, r, K, t_array):
    N = np.zeros(len(t_array)); N[0] = float(N0)
    for i in range(len(t_array) - 1):
        h = t_array[i + 1] - t_array[i]
        N[i + 1] = float(np.clip(N[i] + h * logistic_ode(N[i], t_array[i], r, K), 0.0, K * 1.10))
    return N


def heun_method(N0, r, K, t_array):
    N = np.zeros(len(t_array)); N[0] = float(N0)
    for i in range(len(t_array) - 1):
        h  = t_array[i + 1] - t_array[i]
        k1 = logistic_ode(N[i], t_array[i], r, K)
        k2 = logistic_ode(N[i] + h * k1, t_array[i + 1], r, K)
        N[i + 1] = float(np.clip(N[i] + (h / 2.0) * (k1 + k2), 0.0, K * 1.10))
    return N


def relative_error(numerical, reference):
    denom = np.where(np.abs(reference) < 1e-10, 1e-10, np.abs(reference))
    return np.abs(numerical - reference) / denom * 100.0


def _time_to_fraction(t_array, N_array, K, fraction):
    idx = np.argmax(N_array >= fraction * K)
    return float(t_array[idx]) if idx > 0 else float(t_array[-1])


def _fmt(v):
    return f"{v:.2e}%" if v < 0.01 else f"{v:.3f}%"


def show_analysis(N0, r_frame, K, t_max=30, steps=500,
                  simulation_history=None,
                  microbe_name="E. coli", factor_values=None):
    threading.Thread(
        target=_run_analysis,
        args=(N0, r_frame, K, t_max, steps,
              simulation_history, microbe_name, factor_values),
        daemon=True
    ).start()


def _run_analysis(N0, r_frame, K, t_max=30, steps=500,
                  simulation_history=None,
                  microbe_name="E. coli", factor_values=None):
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import os

    r  = frame_rate_to_daily_r(float(r_frame), fps=FPS_SIM)
    N0 = float(max(1, N0))
    K  = float(max(2, K))

    h = min(1.5 / r, t_max / 8, (2.0 / r) * 0.90)
    t_demo  = np.arange(0, t_max + h * 0.001, h)
    t_demo  = t_demo[t_demo <= t_max + 1e-9]
    h       = float(t_demo[1] - t_demo[0])
    t_dense = np.linspace(0, t_max, 1000)

    N_ana_dense = analytic_solution(t_dense, N0, r, K)
    N_lap_dense = laplace_solution(t_dense,  N0, r, K)
    N_euler     = euler_method(N0, r, K, t_demo)
    N_heun      = heun_method(N0,  r, K, t_demo)
    N_ana_demo  = analytic_solution(t_demo, N0, r, K)

    err_euler    = relative_error(N_euler, N_ana_demo)
    err_heun     = relative_error(N_heun,  N_ana_demo)
    euler_max    = float(np.max(err_euler));  euler_mean = float(np.mean(err_euler))
    heun_max     = float(np.max(err_heun));   heun_mean  = float(np.mean(err_heun))
    euler_stable = h < (2.0 / r)

    t50 = _time_to_fraction(t_demo, N_ana_demo, K, 0.50)
    t95 = _time_to_fraction(t_demo, N_ana_demo, K, 0.95)

    dias_act = (simulation_history[-1][0]
                if simulation_history and len(simulation_history) > 0 else 0.0)

    C_ANA = "#00ff88"; C_EULER = "#ff6644"; C_HEUN = "#44aaff"; C_LAP = "#ffbb44"
    FS_TITLE = 13; FS_LABEL = 11; FS_TICK = 10; FS_LEGEND = 10
    FS_ANNOT = 10; FS_BOX = 9.5; FS_SUP = 13

    plt.style.use("dark_background")

    fig = plt.figure(figsize=(14, 11), facecolor="#07070f")
    fig.suptitle(
        f"Análisis de Crecimiento Bacteriano — {microbe_name}"
        f"\nr = {r:.4f} días⁻¹   K = {int(K)}   N₀ = {int(N0)}   "
        f"h = {h:.4f} días   Día simulado: {dias_act:.2f}",
        fontsize=FS_SUP, color="white", fontweight="bold", y=1.01
    )

    gs = gridspec.GridSpec(
        2, 1, figure=fig,
        hspace=0.45,
        left=0.08, right=0.97,
        top=0.93, bottom=0.04,
        height_ratios=[1.6, 1.0]
    )

    # ── Gráfica ────────────────────────────────────────────────────────────
    ax = fig.add_subplot(gs[0])
    ax.set_facecolor("#0d0d1a")
    ax.tick_params(colors="lightgray", labelsize=FS_TICK)
    for sp in ax.spines.values(): sp.set_color("#2a2a4a")
    ax.grid(alpha=0.13, color="gray", linewidth=0.6, linestyle="--")
    ax.set_xlabel("Tiempo (días)", color="#aaaacc", fontsize=FS_LABEL)
    ax.set_ylabel("Población N(t)", color="#aaaacc", fontsize=FS_LABEL)
    ax.set_title("Crecimiento Logístico — Euler vs Heun vs Analítica",
                 color="white", fontsize=FS_TITLE, fontweight="bold", pad=6)

    ax.plot(t_dense, N_ana_dense, color=C_ANA, lw=2.5, zorder=5, label="Analítica (exacta)")
    ax.plot(t_demo, N_euler, color=C_EULER, lw=1.6, ls="--",
            marker="o", markersize=5, markerfacecolor="none", markeredgewidth=1.4, zorder=4,
            label=f"Euler  h={h:.3f} d  [máx {_fmt(euler_max)}]")
    ax.plot(t_demo, N_heun, color=C_HEUN, lw=1.6, ls="-",
            marker="^", markersize=5, zorder=4,
            label=f"Heun   h={h:.3f} d  [máx {_fmt(heun_max)}]")
    ax.plot(t_dense, N_lap_dense, color=C_LAP, lw=1.5, ls=":", label="Laplace (lineal. cerca K)")

    invalid = laplace_error_region(t_dense, N0, r, K, threshold=5.0)
    if invalid.any():
        ax.fill_between(t_dense, 0, K * 1.05, where=invalid,
                        alpha=0.07, color=C_LAP, label="Zona Laplace inválida (err>5%)")

    ax.axhline(K,   color="#888888", lw=1.0, ls="--", alpha=0.55, label=f"K = {int(K)}")
    ax.axhline(K/2, color="#555566", lw=0.7, ls=":",  alpha=0.35)
    ax.axvline(t50, color=C_HEUN,  lw=0.9, ls=":", alpha=0.6)
    ax.axvline(t95, color=C_EULER, lw=0.9, ls=":", alpha=0.6)
    ax.text(t50 + t_max*0.01, K*0.03, f"t₅₀={t50:.1f}d", color=C_HEUN,  fontsize=FS_ANNOT)
    ax.text(t95 + t_max*0.01, K*0.03, f"t₉₅={t95:.1f}d", color=C_EULER, fontsize=FS_ANNOT)
    ax.text(0.02, 0.97, f"dN/dt = r · N · (1 − N/K)\nN₀={int(N0)}   h={h:.4f} d",
            transform=ax.transAxes, color="#aaddff", fontsize=FS_ANNOT, va="top",
            fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.35", facecolor="#06061a", edgecolor="#2a2a60", alpha=0.88))

    ax.legend(fontsize=FS_LEGEND, facecolor="#111122", edgecolor="#333355",
              framealpha=0.85, loc="lower right")

    # ── Panel info ─────────────────────────────────────────────────────────
    ax_info = fig.add_subplot(gs[1])
    ax_info.set_facecolor("#050510")
    ax_info.axis("off")

    col_params = (
        "  PARÁMETROS\n"
        f"  {'─'*26}\n"
        f"  r  = {r:.5f}  días⁻¹\n"
        f"  K  = {int(K)}  bacterias\n"
        f"  N₀ = {int(N0)}\n"
        f"  h  = {h:.5f}  días\n\n"
        f"  EULER  O(h)\n"
        f"  {'─'*26}\n"
        f"  {'✔ estable' if euler_stable else '✗ inestable'}\n"
        f"  Error máx:   {_fmt(euler_max)}\n"
        f"  Error prom:  {_fmt(euler_mean)}\n\n"
        f"  HEUN  O(h²)\n"
        f"  {'─'*26}\n"
        f"  ✔ siempre más preciso\n"
        f"  Error máx:   {_fmt(heun_max)}\n"
        f"  Error prom:  {_fmt(heun_mean)}\n\n"
        f"  t₅₀ ≈ {t50:.2f} d\n"
        f"  t₉₅ ≈ {t95:.2f} d"
    )

    col_formulas = (
        "  MODELO MATEMÁTICO\n"
        f"  {'─'*26}\n"
        "  E.D. logística:\n"
        "    dN/dt = r · N · (1 − N/K)\n\n"
        "  Solución analítica:\n"
        "    N(t) = K·N₀ / [N₀+(K−N₀)·e^{−rt}]\n\n"
        "  Euler  [O(h)]:\n"
        "    Nₙ₊₁ = Nₙ + h · f(Nₙ)\n\n"
        "  Heun  [O(h²)]:\n"
        "    k₁    = f(Xₙ, Yₙ)\n"
        "    Y*ₙ₊₁ = Yₙ + h·k₁\n"
        "    k₂    = f(Xₙ₊₁, Y*ₙ₊₁)\n"
        "    Yₙ₊₁  = Yₙ + h/2·(k₁+k₂)\n\n"
        "  Laplace (x = N − K):\n"
        "    X(s) = x₀ / (s + r)\n"
        "    N(t) ≈ K + (N₀−K)·e^{−rt}"
    )

    bkw = dict(va="top", fontfamily="monospace", fontsize=FS_BOX)

    ax_info.text(0.01, 0.97, col_params, transform=ax_info.transAxes,
                 color="#88ffcc", **bkw,
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#051208",
                           edgecolor="#1a4a25", alpha=0.92))

    ax_info.text(0.35, 0.97, col_formulas, transform=ax_info.transAxes,
                 color="#aaddff", **bkw,
                 bbox=dict(boxstyle="round,pad=0.5", facecolor="#06061a",
                           edgecolor="#2a2a55", alpha=0.92))

    if factor_values:
        col_env = (
            "  CONDICIONES ACTUALES\n"
            f"  {'─'*26}\n"
            f"  Temperatura:  {factor_values.get('temp', 0):.1f} °C\n"
            f"  Humedad:      {factor_values.get('humidity', 0):.0f} %\n"
            f"  pH:           {factor_values.get('ph', 0):.2f}\n"
            f"  Luz UV:       {factor_values.get('light', 0):.0f} %\n"
            f"  Nutrientes:   {factor_values.get('nutrients', 0):.1f} %\n\n"
            f"  Microbio:\n"
            f"  {microbe_name}"
        )
        ax_info.text(0.68, 0.97, col_env, transform=ax_info.transAxes,
                     color="#ffdd99", **bkw,
                     bbox=dict(boxstyle="round,pad=0.5", facecolor="#141000",
                               edgecolor="#443800", alpha=0.92))

    # ── Guardar ────────────────────────────────────────────────────────────
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(os.path.dirname(__file__), "data", f"analisis_{timestamp}.png")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path, dpi=130, bbox_inches="tight", facecolor="#07070f")
    plt.close("all")
    print(f"[analysis] Listo → {output_path}")

    global analysis_ready, analysis_path
    with _analysis_lock:
        analysis_path  = output_path
        analysis_ready = True