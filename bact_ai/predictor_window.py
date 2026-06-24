import threading
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import matplotlib.gridspec as gridspec
from collections import deque
from datetime import datetime
from predictor_bridge import PredictorBridge

CAPACITY = 500
HISTORY  = 30
HORIZON  = 20

DARK_BG   = '#0a0d0f'
PANEL_BG  = '#0f1512'
GREEN     = '#2ea84a'
GREEN_DIM = '#1e6030'
ORANGE    = '#e8a040'
RED       = '#e84040'
CYAN      = '#40c8e8'
TEXT_DIM  = '#3a6040'
TEXT_MID  = '#5a8060'
TEXT_HI   = '#a0c8a8'

# (clave, umbral_bajo, umbral_alto, msg_bajo, msg_alto, gesto_bajo, gesto_alto, col_bajo, col_alto)
ALERT_RULES = [
    ('nut', 0.15, 0.95,
     '+ NUTRIENTES CRITICOS',  '- NUTRIENTES ALTOS',
     'F = +NUT',               '3-IZQ = -NUT',
     RED,                      ORANGE),
    ('nut', 0.30, 0.95,
     '+ NUTRIENTES BAJOS',     '- NUTRIENTES ALTOS',
     'F = +NUT',               '3-IZQ = -NUT',
     ORANGE,                   ORANGE),
    ('hum', 0.6, 0.95,
     '+ HUMEDAD BAJA',         '- HUMEDAD ALTA',
     '2-IZQ = +HUM',           '2-DER = -HUM',
     ORANGE,                   ORANGE),
    ('temp', 20, 35,
     '+ TEMPERATURA BAJA',     '- TEMPERATURA ALTA',
     '1-IZQ = +TEMP',          '1-DER = -TEMP',
     ORANGE,                   ORANGE),
    ('ph', 6.0, 8.0,
     'pH ACIDO — sube pH',     'pH BASICO — baja pH',
     '4-IZQ = +pH',            '4-DER = -pH',
     ORANGE,                   ORANGE),
    ('uv', 0.0, 0.25,
     '',                       'UV ALTA — reduce luz',
     '',                       'MANO = -UV',
     ORANGE,                   ORANGE),
]


class PredictorWindow(threading.Thread):
    def __init__(self, bridge: PredictorBridge):
        super().__init__(daemon=True)
        self.bridge      = bridge
        self.hist_pop    = deque([100.0] * HISTORY, maxlen=HISTORY)
        self.last_state  = {}
        self.log_lines   = deque(maxlen=5)
        self.frame_count = 0

    def _calc_rate(self, s):
        temp_s = 1 - abs(s.get('temp', 30) - 30) / 30
        hum_s  = s.get('hum', 0.5)
        nut_s  = s.get('nut', 0.5)
        ph_s   = 1 - abs(s.get('ph', 7.0) - 7.0) / 3.5
        uv_s   = 1 - s.get('uv', 0.1)
        return max(-0.05, min(0.12,
            0.04*temp_s + 0.02*hum_s + 0.04*nut_s + 0.015*ph_s - 0.03*uv_s))

    def _project(self, pop, rate, steps=60):
        p = pop
        for _ in range(steps):
            p = p + rate * p * (1 - p / CAPACITY) * 0.016
        return max(0, min(CAPACITY * 1.05, p))

    def _get_status(self, pop, rate):
        if pop > CAPACITY * 0.9: return 'CRITICO', RED
        if rate < 0:              return 'DECLIVE',  ORANGE
        return 'ESTABLE', GREEN

    def _draw_bar(self, ax, y, value, max_val, color, label, val_str):
        bar_w = max(0.005, value / max_val * 0.65)
        ax.barh(y, 0.65, height=0.50, left=0.0, color='#1a2020', zorder=1)
        ax.barh(y, bar_w, height=0.50, left=0.0, color=color, alpha=0.8, zorder=2)
        ax.text(-0.02, y, label, va='center', ha='right',
                color=TEXT_MID, fontsize=9, fontfamily='monospace')
        ax.text(0.67, y, val_str, va='center', ha='left',
                color=color, fontsize=9, fontfamily='monospace', fontweight='bold')

    def _get_alerts(self, s):
        """Devuelve lista ordenada por prioridad de alertas activas. Sin duplicados."""
        alerts = []
        seen_keys = set()
        for rule in ALERT_RULES:
            key, lo, hi, msg_lo, msg_hi, gest_lo, gest_hi, col_lo, col_hi = rule
            val = s.get(key, 0)
            if val < lo and msg_lo:
                dedup = (key, 'lo', lo)
                if dedup not in seen_keys:
                    seen_keys.add(dedup)
                    alerts.append((msg_lo, col_lo, gest_lo))
                    break  # nutrientes criticos tiene prioridad sobre bajos
            elif val > hi and msg_hi:
                dedup = (key, 'hi', hi)
                if dedup not in seen_keys:
                    seen_keys.add(dedup)
                    alerts.append((msg_hi, col_hi, gest_hi))
        # segunda pasada para el resto (sin nut si ya se capturó)
        for rule in ALERT_RULES:
            key, lo, hi, msg_lo, msg_hi, gest_lo, gest_hi, col_lo, col_hi = rule
            val = s.get(key, 0)
            if val < lo and msg_lo:
                dedup = (key, 'lo', lo)
                if dedup not in seen_keys:
                    seen_keys.add(dedup)
                    alerts.append((msg_lo, col_lo, gest_lo))
            elif val > hi and msg_hi:
                dedup = (key, 'hi', hi)
                if dedup not in seen_keys:
                    seen_keys.add(dedup)
                    alerts.append((msg_hi, col_hi, gest_hi))
        return alerts

    def run(self):
        fig = plt.figure(figsize=(12, 9), facecolor=DARK_BG)
        fig.canvas.manager.set_window_title('GESTBACT AI — PREDICTOR v0.1')

        gs = gridspec.GridSpec(
            5, 2,
            figure=fig,
            height_ratios=[0.16, 0.30, 0.16, 0.26, 0.12],
            hspace=0.72, wspace=0.06,
            left=0.09, right=0.98, top=0.95, bottom=0.05
        )

        # ── Fila 0: header ───────────────────────────────────────────
        ax_hdr = fig.add_subplot(gs[0, :])
        ax_hdr.set_facecolor(PANEL_BG)
        ax_hdr.set_xticks([]); ax_hdr.set_yticks([])
        for sp in ax_hdr.spines.values():
            sp.set_edgecolor(GREEN_DIM)

        ax_hdr.text(0.01, 0.75, 'GESTBACT AI  PREDICTOR v0.1',
            transform=ax_hdr.transAxes, color=TEXT_DIM,
            fontsize=9, fontfamily='monospace', va='top')
        clock_txt = ax_hdr.text(0.40, 0.75, '  --:--:--',
            transform=ax_hdr.transAxes, color=GREEN,
            fontsize=9, fontfamily='monospace', va='top', ha='center')
        microbe_txt = ax_hdr.text(0.99, 0.75, 'Microbio: --',
            transform=ax_hdr.transAxes, color=TEXT_DIM,
            fontsize=9, fontfamily='monospace', va='top', ha='right')

        metrics = [
            (0.01,  'POBLACION',     'pop_val',    GREEN,  16),
            (0.24,  'PROYECCION+60', 'proj_val',   ORANGE, 16),
            (0.50,  'TASA',          'rate_val',   GREEN,  16),
            (0.74,  'ESTADO',        'status_val', GREEN,  12),
        ]
        metric_texts = {}
        for x, lbl, key, col, fs in metrics:
            ax_hdr.text(x, -0.55, lbl, transform=ax_hdr.transAxes,
                        color=TEXT_DIM, fontsize=7, fontfamily='monospace')
            metric_texts[key] = ax_hdr.text(x, 0.05, '---',
                transform=ax_hdr.transAxes,
                color=col, fontsize=fs, fontfamily='monospace', fontweight='bold')

        pop_val    = metric_texts['pop_val']
        proj_val   = metric_texts['proj_val']
        rate_val   = metric_texts['rate_val']
        status_val = metric_texts['status_val']

        # ── Fila 1: gráfica ──────────────────────────────────────────
        ax_graph = fig.add_subplot(gs[1, :])
        ax_graph.set_facecolor(DARK_BG)
        ax_graph.tick_params(colors=TEXT_DIM, labelsize=8)
        for sp in ax_graph.spines.values():
            sp.set_edgecolor(GREEN_DIM)
        ax_graph.set_title('Proyeccion de poblacion', loc='left',
                           color=TEXT_MID, fontsize=9, fontfamily='monospace', pad=4)

        x_hist = list(range(-HISTORY, 0))
        x_pred = list(range(0, HORIZON + 1))
        x_all  = list(range(-HISTORY, HORIZON + 1))

        ax_graph.fill_between(x_all, CAPACITY, CAPACITY * 1.1, color=RED, alpha=0.10)
        ax_graph.axhline(CAPACITY, color=RED, lw=0.6, ls='--', alpha=0.4)
        ax_graph.set_ylim(0, CAPACITY * 1.15)
        ax_graph.set_xlim(-HISTORY, HORIZON)
        ax_graph.yaxis.set_tick_params(labelcolor=TEXT_DIM)

        xticks = list(range(-HISTORY, HORIZON + 1, 5))
        ax_graph.set_xticks(xticks)
        ax_graph.set_xticklabels([f'{x:+d}s' for x in xticks],
                                  fontsize=7, color=TEXT_DIM, fontfamily='monospace')

        ax_graph.plot([], [], color=GREEN, lw=2,            label='historico')
        ax_graph.plot([], [], color=CYAN,  lw=1.5, ls='--', label='prediccion')
        ax_graph.plot([], [], color=RED,   lw=4,   alpha=0.3, label='zona critica')
        ax_graph.legend(loc='upper right', facecolor=PANEL_BG,
                        edgecolor=GREEN_DIM, labelcolor=TEXT_MID,
                        fontsize=7, framealpha=0.9)

        line_h, = ax_graph.plot(x_hist, list(self.hist_pop), color=GREEN, lw=2)
        line_p, = ax_graph.plot(x_pred, [list(self.hist_pop)[-1]] * (HORIZON + 1),
                                color=CYAN, lw=1.5, ls='--')
        ax_graph.axvline(0, color=TEXT_DIM, lw=0.5, alpha=0.4)

        # ── Fila 2: panel de ALERTAS ──────────────────────────────────
        ax_alert = fig.add_subplot(gs[2, :])
        ax_alert.set_facecolor('#060c08')
        ax_alert.set_xticks([]); ax_alert.set_yticks([])
        ax_alert.set_xlim(0, 1); ax_alert.set_ylim(0, 1)
        for sp in ax_alert.spines.values():
            sp.set_edgecolor(GREEN_DIM)
            sp.set_linewidth(2.0)

        alert1_tag  = ax_alert.text(0.01, 0.72, '[1]',
            transform=ax_alert.transAxes, color=DARK_BG,
            fontsize=10, va='top', fontfamily='monospace')
        alert1_main = ax_alert.text(0.07, 0.72, '',
            transform=ax_alert.transAxes, color=GREEN,
            fontsize=14, va='top', fontfamily='monospace', fontweight='bold')
        alert1_key  = ax_alert.text(0.99, 0.72, '',
            transform=ax_alert.transAxes, color=TEXT_HI,
            fontsize=11, va='top', ha='right', fontfamily='monospace', fontweight='bold')

        alert2_tag  = ax_alert.text(0.01, 0.18, '[2]',
            transform=ax_alert.transAxes, color=DARK_BG,
            fontsize=9, va='bottom', fontfamily='monospace')
        alert2_main = ax_alert.text(0.07, 0.18, '',
            transform=ax_alert.transAxes, color=ORANGE,
            fontsize=11, va='bottom', fontfamily='monospace')
        alert2_key  = ax_alert.text(0.99, 0.18, '',
            transform=ax_alert.transAxes, color=TEXT_MID,
            fontsize=10, va='bottom', ha='right', fontfamily='monospace')

        # ── Fila 3: factores + optima ─────────────────────────────────
        ax_fact = fig.add_subplot(gs[3, 0])
        ax_opt  = fig.add_subplot(gs[3, 1])

        for ax, title in [(ax_fact, 'FACTORES ACTUALES'), (ax_opt, 'CONFIGURACION OPTIMA')]:
            ax.set_facecolor(PANEL_BG)
            ax.set_xlim(-0.28, 0.80)
            ax.set_ylim(-0.5, 5.5)
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_edgecolor(GREEN_DIM)
            ax.text(0.01, 5.3, title, color=TEXT_DIM, fontsize=9,
                    fontfamily='monospace', va='bottom', fontweight='bold')

        FACTOR_LABELS = ['Temperatura', 'Humedad', 'Nutrientes', 'pH', 'Luz UV']
        FACTOR_KEYS   = [('temp', 60), ('hum', 1.0), ('nut', 1.0), ('ph', 9.0), ('uv', 1.0)]
        OPTIMAL_VALS  = [30/60, 0.85, 0.80, 7.0/9.0, 0.10]
        OPTIMAL_STRS  = ['30C', '85%', '80%', '7.0', '10%']
        FACTOR_COLORS = [ORANGE, CYAN, GREEN, '#a060e0', '#e0c040']

        for i, (lbl, (key, mx), opt_v, opt_s, col) in enumerate(
                zip(FACTOR_LABELS, FACTOR_KEYS, OPTIMAL_VALS, OPTIMAL_STRS, FACTOR_COLORS)):
            y = 4 - i
            self._draw_bar(ax_opt, y, opt_v, 1.0, col, lbl, opt_s)
        ax_opt.text(0.01, -0.35, 'ajusta gestos para maximizar tasa',
                    color=TEXT_DIM, fontsize=7, fontfamily='monospace')

        fact_bars = []
        fact_txts = []
        for i, (lbl, (key, mx), col) in enumerate(
                zip(FACTOR_LABELS, FACTOR_KEYS, FACTOR_COLORS)):
            y = 4 - i
            ax_fact.barh(y, 0.65, height=0.50, left=0.0, color='#1a2020', zorder=1)
            bar = ax_fact.barh(y, 0.01, height=0.50, left=0.0,
                               color=col, alpha=0.8, zorder=2)
            ax_fact.text(-0.02, y, lbl, va='center', ha='right',
                         color=TEXT_MID, fontsize=9, fontfamily='monospace')
            txt = ax_fact.text(0.67, y, '--', va='center', ha='left',
                               color=col, fontsize=9, fontfamily='monospace', fontweight='bold')
            fact_bars.append(bar)
            fact_txts.append(txt)

        # ── Fila 4: log ───────────────────────────────────────────────
        ax_log = fig.add_subplot(gs[4, :])
        ax_log.set_facecolor(PANEL_BG)
        ax_log.set_xticks([]); ax_log.set_yticks([])
        for sp in ax_log.spines.values():
            sp.set_edgecolor(GREEN_DIM)
        ax_log.text(0.005, 0.95, 'LOG',
                    transform=ax_log.transAxes, color=TEXT_DIM,
                    fontsize=8, fontfamily='monospace', va='top', fontweight='bold')
        log_texts = [
            ax_log.text(0.04 + i * 0.19, 0.92, '',
                        transform=ax_log.transAxes, color=GREEN,
                        fontsize=8, fontfamily='monospace', va='top')
            for i in range(5)
        ]

        plt.tight_layout(rect=[0, 0, 1, 1])

        # ── Animacion ─────────────────────────────────────────────────
        def _update(_):
            self.frame_count += 1
            state = self.bridge.pop()
            if state:
                self.last_state = state
                self.hist_pop.append(state.get('population', list(self.hist_pop)[-1]))

            s    = self.last_state
            pop  = list(self.hist_pop)[-1]
            rate = self._calc_rate(s)

            proj = []
            p = pop
            for _ in range(HORIZON + 1):
                proj.append(p)
                p = p + rate * p * (1 - p / CAPACITY) * 0.016
            proj_60 = self._project(pop, rate, steps=60)

            status_str, status_color = self._get_status(pop, rate)

            # header
            clock_txt.set_text(f'  {datetime.now().strftime("%H:%M:%S")}')
            microbe_txt.set_text(f'Microbio: {s.get("microbe", "--")}')
            pop_val.set_text(str(int(pop)))
            proj_val.set_text(str(int(proj_60)))
            rate_val.set_text(f'{rate*100:.2f}%')
            rate_val.set_color(GREEN if rate >= 0 else RED)
            status_val.set_text(f'{status_str}')
            status_val.set_color(status_color)

            # grafica
            line_h.set_ydata(list(self.hist_pop))
            line_p.set_ydata(proj)
            line_h.set_color(RED if status_str == 'CRITICO' else GREEN)
            current_max = max(list(self.hist_pop) + proj)
            ax_graph.set_ylim(0, max(CAPACITY * 1.15, current_max * 1.1))

            # factores
            raw_vals  = [s.get('temp', 30), s.get('hum', 0.5), s.get('nut', 0.5),
                         s.get('ph', 7.0) / 9.0, s.get('uv', 0.1)]
            max_vals  = [60, 1.0, 1.0, 1.0, 1.0]
            disp_strs = [
                f'{s.get("temp", 30):.0f}C',
                f'{s.get("hum", 0.5)*100:.0f}%',
                f'{s.get("nut", 0.5)*100:.0f}%',
                f'{s.get("ph", 7.0):.1f}',
                f'{s.get("uv", 0.1)*100:.0f}%',
            ]
            for bar, txt, val, mx, ds in zip(fact_bars, fact_txts, raw_vals, max_vals, disp_strs):
                bar[0].set_width(max(0.005, val / mx * 0.65))
                txt.set_text(ds)

            # log horizontal
            if self.frame_count % 2 == 0:
                ts = datetime.now().strftime('%H:%M:%S')
                self.log_lines.appendleft(f'{ts} {status_str[:3]} p={int(pop)}')
            for i, lt in enumerate(log_texts):
                lt.set_text(list(self.log_lines)[i] if i < len(self.log_lines) else '')
                lt.set_color(RED if 'CRI' in lt.get_text() else
                             ORANGE if 'DEC' in lt.get_text() else GREEN)

            # ── alertas ───────────────────────────────────────────────
            active       = self._get_alerts(s)
            invasion_pct = s.get('invasion_pct', 0.0)
            hay_invasion = invasion_pct > 0.05

            a1_msg = a1_key = a2_msg = a2_key = ''
            a1_col = a2_col = DARK_BG
            border_col = GREEN_DIM

            if hay_invasion:
                # PRIORIDAD 1: invasión — antibiótico inmediato
                blink      = '#ff2020' if self.frame_count % 2 == 0 else '#990000'
                border_col = blink
                a1_msg = 'INVASION DETECTADA — aplica antibiotico'
                a1_col = RED
                a1_key = 'B = antibiotico'
                # [2]: nutrientes críticos si aplica, sino info de invasión
                nut_val = s.get('nut', 1.0)
                if nut_val < 0.15:
                    a2_msg = '+ NUTRIENTES CRITICOS'
                    a2_col = RED
                    a2_key = 'F = +NUT'
                elif active:
                    a2_msg = active[0][0]
                    a2_col = active[0][1]
                    a2_key = active[0][2]
                else:
                    a2_msg = f'Invasion: {invasion_pct*100:.0f}% — mantén antibiotico activo'
                    a2_col = ORANGE
                    a2_key = ''

            elif s.get('nut', 1.0) < 0.15:
                # PRIORIDAD 2: nutrientes críticos — igual de urgente que invasión
                blink      = RED if self.frame_count % 2 == 0 else '#8b0000'
                border_col = blink
                a1_msg = '+ NUTRIENTES CRITICOS — aplica nutrientes YA'
                a1_col = RED
                a1_key = 'F = +NUT'
                # [2]: siguiente alerta activa
                rest = [a for a in active if 'NUT' not in a[0]]
                if rest:
                    a2_msg = rest[0][0]
                    a2_col = rest[0][1]
                    a2_key = rest[0][2]

            elif status_str == 'CRITICO':
                border_col = ORANGE
                a1_msg = 'POBLACION ALTA — revisa factores'
                a1_col = ORANGE
                a1_key = ''
                if active:
                    a2_msg = active[0][0]
                    a2_col = active[0][1]
                    a2_key = active[0][2]

            elif active:
                border_col = active[0][1]
                a1_msg, a1_col, a1_key = active[0]
                if len(active) > 1:
                    a2_msg = active[1][0]
                    a2_col = active[1][1]
                    a2_key = active[1][2]

            # sin alertas → panel vacío, borde discreto
            for sp in ax_alert.spines.values():
                sp.set_edgecolor(border_col)

            alert1_main.set_text(a1_msg)
            alert1_main.set_color(a1_col)
            alert1_key.set_text(a1_key)
            alert1_key.set_color(a1_col)
            alert1_tag.set_color(a1_col if a1_msg else DARK_BG)

            alert2_main.set_text(a2_msg)
            alert2_main.set_color(a2_col)
            alert2_key.set_text(a2_key)
            alert2_key.set_color(a2_col)
            alert2_tag.set_color(a2_col if a2_msg else DARK_BG)

            fig.canvas.draw_idle()
            return (line_h, line_p, clock_txt, pop_val, proj_val,
                    rate_val, status_val, microbe_txt,
                    alert1_main, alert1_key, alert1_tag,
                    alert2_main, alert2_key, alert2_tag,
                    *[b[0] for b in fact_bars], *fact_txts, *log_texts)

        ani = animation.FuncAnimation(fig, _update, interval=500, blit=False)
        plt.show()