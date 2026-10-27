"""The storage kiosk screen: grid geometry, scrollbar, tiles, tooltip reading."""

import re

import cv2
import numpy as np

from .config import crop_rel
from .ocr import parse_tooltip

# Kiosk grid geometry, measured on a 3840x2160 screen (scaled for others,
# and adjusted by calibrate.py for screens that aren't 16:9).
# Columns lean slightly (perspective), so each column has its own numbers.
GEOM_REF = dict(
    col_x=[2820, 3036, 3257, 3487], col_w=[206, 211, 219, 228],
    row0_y=[509, 500, 489, 475], pitch=[209.6, 212.8, 216.6, 221.4],
    track_top=470, view_rows=6.03, panel_top=455, panel_bottom=1815,
    wide_min_w=300,
    # Category filter buttons above the grid (centres), and half their size
    filter_x=[2845, 2912, 2978, 3043, 3111, 3178, 3246, 3314, 3383, 3453], filter_y=464, filter_h=22,
)
GEOM = dict(GEOM_REF)

# --------------------------------------------------------------------------
# Grid geometry, tiles, scrollbar
# --------------------------------------------------------------------------

def read_scroll(img, region):
    """Top and length of the green scrollbar thumb, in 2160p pixels."""
    H, W = img.shape[:2]
    y0 = int(region[1] * H)
    col = crop_rel(img, region).astype(np.int16)
    b, g, r = col[..., 0], col[..., 1], col[..., 2]
    green = ((g > 120) & (g > r + 40) & (g > b + 10)).sum(1) >= 2
    idx = np.where(green)[0]
    if len(idx) == 0:
        return None, None
    runs = np.split(idx, np.where(np.diff(idx) > 4)[0] + 1)
    best = max(runs, key=len)
    k = 2160 / H
    return round((best[0] + y0) * k), round((best[-1] - best[0]) * k)


def offset_rows(t, l):
    if not t or not l:
        return 0.0
    return (t - GEOM["track_top"]) / l * GEOM["view_rows"]


def cell_of_tile(box, H, W, t, l):
    """(row, col, wide) of a tile box in page content coordinates."""
    sx, sy = W / 3840, H / 2160
    x, y, w, _ = box[0] / sx, box[1] / sy, box[2] / sx, box[3] / sy
    c = min(range(4), key=lambda i: abs(GEOM["col_x"][i] - x))
    r = (y - GEOM["row0_y"][c]) / GEOM["pitch"][c] + offset_rows(t, l)
    return int(round(r)), c, w > GEOM["wide_min_w"]


def cells_in_view(H, W, t, l):
    """Fully visible grid cells: [(row, col, (x, y, w, h))] in screen pixels."""
    sx, sy = W / 3840, H / 2160
    off = offset_rows(t, l)
    out = []
    k0 = max(0, int(np.floor(off)) - 1)
    for k in range(k0, k0 + 9):
        for c in range(4):
            y = GEOM["row0_y"][c] + (k - off) * GEOM["pitch"][c]
            h = GEOM["pitch"][c] - 8
            if y >= GEOM["panel_top"] - 5 and y + h <= GEOM["panel_bottom"] + 5:
                out.append((k, c, (int(GEOM["col_x"][c] * sx), int(y * sy),
                                   int(GEOM["col_w"][c] * sx), int(h * sy))))
    return out


def inner(img, rect, m=0.18):
    x, y, w, h = rect
    return img[y + int(h * m):y + h - int(h * m), x + int(w * m):x + w - int(w * m)]


def icon_sig(crop):
    return cv2.resize(crop, (48, 48), interpolation=cv2.INTER_AREA)


def ncc(a, b):
    a = a.astype(np.float32)
    b = b.astype(np.float32)
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / d) if d > 0 else 0.0


WIDE_TYPES = re.compile(r"rifle|smg|sniper|lmg|shotgun|launcher|cannon|repeater|gatling|scattergun|tractor", re.I)


def cell_at_point(pt, H, W, t, l, item_type=None):
    """(row, col, wide) of the tile under a screen point, from geometry alone."""
    sx, sy = W / 3840, H / 2160
    x, y = pt[0] / sx, pt[1] / sy
    if not (GEOM["col_x"][0] - 20 <= x <= GEOM["col_x"][3] + GEOM["col_w"][3] + 20):
        return None
    # Nearest column (the mouse can sit in the thin gap between tiles)
    c = min(range(4), key=lambda i: abs(GEOM["col_x"][i] + GEOM["col_w"][i] / 2 - x))
    r = int(np.floor((y - GEOM["row0_y"][c]) / GEOM["pitch"][c] + offset_rows(t, l)))
    wide = bool(item_type and WIDE_TYPES.search(item_type) and "pistol" not in item_type.lower())
    if wide and c == 3:
        c = 2           # a wide tile can't start in the last column
    return r, c, wide


def find_tile(img, region, cursor=None, bright=200, loose=False):
    """Bounding box of the highlighted (hovered) tile in the right panel."""
    H, W = img.shape[:2]
    x0, y0 = int(region[0] * W), int(region[1] * H)
    g = cv2.cvtColor(crop_rel(img, region), cv2.COLOR_BGR2GRAY)
    cnts, _ = cv2.findContours((g > bright).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    # Expected tile height on this screen, from the (possibly calibrated) layout
    hp = GEOM["pitch"][0] * H / 2160
    hmin, hmax, wmin, wmax = (0.05 * H, 0.2 * H, 0.05 * H, 0.45 * H) if loose else \
        (0.88 * hp, 1.25 * hp, 0.88 * hp, 2.4 * hp)
    best = None
    for c in cnts:
        x, y, w, h = cv2.boundingRect(c)
        # Only tile-sized outlines: one slot or two slots wide
        if not (hmin <= h <= hmax and wmin <= w <= wmax):
            continue
        box = (x + x0, y + y0, w, h)
        if cursor and not (box[0] <= cursor[0] <= box[0] + w and box[1] <= cursor[1] <= box[1] + h):
            continue
        if best is None or w * h > best[2] * best[3]:
            best = box
    return best


def read_tile_numbers(reader, img, box):
    x, y, w, h = box
    tile = img[y:y + h, x:x + w]
    qty = ammo = quality = None
    for *_, t in reader.read_all(tile, 1.0, img.shape[0] / 2160):
        t2 = t.replace(" ", "")
        m = re.fullmatch(r"(\d+)[xX×]", t2)
        if m:
            qty = int(m.group(1))
        if re.fullmatch(r"\d+/\d+", t2):
            ammo = t2
        m = re.search(r"(\d+)Q", t2)
        if m:
            quality = int(m.group(1))
    return qty, ammo, quality, tile


# --------------------------------------------------------------------------
# Frame reading
# --------------------------------------------------------------------------

def read_filters(img):
    """Names of the kiosk category filters that are switched on (solid light buttons)."""
    from .categories import CATEGORIES
    H, W = img.shape[:2]
    sx, sy = W / 3840, H / 2160
    h = max(4, int(GEOM["filter_h"] * sy))
    y = int(GEOM["filter_y"] * sy)
    g = cv2.cvtColor(img[max(0, y - h):y + h, :], cv2.COLOR_BGR2GRAY)
    on = []
    for name, x in zip(CATEGORIES, GEOM["filter_x"]):
        x = int(x * sx)
        box = g[:, max(0, x - h):x + h]
        if box.size and (box > 170).mean() > 0.5:
            on.append(name)
    return tuple(on)


def read_frame_state(reader, cfg, img):
    """Is the inventory open, which page, where is the scrollbar."""
    R = cfg["regions"]
    if "INVENTORY" not in reader.line(crop_rel(img, R["footer"])).upper():
        return None
    m = re.search(r"(\d+)\s*/\s*(\d+)", reader.line(crop_rel(img, R["page"])))
    t, l = read_scroll(img, R["scrollbar"])
    container = reader.line(crop_rel(img, R["header"])).replace(" ", "")
    if "LOCAL" not in container.upper():
        # Right panel is showing a ship, backpack or other container
        return {"page": None, "pages": None, "scroll": (None, None), "container": container}
    if t is None:
        # No scrollbar: the page fits on screen, so it's at the top
        t, l = GEOM["track_top"], 0
    return {"page": int(m.group(1)) if m else None, "pages": int(m.group(2)) if m else None,
            "scroll": (t, l), "container": container, "filters": read_filters(img)}


def analyse(reader, cat, cfg, img, cursor=None, state=None):
    """Read the item tooltip in a frame. Returns a record dict, or None."""
    R = cfg["regions"]
    H, W = img.shape[:2]
    state = state or read_frame_state(reader, cfg, img)
    if not state or state["page"] is None:
        return None
    s = H / 2160
    lines = reader.read_all(crop_rel(img, R["tooltip_band"]), min(1.0, 0.5 / s), s)
    tip = parse_tooltip(lines, s)
    if not tip:
        return None
    name, key, score, verified = cat.match(tip["name_options"])
    ok = verified and score >= (cfg["min_match_score"] if key else 0)
    expired = any(re.search(r"\bExpired\b", l[4], re.I) for l in lines)
    registered = any(re.search(r"\bregistered\s+to\b", l[4], re.I) for l in lines)
    # Hovered tile: bright outline, or the dimmer one locked/expired items get
    box = find_tile(img, R["right_panel"], cursor)
    if not box and H < 1600:
        # Lower resolutions thin the outline out; look again with a softer threshold
        box = find_tile(img, R["right_panel"], cursor, bright=165)
    qty = ammo = quality = None
    tile_img = None
    cell = None
    if box:
        qty, ammo, quality, tile_img = read_tile_numbers(reader, img, box)
        cell = cell_of_tile(box, H, W, *state["scroll"])
    elif cursor:
        # Locked/expired tiles have a faint outline: place it by the mouse position
        cell = cell_at_point(cursor, H, W, *state["scroll"], tip.get("item_type"))
    return {
        "status": "expired" if expired else None,
        "registered": 1 if registered else 0,
        "ocr_name": tip["name_options"][0],
        "item_name": name if ok else tip["name_options"][0],
        "item_key": key if ok else None,
        "verified": bool(ok),
        "match_score": round(score, 1),
        "item_type": tip.get("item_type"),
        "manufacturer": tip.get("manufacturer"),
        "size": tip.get("size"),
        "grade": tip.get("grade"),
        "class": tip.get("class"),
        "qty": qty or 1,
        "ammo": ammo,
        "quality": quality,
        "page": state["page"],
        "pages": state["pages"],
        "container": state["container"],
        "scroll": state["scroll"],
        "tile": box,
        "cell": cell,
        "_tile_img": tile_img,
    }


def read_qr_time(img):
    H, W = img.shape[:2]
    crop = cv2.resize(img[0:int(0.16 * H), int(0.90 * W):W], None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
    txt, _, _ = cv2.QRCodeDetector().detectAndDecode(crop)
    m = re.search(r"\s(\d{10})\s", txt or "")
    return float(m.group(1)) if m else None



def save_tile(cfg, rec):
    """Keep one icon picture per item (data\\tiles), for later icon work."""
    from .config import DATA
    if not cfg.get("save_tile_images") or rec.get("_tile_img") is None or not rec.get("item_key"):
        return
    folder = DATA / "tiles"
    folder.mkdir(parents=True, exist_ok=True)
    p = folder / f"{rec['item_key']}.png"
    if not p.exists():
        cv2.imwrite(str(p), rec["_tile_img"])


def describe(rec):
    bits = [rec["item_name"]]
    if rec["qty"] and rec["qty"] > 1:
        bits.append(f"x{rec['qty']}")
    extra = "/".join(x for x in (rec["item_type"], rec["grade"] and f"Grade {rec['grade']}") if x)
    where = f"p{rec['page']}" + (f" r{rec['cell'][0] + 1}c{rec['cell'][1] + 1}" if rec.get("cell") else "")
    flag = "" if rec["verified"] else f"  [CHECK: matched {rec['match_score']}%]"
    if rec.get("registered"):
        flag = "  [registered]" + flag
    if rec.get("status") == "expired":
        flag = "  [expired/locked]" + flag
    return f"{where}: {' '.join(bits)}" + (f" ({extra})" if extra else "") + flag
