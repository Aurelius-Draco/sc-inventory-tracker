"""Shop helper: while you're at a shop terminal, show what you already own.

Shop terminals are screens in the game world, so they sit anywhere on your
screen. The tracker reads the text on screen, finds item names (each tile's
name sits above its "Volume:" line, and the selected item's name sits above
"Item Type:" in the details panel), and looks them up in your inventory.
Game.log says when you step up to a shop terminal and when you leave, so this
only runs while you're at one.
"""

import re

from rapidfuzz import fuzz, process
from rapidfuzz.utils import default_process

NOISE = re.compile(r"^(volume|item type|capacity|quick (buy|sell)|buy|sell|wallet|search|item name|choose|all "
                   r"(options|categories)|shop terminal|pharmacy|\W*\d[\d,.]*\W*$)", re.I)


def _clean(t):
    t = t.replace("[", "(").replace("]", ")").replace("CAPI", "CAP)").replace("(CAP", "CAP")
    return re.sub(r"\s+", " ", t).strip(" .")


def name_candidates(lines, s=1.0):
    """Item names on a shop screen: [(text, box, selected)] from OCR lines (x0, y0, x1, y1, text).

    s is the screen height / 2160, for scaling the pixel distances."""
    out = []
    lines = sorted(lines, key=lambda l: (l[1], l[0]))
    for i, l in enumerate(lines):
        t = l[4]
        if not re.match(r"^(volume|item type)\b", t, re.I):
            continue
        # Lines just above, in the same column: the item's name (one or two lines)
        above = [m for m in lines if abs(m[0] - l[0]) < 40 * s and 0 < l[1] - m[1] < 130 * s and not NOISE.match(m[4])]
        above.sort(key=lambda m: m[1])
        if not above:
            continue
        text = _clean(" ".join(m[4] for m in above[-2:]))
        x0 = min(m[0] for m in above[-2:])
        y0 = min(m[1] for m in above[-2:])
        x1 = max(m[2] for m in above[-2:])
        y1 = max(m[3] for m in above[-2:])
        out.append((text, (x0, y0, x1, y1), t.lower().startswith("item type")))
    return out


class ShopReader:
    def __init__(self, cat):
        self.cat = cat
        self.choices = list(cat.names)
        self.low = [default_process(c) for c in self.choices]

    def match(self, text):
        q = default_process(text)
        if len(q) < 4:
            return None
        hit = process.extractOne(q, self.low, scorer=fuzz.ratio, processor=None)
        if hit and hit[1] >= 86:
            return self.choices[hit[2]]
        # a name cut short by the tile: accept when it's the start of exactly one name
        starts = [i for i, c in enumerate(self.low) if c.startswith(q)] if len(q) >= 12 else []
        if len(starts) == 1:
            return self.choices[starts[0]]
        return None

    def read(self, lines, s=1.0):
        """[(item name, box, is_selected)] for the items readable on screen."""
        seen, out = set(), []
        for text, box, selected in name_candidates(lines, s):
            name = self.match(text)
            if name and (name, selected) not in seen:
                seen.add((name, selected))
                out.append((name, box, selected))
        return out


def owned_text(model, name):
    """'You have 3: People's Service Station Alpha 2, Levski 1' or None."""
    if not model:
        return None
    rows = [i for i in model["items"] if i["qty"] and i["name"].lower() == name.lower()]
    if not rows:
        return None
    total = sum(i["qty"] for i in rows)
    where = ", ".join(f"{i['location'].replace(chr(39).join(['People', 's Service Station']), 'PSS')} {i['qty']}"
                      for i in sorted(rows, key=lambda i: -i["qty"])[:3])
    return f"You have {total}: {where}"
