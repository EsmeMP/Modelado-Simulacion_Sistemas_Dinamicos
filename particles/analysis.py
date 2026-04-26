import os
import sys
import subprocess
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from datetime import datetime

def save(c, k_voz, v0, dt, num_particles,
        analytic_log, numeric_log, energy_log, voice_log, final_frame):

    import cv2
    cv2.imwrite("resultado_simulacion.png", final_frame)
    print("[info] Captura guardada: resultado_simulacion.png")

    plt.style.use("dark_background")
    fig = plt.figure(figsize=(16, 10), facecolor="#0a0a1a")
    fig.suptitle(
        f"Analisis de Simulacion — Particulas con Voz y Mano "
        f"(c={c:.4f}, k_voz={k_voz:.4f}, v0={v0}, N={num_particles})",
        fontsize=14, color="white", fontweight="bold", y=0.98
    )
    gs = gridspec.GridSpec(3, 3, figure=fig,
                        hspace=0.45, wspace=0.35,
                        left=0.07, right=0.97, top=0.93, bottom=0.07)

    C_NUMERIC  = "#ff6644"; C_ANALYTIC = "#00ff88"
    C_ENERGY   = "#ffffff"; C_VOICE    = "#ffdd44"
    C_DIFF     = "#44aaff"; C_EPEAK    = "#ff9900"

    def style_ax(ax):
        ax.tick_params(colors="lightgray"); ax.set_facecolor("#080818")
        ax.spines[:].set_color("#333355");  ax.grid(alpha=0.15, color="gray")
        ax.set_xlabel("Tiempo (frames)", color="lightgray")

    ax1 = fig.add_subplot(gs[0, :2])
    ax1.plot(analytic_log, color=C_ANALYTIC, lw=2.5, label="Analitica v(t)=v0*e^(-ct)", zorder=5)
    ax1.plot(numeric_log,  color=C_NUMERIC,  lw=1.8, label="Numerica (vel. media)", ls="--")
    ax1.set_title("Comparacion: Velocidad Analitica vs Numerica", color="white", fontsize=11)
    ax1.set_ylabel("Velocidad", color="lightgray")
    ax1.legend(fontsize=8, loc="upper right", facecolor="#111122", edgecolor="#333355")
    style_ax(ax1)

    ax2 = fig.add_subplot(gs[0, 2])
    ax2.plot(energy_log, color=C_ENERGY, lw=1.8, label="Energia total")
    ax2.fill_between(range(len(energy_log)), energy_log, alpha=0.15, color=C_ENERGY)
    ax2.set_title("Energia Total", color="white", fontsize=11)
    ax2.set_ylabel("Energia", color="lightgray")
    ax2.legend(fontsize=7, facecolor="#111122", edgecolor="#333355")
    style_ax(ax2)

    ax3 = fig.add_subplot(gs[1, 0])
    ax3.fill_between(range(len(voice_log)), voice_log, alpha=0.3, color=C_VOICE)
    ax3.plot(voice_log, color=C_VOICE, lw=1.8)
    ax3.set_title("Nivel de Voz (Audio)", color="white", fontsize=11)
    ax3.set_ylabel("Amplitud", color="lightgray")
    if voice_log:
        idx_v = int(np.argmax(voice_log))
        ax3.annotate(f"pico={voice_log[idx_v]:.2f}",
                    xy=(idx_v, voice_log[idx_v]),
                    xytext=(max(0, idx_v - len(voice_log)*0.15), voice_log[idx_v]*0.8),
                    color=C_VOICE, fontsize=8,
                    arrowprops=dict(arrowstyle="->", color=C_VOICE))
    style_ax(ax3)

    ax4 = fig.add_subplot(gs[1, 1])
    min_len = min(len(analytic_log), len(numeric_log))
    diff    = [abs(analytic_log[i] - numeric_log[i]) for i in range(min_len)]
    ax4.fill_between(range(len(diff)), diff, alpha=0.3, color=C_DIFF)
    ax4.plot(diff, color=C_DIFF, lw=1.8)
    ax4.set_title("Diferencia |Analitica - Numerica|", color="white", fontsize=11)
    ax4.set_ylabel("Error absoluto", color="lightgray")
    if diff:
        idx_d = int(np.argmax(diff))
        ax4.annotate(f"{diff[idx_d]:.4f}",
                    xy=(idx_d, diff[idx_d]),
                    xytext=(max(0, idx_d - len(diff)*0.15), diff[idx_d]*0.8),
                    color=C_DIFF, fontsize=8,
                    arrowprops=dict(arrowstyle="->", color=C_DIFF))
    style_ax(ax4)

    ax5 = fig.add_subplot(gs[1, 2])
    ax5.plot(energy_log, color=C_EPEAK, lw=2.0)
    ax5.fill_between(range(len(energy_log)), energy_log, alpha=0.2, color=C_EPEAK)
    ax5.axhline(0, color="gray", lw=0.8, ls="--")
    if energy_log:
        idx_peak = int(np.argmax(energy_log))
        ax5.axvline(idx_peak, color=C_EPEAK, lw=1, ls=":", alpha=0.7)
        ax5.annotate(f"pico t={idx_peak}",
                    xy=(idx_peak, energy_log[idx_peak]),
                    xytext=(min(idx_peak+len(energy_log)*0.05, len(energy_log)-1),
                    energy_log[idx_peak]*0.85),
                    color=C_EPEAK, fontsize=8,
                    arrowprops=dict(arrowstyle="->", color=C_EPEAK))
    ax5.set_title("Pico de Energia del Sistema", color="white", fontsize=11)
    ax5.set_ylabel("Energia", color="lightgray")
    style_ax(ax5)

    ax6 = fig.add_subplot(gs[2, :])
    ax6.set_facecolor("#05050f"); ax6.axis("off")

    mean_numeric  = float(np.mean(numeric_log))  if numeric_log  else 0.0
    mean_analytic = float(np.mean(analytic_log)) if analytic_log else 0.0
    mean_energy   = float(np.mean(energy_log))   if energy_log   else 0.0
    max_energy    = float(np.max(energy_log))    if energy_log   else 0.0
    mean_voice    = float(np.mean(voice_log))    if voice_log    else 0.0
    mean_diff     = float(np.mean(diff)) if diff else 0.0
    max_diff      = float(np.max(diff))  if diff else 0.0

    ax6.text(0.01, 0.97,
            f"  METRICAS FINALES\n"
            f"  Vel. analitica media:  {mean_analytic:.4f}\n"
            f"  Vel. numerica media:   {mean_numeric:.4f}\n"
            f"  Error medio: {mean_diff:.4f}   Error max: {max_diff:.4f}\n"
            f"  Energia media: {mean_energy:.2f}   max: {max_energy:.2f}\n"
            f"  Voz media: {mean_voice:.3f}",
            transform=ax6.transAxes, color="#44ffaa", fontsize=8.2,
            va="top", fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#0a1a0a", edgecolor="#224422", alpha=0.8))
    ax6.text(0.33, 0.97,
            "  MODELO MATEMATICO\n"
            "  Sistema dinamico: particulas con amortiguamiento y voz\n\n"
            "  ED:        dv/dt = -c*v + k_voz*ruido(t)\n"
            "  Laplace:   V(s) = v0 / (s + c)\n"
            "  Analitica: v(t) = v0*e^(-c*t)\n"
            "  Euler:     v_(n+1) = vn + h*(-c*vn + k_voz*rn)",
            transform=ax6.transAxes, color="#aaddff", fontsize=8.2,
            va="top", fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#0a0a1a", edgecolor="#222244", alpha=0.8))
    ax6.text(0.75, 0.97,
            f"  PARAMETROS\n"
            f"  c      = {c:.4f}\n"
            f"  k_voz  = {k_voz:.4f}\n"
            f"  v0     = {v0}\n"
            f"  dt     = {dt}\n"
            f"  N part.= {num_particles}",
            transform=ax6.transAxes, color="#ffdd88", fontsize=8.2,
            va="top", fontfamily="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#1a1500", edgecolor="#443300", alpha=0.8))

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"analisis_{timestamp}.png"
    plt.savefig(output_path, dpi=120, bbox_inches="tight", facecolor="#0a0a1a")
    plt.close()
    print(f"[analisis] Guardado en: {output_path}")

    try:
        abs_path = os.path.abspath(output_path)
        if sys.platform.startswith("win"):   os.startfile(abs_path)
        elif sys.platform == "darwin":        subprocess.Popen(["open",     abs_path])
        else:                                 subprocess.Popen(["xdg-open", abs_path])
    except Exception as e:
        print(f"[analisis] No se pudo abrir: {e}")