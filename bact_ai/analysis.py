# ========================
# ANALYSIS.PY
# Análisis matemático del crecimiento bacteriano
# Ecuaciones Diferenciales + Transformada de Laplace
# + Métodos Numéricos (Euler, Heun) + Comparación
# + Modelo de Invasión: Lotka-Volterra Competitivo
# ========================

import numpy as np
import warnings
warnings.filterwarnings("ignore")

FPS_SIM      = 60
DAYS_PER_FRAME = 1 / FPS_SIM


# ========================
# 0. CONVERSIÓN DE TASA
#    p_frame (prob/frame) → r (días⁻¹)
#    r = -fps · ln(1 - p_frame)
# ========================

def frame_rate_to_daily_r(p_frame: float, fps: int = FPS_SIM) -> float:
    p_frame = float(np.clip(p_frame, 1e-6, 1 - 1e-6))
    return -fps * np.log(1.0 - p_frame)


# ========================
# 1. ECUACIÓN DIFERENCIAL — MODELO LOGÍSTICO (1 especie)
# ========================

def logistic_ode(N: float, t: float, r: float, K: float) -> float:
    """
    dN/dt = r · N · (1 - N/K)   — Verhulst
    """
    if K <= 0:
        return 0.0
    return r * N * (1.0 - N / K)


# ========================
# 2. MODELO LOTKA-VOLTERRA COMPETITIVO (2 especies)
#
#    dN/dt = r₁·N·(1 - N/K₁  - α₁₂·M/K₁)
#    dM/dt = r₂·M·(1 - M/K₂  - α₂₁·N/K₂)
#
#    N = nativas,  M = invasoras
#    α₁₂ = efecto del invasor sobre el nativo (≥1 invasor agresivo)
#    α₂₁ = efecto del nativo sobre el invasor  (<1 nativo débil)
#
#    Equilibrios de coexistencia:
#      N* = K₁(1 - α₁₂·M*/K₁) / (1 - α₁₂·α₂₁)
#      M* = K₂(1 - α₂₁·N*/K₂) / (1 - α₁₂·α₂₁)
#
#    Transformada de Laplace (linealización en N*, M*):
#      δN' = a₁₁·δN + a₁₂·δM    →    [s·I - A]·X(s) = x₀
#      Eigenvalores λ₁,₂ determinan estabilidad del equilibrio.
# ========================

def lv_odes(state: np.ndarray, t: float,
            r1: float, r2: float,
            K1: float, K2: float,
            alpha12: float, alpha21: float) -> np.ndarray:
    """
    Sistema Lotka-Volterra competitivo.

    Returns dN/dt, dM/dt
    """
    N, M = max(0.0, state[0]), max(0.0, state[1])
    dN = r1 * N * (1.0 - (N + alpha12 * M) / K1)
    dM = r2 * M * (1.0 - (M + alpha21 * N) / K2)
    return np.array([dN, dM])


def lv_equilibrium(r1, r2, K1, K2, alpha12, alpha21):
    """
    Calcula el equilibrio de coexistencia (si existe) y los eigenvalores
    de la matriz Jacobiana linealizada para el análisis de estabilidad
    (equivalente a la solución vía Transformada de Laplace).

    Jacobiana en (N*, M*):
        J = [[r1(1 - 2N*/K1 - α12·M*/K1),  -r1·α12·N*/K1 ],
             [-r2·α21·M*/K2,                r2(1-2M*/K2-α21·N*/K2)]]

    Polos de X(s) = (sI-J)⁻¹·x₀  coinciden con los eigenvalores de J.
    """
    denom = 1.0 - alpha12 * alpha21
    if abs(denom) < 1e-9:
        return None, None, None   # frontera inestable

    N_star = K1 * (1.0 - alpha12) / denom
    M_star = K2 * (1.0 - alpha21) / denom

    if N_star < 0 or M_star < 0:
        return None, None, None   # coexistencia imposible

    # Jacobiana en el equilibrio
    J = np.array([
        [r1 * (1 - 2*N_star/K1 - alpha12*M_star/K1),  -r1 * alpha12 * N_star / K1],
        [-r2 * alpha21 * M_star / K2,                   r2 * (1 - 2*M_star/K2 - alpha21*N_star/K2)]
    ])
    eigenvalues = np.linalg.eigvals(J)
    return N_star, M_star, eigenvalues


# ========================
# 3. SOLUCIÓN ANALÍTICA EXACTA (logística 1 especie)
# ========================

def analytic_solution(t_array, N0, r, K):
    """
    N(t) = K·N₀ / [N₀ + (K-N₀)·e^{-rt}]
    Obtenida por Laplace + sustitución de Bernoulli:
        U(s) = u₀/(s+r)  →  u(t)=u₀·e^{-rt}
    """
    if r == 0 or N0 == 0:
        return np.full_like(t_array, float(N0))
    denom = N0 + (K - N0) * np.exp(-r * t_array)
    denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
    return (K * N0) / denom


# ========================
# 4. LAPLACE LINEALIZADO (1 especie, cerca de K)
# ========================

def laplace_linearized(t_array, N0, r, K):
    """
    Linealización x=N-K → dx/dt=-r·x
    Laplace: X(s)=x₀/(s+r) → x(t)=x₀·e^{-rt}
    Polo simple en s=-r (siempre estable para r>0).
    """
    x0 = float(N0) - float(K)
    return K + x0 * np.exp(-r * t_array)


# ========================
# 5. LAPLACE LINEALIZADO PARA INVASIÓN (2 especies)
#
#    Perturbaciones δN, δM alrededor del equilibrio (N*,M*):
#      d/dt [δN]  =  J · [δN]
#           [δM]         [δM]
#
#    Solución en dominio de Laplace:
#      [sI - J] · X(s) = x₀
#      X(s) = (sI-J)⁻¹ · x₀
#
#    Transformada inversa → suma de exponenciales e^{λ_i · t}
# ========================

def laplace_invasion(t_array, N0, M0, N_star, M_star, J):
    """
    Solución linealizada vía Transformada de Laplace:
        x(t) = e^{Jt} · x₀    (exponencial matricial)

    Implementada como suma de modos propios:
        x(t) = Σ cᵢ · vᵢ · e^{λᵢ·t}

    Args:
        J: Jacobiana 2×2 en el equilibrio (N*, M*)
        N0, M0: condiciones iniciales
    Returns:
        N_lap, M_lap  (arrays)
    """
    eigenvalues, eigenvectors = np.linalg.eig(J)
    x0 = np.array([float(N0) - N_star, float(M0) - M_star])

    # Coeficientes c = V⁻¹ · x₀
    try:
        V_inv = np.linalg.inv(eigenvectors)
        c = V_inv @ x0
    except np.linalg.LinAlgError:
        c = np.zeros(2)

    N_lap = np.zeros(len(t_array))
    M_lap = np.zeros(len(t_array))

    for i in range(2):
        lam = eigenvalues[i].real   # parte real del eigenvalor
        mode_N = (c[i] * eigenvectors[0, i]).real * np.exp(lam * t_array)
        mode_M = (c[i] * eigenvectors[1, i]).real * np.exp(lam * t_array)
        N_lap += mode_N
        M_lap += mode_M

    N_lap = np.clip(N_lap + N_star, 0, None)
    M_lap = np.clip(M_lap + M_star, 0, None)
    return N_lap, M_lap


# ========================
# 6. MÉTODOS NUMÉRICOS
# ========================

def euler_method(N0, r, K, t_array):
    """
    Euler explícito O(h):  N_{n+1} = Nₙ + h·f(Nₙ)
    """
    N = np.zeros(len(t_array));  N[0] = float(N0)
    for i in range(len(t_array) - 1):
        h = t_array[i+1] - t_array[i]
        N[i+1] = N[i] + h * logistic_ode(N[i], t_array[i], r, K)
        N[i+1] = float(np.clip(N[i+1], 0.0, K * 1.10))
    return N


def heun_method(N0, r, K, t_array):
    """
    Heun / RK2 O(h²):
        k₁ = f(Nₙ),  k₂ = f(Nₙ+h·k₁)
        N_{n+1} = Nₙ + h/2·(k₁+k₂)
    """
    N = np.zeros(len(t_array));  N[0] = float(N0)
    for i in range(len(t_array) - 1):
        h  = t_array[i+1] - t_array[i]
        k1 = logistic_ode(N[i],        t_array[i],   r, K)
        k2 = logistic_ode(N[i]+h*k1,   t_array[i+1], r, K)
        N[i+1] = N[i] + (h/2.0) * (k1 + k2)
        N[i+1] = float(np.clip(N[i+1], 0.0, K * 1.10))
    return N


def euler_lv(N0, M0, r1, r2, K1, K2, alpha12, alpha21, t_array):
    """
    Euler para sistema Lotka-Volterra competitivo (2 especies).
    O(h) — mismo esquema que el escalar pero vectorial.
    """
    N = np.zeros(len(t_array));  N[0] = float(N0)
    M = np.zeros(len(t_array));  M[0] = float(M0)
    for i in range(len(t_array) - 1):
        h     = t_array[i+1] - t_array[i]
        state = np.array([N[i], M[i]])
        d     = lv_odes(state, t_array[i], r1, r2, K1, K2, alpha12, alpha21)
        N[i+1] = float(np.clip(N[i] + h * d[0], 0, K1 * 1.1))
        M[i+1] = float(np.clip(M[i] + h * d[1], 0, K2 * 1.1))
    return N, M


def heun_lv(N0, M0, r1, r2, K1, K2, alpha12, alpha21, t_array):
    """
    Heun para Lotka-Volterra.
    O(h²) — predictor-corrector vectorial.
    """
    N = np.zeros(len(t_array));  N[0] = float(N0)
    M = np.zeros(len(t_array));  M[0] = float(M0)
    for i in range(len(t_array) - 1):
        h      = t_array[i+1] - t_array[i]
        s0     = np.array([N[i], M[i]])
        k1     = lv_odes(s0,       t_array[i],   r1, r2, K1, K2, alpha12, alpha21)
        k2     = lv_odes(s0+h*k1,  t_array[i+1], r1, r2, K1, K2, alpha12, alpha21)
        s1     = s0 + (h/2.0) * (k1 + k2)
        N[i+1] = float(np.clip(s1[0], 0, K1 * 1.1))
        M[i+1] = float(np.clip(s1[1], 0, K2 * 1.1))
    return N, M


# ========================
# 7. ERROR RELATIVO
# ========================

def relative_error(numerical, analytical):
    denom = np.where(np.abs(analytical) < 1e-10, 1e-10, np.abs(analytical))
    return np.abs(numerical - analytical) / denom * 100.0


# ========================
# 8. ESTABILIDAD NUMÉRICA
# ========================

def check_stability(r, h):
    h_max_euler = 2.0 / r if r > 0 else float('inf')
    h_max_heun  = 2.5 / r if r > 0 else float('inf')
    return {
        'euler_stable': h < h_max_euler,
        'heun_stable':  h < h_max_heun,
        'h_max_euler':  h_max_euler,
        'h_max_heun':   h_max_heun,
        'h_actual':     h,
    }


def _time_to_fraction(t_array, N_array, K, fraction=0.95):
    threshold = fraction * K
    idx = np.argmax(N_array >= threshold)
    return float(t_array[idx]) if idx > 0 else float(t_array[-1])


# ========================
# 9. FUNCIÓN PRINCIPAL
# ========================

def show_analysis(N0, r_frame, K, t_max=30, steps=500,
                  simulation_history=None,
                  microbe_name="E. coli", factor_values=None,
                  # ── Parámetros de invasión (opcionales) ──────────────
                  invasion_active=False,
                  invader_name="Invasor",
                  N0_native=None,    # bacterias nativas al llamar M
                  M0_invader=None,   # bacterias invasoras al llamar M
                  r_frame_invader=None,
                  invasion_history=None):  # [(día, n_nativas, n_invasoras), ...]
    """
    Genera análisis matemático completo y lo guarda como PNG.

    Modo normal:  muestra modelo logístico (1 especie).
    Modo invasión: añade panel Lotka-Volterra competitivo con
                   Euler, Heun, Laplace y análisis de estabilidad.
    """
    import matplotlib
    import matplotlib.pyplot as plt
    import matplotlib.gridspec as gridspec
    import os
    from datetime import datetime

    for backend in ["TkAgg", "Qt5Agg", "GTK3Agg", "Agg"]:
        try:
            matplotlib.use(backend)
            plt.figure(); plt.close()
            break
        except Exception:
            continue

    # ── Conversión de tasas ───────────────────────────────────────────────
    r  = frame_rate_to_daily_r(float(r_frame), fps=FPS_SIM)
    r2 = frame_rate_to_daily_r(float(r_frame_invader), fps=FPS_SIM) \
         if r_frame_invader else r * 0.85

    N0  = float(max(1, N0))
    K   = float(max(2, K))

    # Población inicial para curva S completa
    if N0 >= K * 0.80:
        N0_plot = K * 0.05
    elif N0 >= K * 0.40:
        N0_plot = K * 0.10
    else:
        N0_plot = N0

    # ── Vector de tiempo ─────────────────────────────────────────────────
    t = np.linspace(0, t_max, steps)
    h = t[1] - t[0]

    stab = check_stability(r, h)
    if not stab['euler_stable']:
        steps_needed = int(np.ceil(t_max * r * 3))
        t = np.linspace(0, t_max, max(steps, steps_needed))
        h = t[1] - t[0]
        stab = check_stability(r, h)

    # ── Soluciones logísticas (1 especie) ─────────────────────────────────
    N_ana     = analytic_solution(t, N0_plot, r, K)
    N_euler   = euler_method(N0_plot, r, K, t)
    N_heun    = heun_method(N0_plot, r, K, t)
    N_laplace = laplace_linearized(t, N0_plot, r, K)

    err_euler = relative_error(N_euler,   N_ana)
    err_heun  = relative_error(N_heun,    N_ana)
    err_lap   = relative_error(N_laplace, N_ana)

    eps_lin   = abs(N0_plot - K) / K
    euler_max = float(np.max(err_euler));  euler_mean = float(np.mean(err_euler))
    heun_max  = float(np.max(err_heun));   heun_mean  = float(np.mean(err_heun))
    mejora    = max(0.0, euler_mean - heun_mean)
    t95       = _time_to_fraction(t, N_ana, K, 0.95)
    t50       = _time_to_fraction(t, N_ana, K, 0.50)
    N_eq      = float(N_ana[-1])

    # ── Parámetros Lotka-Volterra ─────────────────────────────────────────
    lv_active = invasion_active and (M0_invader is not None) and (M0_invader > 0)

    if lv_active:
        n0_nat = float(N0_native  or max(1, N0 * 0.7))
        m0_inv = float(M0_invader or max(1, N0 * 0.3))

        # K proporcional a la tasa de cada especie (invasor más agresivo → K mayor)
        ratio_r = r2 / r if r > 0 else 1.0
        K1 = K
        K2 = float(np.clip(K * ratio_r, K * 0.4, K * 1.4))

        # ── Coeficientes de competencia derivados de las tasas reales ────
        # La idea: si el invasor crece más rápido (r2 > r1), ejerce más presión
        # sobre el nativo (α₁₂ > 1) y el nativo le afecta menos (α₂₁ < 1).
        #
        # Fórmula calibrada:
        #   α₁₂ = r2/r1  (presión invasor → nativo, proporcional a su ventaja)
        #   α₂₁ = r1/r2  (presión nativo  → invasor, inversamente proporcional)
        # Acotados en [0.3, 2.5] para evitar valores sin sentido biológico.
        alpha12 = float(np.clip(r2 / r,  0.30, 2.50))   # invasor → nativo
        alpha21 = float(np.clip(r  / r2, 0.30, 2.50))   # nativo  → invasor

        # Si ambas tasas son muy similares usamos valores ligeramente asimétricos
        # para reflejar que el invasor siempre tiene ventaja de colonización
        if abs(alpha12 - 1.0) < 0.05:
            alpha12 = 1.10
            alpha21 = 0.90

        # Soluciones numéricas LV
        N_eu_lv, M_eu_lv = euler_lv(n0_nat, m0_inv, r, r2, K1, K2,
                                     alpha12, alpha21, t)
        N_hu_lv, M_hu_lv = heun_lv( n0_nat, m0_inv, r, r2, K1, K2,
                                     alpha12, alpha21, t)

        # Estabilidad Laplace LV
        N_star, M_star, eigenvalues = lv_equilibrium(r, r2, K1, K2,
                                                      alpha12, alpha21)
        lv_eq_exists = N_star is not None

        if lv_eq_exists:
            # Jacobiana para la solución vía Laplace
            J_lv = np.array([
                [r  * (1 - 2*N_star/K1 - alpha12*M_star/K1),
                 -r  * alpha12 * N_star / K1],
                [-r2 * alpha21 * M_star / K2,
                 r2  * (1 - 2*M_star/K2 - alpha21*N_star/K2)]
            ])
            N_lap_lv, M_lap_lv = laplace_invasion(t, n0_nat, m0_inv,
                                                   N_star, M_star, J_lv)
            lam_real = eigenvalues.real
            stable_lv = np.all(lam_real < 0)
        else:
            N_lap_lv = M_lap_lv = None
            stable_lv = False
            eigenvalues = np.array([0+0j, 0+0j])

    # ── Figura ────────────────────────────────────────────────────────────
    plt.style.use("dark_background")

    n_rows = 4 if lv_active else 3
    fig = plt.figure(figsize=(17, 5 * n_rows), facecolor="#07070f")

    dias_actuales = simulation_history[-1][0] \
        if simulation_history and len(simulation_history) > 0 else 0.0

    titulo_n0 = f"N₀={int(N0_plot)}" + (f" (curva ajust., real={int(N0)})" if N0_plot != N0 else "")
    if lv_active:
        modo_txt = (f"  |  INVASION: {invader_name}   "
                    f"Nativas={int(n0_nat)}  Invasoras={int(m0_inv)}  Total={int(N0)}")
    else:
        modo_txt = ""
    fig.suptitle(
        f"Analisis Matematico — {microbe_name}{modo_txt}\n"
        f"r={r:.4f} dias-1  (p_frame={r_frame:.5f})   K={int(K)}   {titulo_n0}   "
        f"h={h:.4f} dias     Dia simulado: {dias_actuales:.2f}",
        fontsize=11, color="white", fontweight="bold", y=0.995
    )

    gs = gridspec.GridSpec(
        n_rows, 3, figure=fig,
        hspace=0.55, wspace=0.38,
        left=0.07, right=0.97,
        top=0.965, bottom=0.04
    )

    C_ANA     = "#00ff88"
    C_EULER   = "#ff6644"
    C_HEUN    = "#44aaff"
    C_LAPLACE = "#ffdd44"
    C_REAL    = "#ff44ff"
    C_NAT     = "#00ff88"
    C_INV     = "#ff4455"
    C_LAP_LV  = "#ffaa00"

    def _ax_style(ax, title=""):
        if title:
            ax.set_title(title, color="white", fontsize=9.5, pad=4)
        ax.tick_params(colors="lightgray", labelsize=8)
        ax.set_facecolor("#080818")
        for sp in ax.spines.values():
            sp.set_color("#2a2a4a")
        ax.grid(alpha=0.12, color="gray", linewidth=0.6)

    def fmt_err(v):
        return f"{v:.2e}%" if v < 0.01 else f"{v:.3f}%"

    # ─────────────────────────────────────────────────────────────────────
    # FILA 0 — Comparación logística principal
    # ─────────────────────────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, :2])
    ax1.plot(t, N_ana,     color=C_ANA,     lw=2.2, label="Analítica exacta",            zorder=5)
    ax1.plot(t, N_euler,   color=C_EULER,   lw=1.6, label="Euler O(h)",            ls="--")
    ax1.plot(t, N_heun,    color=C_HEUN,    lw=1.6, label="Heun O(h²)",            ls="-.")
    ax1.plot(t, N_laplace, color=C_LAPLACE, lw=1.4, label=f"Laplace (ε={eps_lin:.2f})", ls=":", alpha=0.85)
    ax1.axhline(K,   color="gray",    lw=1.0, ls="--", alpha=0.5, label=f"K = {int(K)}")
    ax1.axhline(K/2, color="#555577", lw=0.8, ls=":",  alpha=0.4, label=f"K/2 = {int(K/2)}")
    ax1.axvline(t50, color=C_HEUN,  lw=0.8, ls=":", alpha=0.6)
    ax1.axvline(t95, color=C_EULER, lw=0.8, ls=":", alpha=0.6)
    ax1.text(t50 + 0.3, K * 0.05, f"t₅₀={t50:.1f}d", color=C_HEUN,  fontsize=7)
    ax1.text(t95 + 0.3, K * 0.05, f"t₉₅={t95:.1f}d", color=C_EULER, fontsize=7)
    validez = "válida" if eps_lin < 0.3 else "⚠ aprox. lejana"
    ax1.set_xlabel("Tiempo (días simulados)", color="lightgray", fontsize=9)
    ax1.set_ylabel("Población N(t)", color="lightgray", fontsize=9)
    ax1.legend(fontsize=8, loc="lower right",
               facecolor="#111122", edgecolor="#333355", framealpha=0.8)
    _ax_style(ax1, f"Comparación de Soluciones — Laplace {validez} (ε={eps_lin:.2f})")

    # Fila 0 col 2 — Historia real vs modelo
    ax2 = fig.add_subplot(gs[0, 2])
    if simulation_history and len(simulation_history) > 1:
        t_real = [s[0] for s in simulation_history]
        n_real = [s[1] for s in simulation_history]
        ax2.plot(t_real, n_real, color=C_REAL, lw=1.6, label="Simulación real", alpha=0.9)
        ax2.plot(t, N_ana, color=C_ANA, lw=1.4, ls="--", alpha=0.6, label="Modelo logístico")
        ax2.axhline(K, color="gray", lw=0.8, ls="--", alpha=0.4)
        ax2.legend(fontsize=7, facecolor="#111122", edgecolor="#333355")
        t_end = max(t_real[-1] * 1.3, 2.0)
        ax2.set_xlim(0, t_end)
    else:
        ax2.text(0.5, 0.5,
                 "Simula un rato antes\nde presionar M",
                 ha="center", va="center", color="#888",
                 transform=ax2.transAxes, fontsize=9)
    ax2.set_xlabel("Tiempo (días)", color="lightgray", fontsize=9)
    ax2.set_ylabel("Población",    color="lightgray", fontsize=9)
    _ax_style(ax2, "Simulación Real vs Modelo Logístico")

    # ─────────────────────────────────────────────────────────────────────
    # FILA 1 — Errores relativos (Euler, Heun, Laplace)
    # ─────────────────────────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.fill_between(t, err_euler, alpha=0.25, color=C_EULER)
    ax3.plot(t, err_euler, color=C_EULER, lw=1.6)
    idx_max = int(np.argmax(err_euler))
    ax3.annotate(fmt_err(err_euler[idx_max]),
                 xy=(t[idx_max], err_euler[idx_max]),
                 xytext=(t[idx_max]*0.4 + t_max*0.05, err_euler[idx_max]*0.7),
                 color=C_EULER, fontsize=8,
                 arrowprops=dict(arrowstyle="->", color=C_EULER, lw=1.2))
    stab_label = "✔ ESTABLE" if stab['euler_stable'] else "✗ INESTABLE"
    ax3.set_xlabel("Tiempo (días)", color="lightgray", fontsize=9)
    ax3.set_ylabel("Error %",       color="lightgray", fontsize=9)
    _ax_style(ax3, f"Error Euler [{stab_label}]  max={fmt_err(euler_max)}")

    ax4 = fig.add_subplot(gs[1, 1])
    ax4.fill_between(t, err_heun, alpha=0.25, color=C_HEUN)
    ax4.plot(t, err_heun, color=C_HEUN, lw=1.6)
    idx_max2 = int(np.argmax(err_heun))
    ax4.annotate(fmt_err(err_heun[idx_max2]),
                 xy=(t[idx_max2], err_heun[idx_max2]),
                 xytext=(t[idx_max2]*0.4 + t_max*0.05, err_heun[idx_max2]*0.7),
                 color=C_HEUN, fontsize=8,
                 arrowprops=dict(arrowstyle="->", color=C_HEUN, lw=1.2))
    ax4.set_xlabel("Tiempo (días)", color="lightgray", fontsize=9)
    ax4.set_ylabel("Error %",       color="lightgray", fontsize=9)
    _ax_style(ax4, f"Error Heun [O(h²)]  max={fmt_err(heun_max)}")

    ax5 = fig.add_subplot(gs[1, 2])
    ax5.fill_between(t, err_lap, alpha=0.25, color=C_LAPLACE)
    ax5.plot(t, err_lap, color=C_LAPLACE, lw=1.6)
    t_valid = t_max * 0.3
    ax5.axvspan(0, t_valid, alpha=0.07, color=C_LAPLACE,
                label=f"Zona válida (t<{t_valid:.1f}d)")
    ax5.legend(fontsize=7, facecolor="#111122", edgecolor="#333355")
    ax5.set_xlabel("Tiempo (días)", color="lightgray", fontsize=9)
    ax5.set_ylabel("Error %",       color="lightgray", fontsize=9)
    _ax_style(ax5, f"Error Laplace (ε_lin={eps_lin:.2f})")

    # ─────────────────────────────────────────────────────────────────────
    # FILA 2 — Panel de métricas + ecuaciones + factores (siempre presente)
    # ─────────────────────────────────────────────────────────────────────
    row_metrics = 2 if not lv_active else 3

    ax_met = fig.add_subplot(gs[row_metrics, :])
    ax_met.set_facecolor("#05050f")
    ax_met.axis("off")

    stab_euler_s = "✔ ESTABLE" if stab['euler_stable'] else "✗ INESTABLE"
    stab_heun_s  = "✔ ESTABLE" if stab['heun_stable']  else "✗ INESTABLE"

    metrics_text = (
        "  MÉTRICAS DE PRECISIÓN\n"
        f"  r (días⁻¹):   {r:.5f}   ←  p_frame={r_frame:.5f}\n"
        f"  h (paso):      {h:.5f}   h_max Euler: {stab['h_max_euler']:.5f}\n"
        f"  Euler  [{stab_euler_s}]  Error máx: {euler_max:8.4f}%   medio: {euler_mean:8.4f}%\n"
        f"  Heun   [{stab_heun_s}]   Error máx: {heun_max:8.4f}%   medio: {heun_mean:8.4f}%\n"
        f"  Mejora Heun/Euler: {mejora:.4f}% promedio\n"
        f"  Laplace  ε_lin={eps_lin:.3f}  ({'válida' if eps_lin<0.3 else '⚠ lejana'})\n"
        f"  N(∞) ≈ {N_eq:.1f}   t₅₀ ≈ {t50:.2f}d   t₉₅ ≈ {t95:.2f}d"
    )

    eq_text = (
        "  MODELO MATEMÁTICO\n"
        "  ED:        dN/dt = r·N·(1 - N/K)\n"
        "  Analítica: N(t) = K·N₀/[N₀+(K-N₀)·e^{-rt}]\n"
        "  Laplace:   X(s) = x₀/(s+r)  →  N≈K+(N₀-K)·e^{-rt}\n"
        "  Euler:     N_{n+1} = Nₙ + h·f(Nₙ)            O(h)\n"
        "  Heun:      N_{n+1} = Nₙ+h/2·(k₁+k₂)          O(h²)\n"
        f"  Conv. r:   r = -fps·ln(1-p_frame)"
    )

    factors_text = ""
    if factor_values:
        factors_text = (
            "  CONDICIONES ACTUALES\n"
            f"  Temp:      {factor_values.get('temp',0):.1f} °C\n"
            f"  Humedad:   {factor_values.get('humidity',0):.0f} %\n"
            f"  pH:        {factor_values.get('ph',0):.2f}\n"
            f"  Luz UV:    {factor_values.get('light',0):.0f} %\n"
            f"  Nutrientes:{factor_values.get('nutrients',0):.1f} %"
        )

    ax_met.text(0.01, 0.98, metrics_text, transform=ax_met.transAxes,
                color="#44ffaa", fontsize=8, va="top", fontfamily="monospace",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#061206",
                          edgecolor="#1a4a1a", alpha=0.9))
    ax_met.text(0.40, 0.98, eq_text, transform=ax_met.transAxes,
                color="#aaddff", fontsize=8, va="top", fontfamily="monospace",
                bbox=dict(boxstyle="round,pad=0.4", facecolor="#060612",
                          edgecolor="#1a1a44", alpha=0.9))
    if factors_text:
        ax_met.text(0.76, 0.98, factors_text, transform=ax_met.transAxes,
                    color="#ffdd88", fontsize=8, va="top", fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.4", facecolor="#141200",
                              edgecolor="#443a00", alpha=0.9))

    # ─────────────────────────────────────────────────────────────────────
    # FILA 2 (solo si invasión) — Paneles Lotka-Volterra
    # ─────────────────────────────────────────────────────────────────────
    if lv_active:

        # ── 2-A: Dinámica LV Euler vs Heun ───────────────────────────────
        ax_lv1 = fig.add_subplot(gs[2, :2])

        ax_lv1.plot(t, N_eu_lv, color=C_NAT,  lw=1.5, ls="--",
                    label=f"Euler — Nativas ({microbe_name})")
        ax_lv1.plot(t, M_eu_lv, color=C_INV,  lw=1.5, ls="--",
                    label=f"Euler — Invasoras ({invader_name})")
        ax_lv1.plot(t, N_hu_lv, color=C_NAT,  lw=2.0,
                    label=f"Heun — Nativas")
        ax_lv1.plot(t, M_hu_lv, color=C_INV,  lw=2.0,
                    label=f"Heun — Invasoras")

        if lv_eq_exists and N_lap_lv is not None:
            ax_lv1.plot(t, N_lap_lv, color="#aaffaa", lw=1.3, ls=":",
                        alpha=0.8, label="Laplace — Nativas (lin.)")
            ax_lv1.plot(t, M_lap_lv, color="#ffaaaa", lw=1.3, ls=":",
                        alpha=0.8, label="Laplace — Invasoras (lin.)")
            ax_lv1.axhline(N_star, color=C_NAT,  lw=0.7, ls="--",
                           alpha=0.35, label=f"N* = {N_star:.0f}")
            ax_lv1.axhline(M_star, color=C_INV,  lw=0.7, ls="--",
                           alpha=0.35, label=f"M* = {M_star:.0f}")

        # Historia real de invasión
        if invasion_history and len(invasion_history) > 1:
            t_ih  = [s[0] for s in invasion_history]
            n_ih  = [s[1] for s in invasion_history]
            m_ih  = [s[2] for s in invasion_history]
            ax_lv1.plot(t_ih, n_ih, color=C_NAT,  lw=2.5, alpha=0.55,
                        marker=".", markersize=3, label="Real — Nativas")
            ax_lv1.plot(t_ih, m_ih, color=C_INV,  lw=2.5, alpha=0.55,
                        marker=".", markersize=3, label="Real — Invasoras")

        ax_lv1.set_xlabel("Tiempo (días simulados)", color="lightgray", fontsize=9)
        ax_lv1.set_ylabel("Población", color="lightgray", fontsize=9)
        ax_lv1.legend(fontsize=7, loc="upper right",
                      facecolor="#111122", edgecolor="#333355",
                      framealpha=0.85, ncol=2)
        estab_txt = ("ESTABLE ✔" if (lv_eq_exists and stable_lv)
                     else "INESTABLE ✗" if lv_eq_exists else "sin coexistencia")
        _ax_style(ax_lv1,
                  f"Lotka-Volterra Competitivo — Euler vs Heun vs Laplace  "
                  f"[α₁₂={alpha12}  α₂₁={alpha21}  Eq. {estab_txt}]")

        # ── 2-B: Plano de fase ────────────────────────────────────────────
        ax_lv2 = fig.add_subplot(gs[2, 2])

        ax_lv2.plot(N_eu_lv, M_eu_lv, color=C_EULER, lw=1.3,
                    ls="--", label="Euler", alpha=0.7)
        ax_lv2.plot(N_hu_lv, M_hu_lv, color=C_HEUN,  lw=1.8,
                    label="Heun")
        if lv_eq_exists and N_lap_lv is not None:
            ax_lv2.plot(N_lap_lv, M_lap_lv, color=C_LAP_LV, lw=1.3,
                        ls=":", label="Laplace (lin.)", alpha=0.8)

        # Punto de equilibrio
        if lv_eq_exists:
            ax_lv2.scatter([N_star], [M_star],
                           color="white", s=60, zorder=5,
                           label=f"Eq. ({N_star:.0f}, {M_star:.0f})")
        # Punto inicial
        ax_lv2.scatter([n0_nat], [m0_inv],
                       color="#ffff44", s=40, zorder=5, marker="^",
                       label=f"t=0 ({int(n0_nat)}, {int(m0_inv)})")

        # Nulclinas N' = 0 y M' = 0
        n_vals = np.linspace(0, K1 * 1.05, 200)
        # N-nulclina (M cuando dN/dt=0): M = K1/α12 · (1 - N/K1)
        M_nc_N = (K1 / alpha12) * (1.0 - n_vals / K1)
        # M-nulclina (M cuando dM/dt=0): M = K2 · (1 - α21·N/K2)
        M_nc_M = K2 * (1.0 - alpha21 * n_vals / K2)
        ax_lv2.plot(n_vals, M_nc_N, color=C_NAT,  lw=1.0, ls="--",
                    alpha=0.5, label="Nulclina N'=0")
        ax_lv2.plot(n_vals, M_nc_M, color=C_INV,  lw=1.0, ls="--",
                    alpha=0.5, label="Nulclina M'=0")

        ax_lv2.set_xlim(0, K1 * 1.05)
        ax_lv2.set_ylim(0, K2 * 1.05)
        ax_lv2.set_xlabel("Nativas N",   color="lightgray", fontsize=9)
        ax_lv2.set_ylabel("Invasoras M", color="lightgray", fontsize=9)
        ax_lv2.legend(fontsize=6.5, loc="upper right",
                      facecolor="#111122", edgecolor="#333355",
                      framealpha=0.85)
        _ax_style(ax_lv2, "Plano de Fase  N vs M")

        # ── Extra en panel de métricas: datos LV ─────────────────────────
        # Determinar quien gana según los coeficientes
        if alpha12 > 1.0 and alpha21 < 1.0:
            dominante = f"{invader_name} GANA"
        elif alpha12 < 1.0 and alpha21 > 1.0:
            dominante = f"{microbe_name} GANA"
        else:
            dominante = "Resultado incierto"

        if lv_eq_exists:
            lam1, lam2 = eigenvalues[0], eigenvalues[1]
            lv_info = (
                f"  LOTKA-VOLTERRA\n"
                f"  r1={r:.4f}  r2={r2:.4f} dias-1\n"
                f"  K1={int(K1)}  K2={int(K2)}\n"
                f"  a12={alpha12:.3f} (inv->nat)  a21={alpha21:.3f} (nat->inv)\n"
                f"  N*={N_star:.0f}   M*={M_star:.0f}\n"
                f"  L1={lam1.real:+.4f}  L2={lam2.real:+.4f}\n"
                f"  Eq: {'ESTABLE (Re<0)' if stable_lv else 'INESTABLE (Re>0)'}\n"
                f"  Laplace: X(s)=(sI-J)-1*x0"
            )
        else:
            # Calcular quien gana en exclusión competitiva
            # K1/alpha12 vs K2  y  K2/alpha21 vs K1
            cond_nat_wins  = (K1 / alpha12 > K2) and (K2 / alpha21 < K1)
            cond_inv_wins  = (K1 / alpha12 < K2) and (K2 / alpha21 > K1)
            if cond_inv_wins:
                resultado = f"Exclusion: {invader_name} elimina nativas"
            elif cond_nat_wins:
                resultado = f"Exclusion: nativas resisten"
            else:
                resultado = f"Exclusion competitiva\n  (resultado depende N0,M0)"
            lv_info = (
                f"  LOTKA-VOLTERRA\n"
                f"  r1={r:.4f}  r2={r2:.4f} dias-1\n"
                f"  K1={int(K1)}  K2={int(K2)}\n"
                f"  a12={alpha12:.3f} (inv->nat)  a21={alpha21:.3f} (nat->inv)\n"
                f"  Sin coexistencia estable:\n"
                f"  {resultado}\n"
                f"  ({dominante})\n"
                f"  Laplace: eigenvalores no aplicables"
            )

        # Añadir al panel de métricas (fila 3)
        ax_met.text(0.57, 0.98, lv_info, transform=ax_met.transAxes,
                    color="#ffaacc", fontsize=8, va="top", fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.4", facecolor="#140810",
                              edgecolor="#441830", alpha=0.9))

        # Error numérico LV (Euler vs Heun sobre nativas)
        err_lv_N = relative_error(N_eu_lv, N_hu_lv)
        err_lv_M = relative_error(M_eu_lv, M_hu_lv)
        err_lv_info = (
            "  ERROR LV (Euler vs Heun)\n"
            f"  Nativas  máx: {np.max(err_lv_N):.3f}%\n"
            f"           med: {np.mean(err_lv_N):.4f}%\n"
            f"  Invasoras máx: {np.max(err_lv_M):.3f}%\n"
            f"           med:  {np.mean(err_lv_M):.4f}%"
        )
        ax_met.text(0.57, 0.42, err_lv_info, transform=ax_met.transAxes,
                    color="#ffccaa", fontsize=8, va="top", fontfamily="monospace",
                    bbox=dict(boxstyle="round,pad=0.4", facecolor="#141008",
                              edgecolor="#442800", alpha=0.9))

    # ── Guardar ───────────────────────────────────────────────────────────
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(
        os.path.dirname(__file__), "data",
        f"analisis_{'invasion_' if lv_active else ''}{timestamp}.png"
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