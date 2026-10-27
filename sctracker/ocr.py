"""Reading text off the screen with RapidOCR, and parsing item tooltips."""

import re
import threading

import cv2

# --------------------------------------------------------------------------
# OCR
# --------------------------------------------------------------------------

class Reader:
    def __init__(self):
        import logging
        logging.disable(logging.WARNING)
        from rapidocr import RapidOCR
        self.eng = RapidOCR()
        self.lock = threading.Lock()

    def line(self, img):
        if img is None or img.size == 0:
            return ""
        with self.lock:
            r = self.eng(img, use_det=False, use_cls=False, use_rec=True)
        return (r.txts[0] if r.txts else "").strip()

    def boxes(self, img, scale):
        small = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        with self.lock:
            r = self.eng(small, use_det=True, use_cls=False, use_rec=False)
        out = []
        if r.boxes is None:
            return out
        for b in r.boxes:
            xs = [p[0] / scale for p in b]
            ys = [p[1] / scale for p in b]
            out.append((int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))))
        return out

    def read_all(self, img, scale, s=1.0):
        frags = []
        for x0, y0, x1, y1 in self.boxes(img, scale):
            if (x1 - x0) < 12 or (y1 - y0) < 8:
                continue
            crop = img[max(0, y0 - 4):y1 + 4, max(0, x0 - 4):x1 + 4]
            t = self.line(crop)
            if t:
                frags.append([x0, y0, x1, y1, t])
        return merge_rows(frags, s)


def merge_rows(frags, s=1.0):
    """Join text pieces that sit side by side on the same line."""
    frags = sorted(frags, key=lambda f: (f[1] + f[3]) / 2)
    rows = []
    for f in frags:
        cy = (f[1] + f[3]) / 2
        for r in rows:
            if abs(cy - (r[0][1] + r[0][3]) / 2) < 10 * s:
                r.append(f)
                break
        else:
            rows.append([f])
    out = []
    for r in rows:
        r.sort(key=lambda f: f[0])
        cur = list(r[0])
        for f in r[1:]:
            if f[0] - cur[2] < 45 * s:
                cur = [cur[0], min(cur[1], f[1]), f[2], max(cur[3], f[3]), cur[4] + " " + f[4]]
            else:
                out.append(tuple(cur))
                cur = list(f)
        out.append(tuple(cur))
    out.sort(key=lambda l: (l[1], l[0]))
    return out


# --------------------------------------------------------------------------
# Tooltip parsing
# --------------------------------------------------------------------------

FIELD_RE = {
    "item_type": re.compile(r"^Item\s*Type\W*\s*(.+)$", re.I),
    "manufacturer": re.compile(r"^Ma[nr]u?fact?urer\W*\s*(.+)$", re.I),
    "size": re.compile(r"^Size\W*\s*(.+)$", re.I),
    "grade": re.compile(r"^Grade\W*\s*(.+)$", re.I),
    "class": re.compile(r"^Class\W*\s*(.+)$", re.I),
}
ANCHOR_RE = re.compile(r"^(v[ao]l[uo]mer?|item\s*type|capac[il1]ty|ma[nr]u?fact?urer)(?=[\W\d])", re.I)
FIELDISH_RE = re.compile(
    r"^([A-Za-z][A-Za-z .()/&-]{1,24}:\s*\S"
    r"|(capac|v[ao]l[uo]m|item\s*type|ma[nr]u|size\W|grade\W|class\W|carrying|contents)"
    r"|\S*\d+\s*[μµp]s?CU)", re.I)


def parse_tooltip(lines, s=1.0):
    """Find the item tooltip among OCR lines. Returns dict or None."""
    anchor = None
    for i, l in enumerate(lines):
        if ANCHOR_RE.match(l[4]):
            anchor = i
            break
    if anchor is None:
        return None
    ax = lines[anchor][0]
    col = sorted([l for l in lines if abs(l[0] - ax) <= 40 * s], key=lambda l: l[1])
    a = col.index(lines[anchor])
    # Top of the tooltip: walk up while lines stay tightly packed
    top = a
    while top > 0 and col[top][1] - col[top - 1][3] < 45 * s:
        top -= 1
    block = col[top:a]
    plain = [l for l in block if not FIELDISH_RE.search(l[4])
             and not re.match(r"^\W*(expired\W*$|registered\s+to)", l[4], re.I)]
    if not plain:
        return None
    # Name candidates: topmost plain line first (fallback), then all others
    # and joined neighbours. The catalogue picks the best match among them.
    opts = [plain[0][4]]
    for i, l in enumerate(plain):
        if l[4] not in opts:
            opts.append(l[4])
        if i + 1 < len(plain) and plain[i + 1][1] - l[3] < 20 * s:
            opts.append(l[4] + " " + plain[i + 1][4])
    fields = {}
    prev = col[a]
    for l in col[a:]:
        t = l[4]
        if l is not col[a] and (l[1] - prev[3] > 45 * s or len(t) > 48 or t.endswith(".")):
            break
        for k, rx in FIELD_RE.items():
            m = rx.match(t)
            if m and k not in fields:
                fields[k] = m.group(1).strip(" :.")
        prev = l
    return {"name_options": opts, **fields}

