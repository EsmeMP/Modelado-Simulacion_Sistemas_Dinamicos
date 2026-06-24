import cv2
import numpy as np

def draw_graph_pro(data, width, height, line_color, label, unit=""):
    graph = np.full((height, width, 3), (12, 10, 20), dtype=np.uint8)
    cv2.line(graph, (0, 0), (width-1, 0), line_color, 2)
    cv2.line(graph, (0, 0), (0, height-1), tuple(ch//4 for ch in line_color), 1)
    cv2.putText(graph, label, (7, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, line_color, 1, cv2.LINE_AA)

    if len(data) < 2:
        return graph

    ML, MB, MT = 4, 18, 22
    plot_w = width  - ML - 2
    plot_h = height - MB - MT
    window = list(data[-plot_w:])
    n      = len(window)
    max_val = float(max(window)) if max(window) > 0 else 1.0

    def to_px(v, idx):
        px = ML + int(idx * plot_w / max(n-1, 1))
        py = MT + plot_h - int(np.clip(v / max_val, 0, 1) * plot_h)
        return px, int(np.clip(py, MT, MT + plot_h))

    for frac in [0.25, 0.5, 0.75]:
        gy = MT + int(plot_h * (1.0 - frac))
        cv2.line(graph, (ML, gy), (width-2, gy), tuple(ch//9 for ch in line_color), 1)

    pts = [to_px(window[i], i) for i in range(n)]
    for layer in range(5, 0, -1):
        alpha = layer / 5.0
        shift = int((5 - layer) * 2)
        poly  = [(p[0], p[1]+shift) for p in pts]
        poly += [(pts[-1][0], MT+plot_h+shift), (pts[0][0], MT+plot_h+shift)]
        cv2.fillPoly(graph, [np.array(poly, dtype=np.int32)],
                     tuple(int(ch * alpha * 0.3) for ch in line_color))

    for i in range(1, n):
        x1, y1 = pts[i-1]; x2, y2 = pts[i]
        cv2.line(graph, (x1, y1+1), (x2, y2+1), tuple(ch//3 for ch in line_color), 1, cv2.LINE_AA)
        cv2.line(graph, (x1, y1),   (x2, y2),   line_color, 2, cv2.LINE_AA)

    lx, ly = pts[-1]
    cv2.circle(graph, (lx, ly), 4, (255,255,255), -1, cv2.LINE_AA)
    cv2.circle(graph, (lx, ly), 4, line_color, 1, cv2.LINE_AA)
    cv2.circle(graph, (lx, ly), 7, tuple(ch//2 for ch in line_color), 1, cv2.LINE_AA)

    val_str = f"{window[-1]:.2f}{unit}"
    (tw, _), _ = cv2.getTextSize(val_str, cv2.FONT_HERSHEY_SIMPLEX, 0.38, 1)
    cv2.putText(graph, val_str, (width-tw-5, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (210,210,210), 1, cv2.LINE_AA)
    cv2.putText(graph, f"max {max_val:.1f}", (7, height-5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.32, tuple(ch//2 for ch in line_color), 1, cv2.LINE_AA)
    return graph