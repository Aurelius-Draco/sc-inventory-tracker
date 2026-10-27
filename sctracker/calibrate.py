"""Fitting the kiosk layout to your screen.

The layout was measured on a 3840x2160 (16:9) screen. Any other 16:9 screen
just scales, so most people never need this. On other shapes (ultrawide,
16:10) the kiosk may sit somewhere else, so you hover two tiles and the
tracker works out the scale and shift from them:

  1. Open a storage kiosk, page 1, scrolled to the top.
  2. Rest the mouse on the top-left item and press Insert.
  3. Rest it on the item in row 2, column 2 and press Insert.

Both must be one-slot items (not rifles or other two-slot ones).
Run with: tracker.py --calibrate   (or from two screenshots: --calibrate A.jpg B.jpg)
"""

import json

from .config import DATA, DEFAULT_CONFIG, say
from .kiosk import GEOM, GEOM_REF, find_tile

# Reference top-left corners (4K pixels) of the tiles at row 1 col 1 and row 2 col 2
REF_A = (GEOM_REF["col_x"][0], GEOM_REF["row0_y"][0])
REF_B = (GEOM_REF["col_x"][1], GEOM_REF["row0_y"][1] + GEOM_REF["pitch"][1])


def solve(box_a, box_b, W, H):
    """Scale and shift that map the 4K reference onto this screen."""
    dx_ref, dy_ref = REF_B[0] - REF_A[0], REF_B[1] - REF_A[1]
    sx = (box_b[0] - box_a[0]) / dx_ref
    sy = (box_b[1] - box_a[1]) / dy_ref
    if sx <= 0 or sy <= 0:
        raise ValueError("The second tile must be below and to the right of the first.")
    if abs(sx - sy) / max(sx, sy) > 0.08:
        raise ValueError(f"The two hovers don't line up (scale {sx:.3f} across vs {sy:.3f} down). "
                         "Check you used the top-left item and the one at row 2, column 2.")
    s = (sx + sy) / 2
    ox = box_a[0] - s * REF_A[0]
    oy = box_a[1] - s * REF_A[1]
    return {"s": round(s, 5), "ox": round(ox, 1), "oy": round(oy, 1), "W": W, "H": H}


def from_frames(frame_a, frame_b, cursor_a=None, cursor_b=None):
    H, W = frame_a.shape[:2]
    region = [0.40, 0.10, 1.0, 0.95]       # wide search area: the kiosk may sit anywhere on the right
    a = find_tile(frame_a, region, cursor_a, loose=True)
    b = find_tile(frame_b, region, cursor_b, loose=True)
    if not a or not b:
        raise ValueError("Couldn't see the highlighted tile in " + ("the first" if not a else "the second") +
                         " capture. Rest the mouse on the item until it lights up, then press Insert.")
    return solve(a, b, W, H)


def save(cal):
    path = DATA / "config.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    saved["calibration"] = cal
    path.write_text(json.dumps(saved, indent=2), encoding="utf-8")
    say(f"Calibrated for {cal['W']}x{cal['H']}: scale {cal['s']}, shift {cal['ox']:.0f},{cal['oy']:.0f} px.")


def apply(cfg, W, H):
    """Adjust the layout and screen regions for this screen. Call once the screen size is known."""
    cal = cfg.get("calibration")
    GEOM.clear()
    GEOM.update(json.loads(json.dumps(GEOM_REF)))
    if not cal:
        return False
    if (cal.get("W"), cal.get("H")) != (W, H):
        say(f"Calibration was for {cal.get('W')}x{cal.get('H')}, this screen is {W}x{H}. "
            "Using the standard layout; run --calibrate again if scans don't line up.")
        return False
    s, ox, oy = cal["s"], cal["ox"], cal["oy"]
    kx, ky = 3840 / W, 2160 / H          # screen pixels -> the 4K units the rest of the code uses

    def X(v):
        return (s * v + ox) * kx

    def Y(v):
        return (s * v + oy) * ky

    GEOM["col_x"] = [X(v) for v in GEOM_REF["col_x"]]
    GEOM["col_w"] = [s * v * kx for v in GEOM_REF["col_w"]]
    GEOM["row0_y"] = [Y(v) for v in GEOM_REF["row0_y"]]
    GEOM["pitch"] = [s * v * ky for v in GEOM_REF["pitch"]]
    for k in ("track_top", "panel_top", "panel_bottom"):
        GEOM[k] = Y(GEOM_REF[k])
    GEOM["wide_min_w"] = s * GEOM_REF["wide_min_w"] * kx
    GEOM["filter_x"] = [X(v) for v in GEOM_REF["filter_x"]]
    GEOM["filter_y"] = Y(GEOM_REF["filter_y"])
    GEOM["filter_h"] = s * GEOM_REF["filter_h"] * ky
    regions = {}
    for name, (x0, y0, x1, y1) in DEFAULT_CONFIG["regions"].items():
        regions[name] = [(s * x0 * 3840 + ox) / W, (s * y0 * 2160 + oy) / H,
                         (s * x1 * 3840 + ox) / W, (s * y1 * 2160 + oy) / H]
    cfg["regions"].update(regions)
    return True
