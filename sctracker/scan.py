"""A scan of one station's storage: the grid of tiles and what's known about each."""

import re
import time
from collections import defaultdict

import cv2
import numpy as np

from .kiosk import cells_in_view, icon_sig, inner, ncc
from .store import CELL_COLS, ITEM_FIELDS

# --------------------------------------------------------------------------
# A scan of one location: the grid of cells and what's known about each
# --------------------------------------------------------------------------

class Scan:
    def __init__(self, store, cfg, session_id, loc_key, loc_name):
        self.store, self.cfg = store, cfg
        self.sid, self.loc_key, self.loc_name = session_id, loc_key, loc_name
        self.cells = {}          # (page,row,col) -> dict(std, sigs, item..., source)
        self.pages = None
        self.freight_total = None
        self.filters = ()
        self.dirty = True
        self._load()

    def _load(self):
        rows = self.store.q(f"SELECT page,row,col,{','.join(CELL_COLS)} FROM cells WHERE session_id=?", (self.sid,))
        for r in rows:
            d = dict(zip(CELL_COLS, r[3:]))
            d["sigs"] = [np.frombuffer(d.pop("sig"), np.uint8).reshape(48, 48, 3)] if r[4] else []
            self.cells[(r[0], r[1], r[2])] = d
        s = self.store.q("SELECT pages, freight_total, filter FROM sessions WHERE id=?", (self.sid,))
        if s:
            self.pages, self.freight_total = s[0][0], s[0][1]
            self.filters = tuple(f for f in (s[0][2] or "").split(",") if f)

    def _save(self, key):
        d = self.cells[key]
        vals = {c: d.get(c) for c in CELL_COLS}
        vals["sig"] = d["sigs"][0].tobytes() if d.get("sigs") else None
        vals["wide"] = int(bool(d.get("wide")))
        self.store.q(f"INSERT OR REPLACE INTO cells (session_id,page,row,col,{','.join(CELL_COLS)}) "
                     f"VALUES ({','.join('?' * (4 + len(CELL_COLS)))})",
                     (self.sid, *key, *[vals[c] for c in CELL_COLS]))

    def touch(self, pages=None, freight_total=None):
        if pages:
            self.pages = pages
        if self.filters:
            freight_total = None         # the freight elevator count is for everything, not just the filter
        if freight_total:
            self.freight_total = freight_total
        est = self.overall()[1] if self.pages else None
        self.store.q("UPDATE sessions SET last=?, pages=COALESCE(?,pages), freight_total=COALESCE(?,freight_total),"
                     " total_est=COALESCE(?,total_est) WHERE id=?", (time.time(), pages, freight_total, est, self.sid))

    # --- inputs -----------------------------------------------------------

    def add_view(self, img, page, t, l):
        """Remember what every visible tile looks like.

        Returns "moved" if the tiles no longer look like what was recorded for
        this page earlier: items were added, removed or moved (freight
        elevator, dropping a backpack in, stacking), so the scan is stale.
        """
        H, W = img.shape[:2]
        seen = []
        compared = mismatched = 0
        for k, c, rect in cells_in_view(H, W, t, l):
            crop = inner(img, rect)
            if crop.size == 0:
                continue
            key = (page, k, c)
            std = float(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).std())
            sig = icon_sig(crop)
            seen.append((key, std, sig))
            d = self.cells.get(key)
            if d and d.get("sigs") and (std >= self.cfg["empty_std"] or (d.get("std") or 0) >= self.cfg["empty_std"]):
                compared += 1
                if max(ncc(sig, s) for s in d["sigs"]) < 0.6:
                    mismatched += 1
        if compared >= 8 and mismatched / compared > 0.4:
            return "moved"
        changed = False
        for key, std, sig in seen:
            d = self.cells.setdefault(key, {"sigs": []})
            if not d["sigs"]:
                d["sigs"] = [sig]
                d["std"] = std
                changed = True
                self._save(key)
            elif len(d["sigs"]) < 3:
                d["sigs"].append(sig)
                d["std"] = min(d.get("std") or std, std)
        if changed:
            self.dirty = True
        return changed

    def add_hover(self, rec, ts):
        page = rec["page"]
        if page is None or not rec.get("cell"):
            return None
        k, c, wide = rec["cell"]
        key = (page, k, c)
        d = self.cells.setdefault(key, {"sigs": []})
        d.update({f: rec.get(f) for f in ITEM_FIELDS})
        d.update(source="hover", wide=wide, ts=ts)
        self._save(key)
        if wide and c < 3:
            r = self.cells.setdefault((page, k, c + 1), {"sigs": []})
            r.update({f: None for f in ITEM_FIELDS})
            r.update(item_name=rec["item_name"], source="wide-right", wide=False, ts=ts)
            self._save((page, k, c + 1))
        self.store.q("INSERT INTO observations (session_id, ts, page, row, col, ocr_name, item_name, item_key,"
                     " verified, match_score, item_type, manufacturer, size, grade, class, qty, ammo, quality, source,"
                     " status, registered) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (self.sid, ts, page, k, c, rec["ocr_name"], rec["item_name"], rec["item_key"],
                      int(rec["verified"]), rec["match_score"], rec["item_type"], rec["manufacturer"],
                      rec["size"], rec["grade"], rec["class"], rec["qty"], rec["ammo"], rec["quality"], "hover",
                      rec.get("status"), rec.get("registered", 0)))
        self.dirty = True
        return key

    # --- run fill-in ------------------------------------------------------

    def is_empty(self, d, key=None):
        """A plain dark tile is an empty slot, unless something comes after it on the same page.

        Locked (expired) items are drawn almost black too, but empty slots only
        ever come at the end of the list, so a dark tile mid-page is an item.
        """
        if d.get("source") or d.get("std") is None or d["std"] >= self.cfg["empty_std"]:
            return False
        if key is None:
            return True
        last = self._last_filled().get(key[0])
        return last is None or key[1:] > last

    def _last_filled(self):
        """Page -> (row, col) of the last tile that clearly holds something."""
        last = {}
        for k, d in self.cells.items():
            if d.get("source") or (d.get("std") is not None and d["std"] >= self.cfg["empty_std"]):
                if k[1:] > last.get(k[0], (-1, -1)):
                    last[k[0]] = k[1:]
        return last

    def order(self):
        return [k for k in sorted(self.cells)
                if not self.is_empty(self.cells[k], k) and self.cells[k].get("source") != "wide-right"]

    def infer(self):
        """Fill tiles that sit between two hovered tiles of the same item."""
        if not self.dirty:
            return 0
        self.dirty = False
        thr = self.cfg["icon_match"]
        before = {k: (d.get("source"), d.get("item_name")) for k, d in self.cells.items()}
        for k, d in self.cells.items():          # recompute from scratch
            if d.get("source") in ("inferred", "inferred-right"):
                d.update({f: None for f in ITEM_FIELDS})
                d["source"] = None
                d["wide"] = False
        order = self.order()
        hovered = [i for i, k in enumerate(order) if self.cells[k].get("source") == "hover"
                   and self.cells[k].get("item_name")]
        by_name = defaultdict(list)
        for i in hovered:
            by_name[self.cells[order[i]]["item_name"]].append(order[i])
        added = 0
        for a, b in zip(hovered, hovered[1:]):
            da, db = self.cells[order[a]], self.cells[order[b]]
            if da["item_name"] != db["item_name"] or b - a < 2:
                continue
            refs = [s for kk in by_name[da["item_name"]] for s in self.cells[kk].get("sigs", [])]
            wide = bool(da.get("wide") and db.get("wide"))
            i = a + 1
            while i < b:
                key = order[i]
                d = self.cells[key]
                i += 1
                if d.get("source"):
                    continue
                score = max((ncc(s, r) for s in d.get("sigs", []) for r in refs), default=0.0)
                # No picture yet (cell only seen scrolling): trust the sort order
                if d.get("sigs") and refs and score < thr:
                    continue
                d.update({f: da.get(f) for f in ITEM_FIELDS})
                d.update(qty=1, ammo=None, quality=None, status=None, source="inferred", wide=wide, ts=time.time(),
                         registered=1 if (da.get("registered") and db.get("registered")) else 0)
                added += 1
                if wide:
                    # A two-slot item: its right half is part of the same item
                    rkey = (key[0], key[1], key[2] + 1)
                    if i < b and order[i] == rkey and not self.cells[rkey].get("source"):
                        self.cells[rkey].update({f: None for f in ITEM_FIELDS})
                        self.cells[rkey].update(item_name=da["item_name"], source="inferred-right", wide=False)
                        i += 1
        changed = 0
        for k, d in self.cells.items():
            if before.get(k) != (d.get("source"), d.get("item_name")):
                self._save(k)
                changed += 1
        return changed

    # --- reporting --------------------------------------------------------

    def expected(self, page):
        per = self.cfg["items_per_page"]
        if not self.pages:
            return None
        if page < self.pages:
            return per
        if self.freight_total:
            return max(0, self.freight_total - per * (self.pages - 1))
        return None

    def page_report(self, page):
        keys = [k for k in self.cells if k[0] == page]
        known = [k for k in keys if self.cells[k].get("source") in ("hover", "inferred")]
        unknown = sorted(k for k in keys if not self.cells[k].get("source") and not self.is_empty(self.cells[k], k)
                         and self.cells[k].get("sigs"))
        exp = self.expected(page)
        return {"page": page, "known": len(known), "unknown": unknown, "expected": exp,
                "hovered": sum(1 for k in known if self.cells[k]["source"] == "hover")}

    def status_line(self, page):
        r = self.page_report(page)
        exp = r["expected"]
        need = len(r["unknown"])
        tail = f"{r['known']}/{exp}" if exp else f"{r['known']}"
        if exp and r["known"] >= exp:
            return f"Page {page}: {tail} done"
        return f"Page {page}: {tail}" + (f", {need} to hover" if need else "")

    def overall(self):
        known = sum(1 for d in self.cells.values() if d.get("source") in ("hover", "inferred"))
        total = None
        if self.freight_total:
            total = self.freight_total
        elif self.pages:
            last = self.page_report(self.pages)
            seen = last["known"] + len(last["unknown"])
            # Until the last page has been looked at, the total isn't known
            total = self.cfg["items_per_page"] * (self.pages - 1) + seen if seen else None
        return known, total

    def kiosk_seq(self):
        return [(k, self.cells[k]["item_name"]) for k in sorted(self.cells)
                if self.cells[k].get("source") in ("hover", "inferred") and self.cells[k].get("item_name")]

    def completeness_text(self):
        known, total = self.overall()
        _, chunks = detect_repeats(self.kiosk_seq())
        lines = [f"{self.loc_name}: {known} of {total if total else '?'} items identified"
                 + (" (total from the freight elevator)" if self.freight_total else
                    " (total estimated from page count)" if total else "")]
        for p in range(1, (self.pages or max((k[0] for k in self.cells), default=0)) + 1):
            r = self.page_report(p)
            exp = r["expected"]
            if exp and r["known"] >= exp:
                continue
            cells = ", ".join(f"r{k[1] + 1}c{k[2] + 1}" for k in r["unknown"][:12])
            unseen = (exp - r["known"] - len(r["unknown"])) if exp else 0
            msg = f"  page {p}: {r['known']}/{exp or '?'}"
            if cells:
                msg += f"  hover: {cells}" + (" ..." if len(r["unknown"]) > 12 else "")
            if unseen > 0:
                msg += f"  ({unseen} not seen yet, scroll that page)"
            lines.append(msg)
        if chunks:
            lines.append(repeats_text(chunks))
        return "\n".join(lines)

    def overlay_markers(self, page, H, W, t, l):
        out = []
        for k, c, rect in cells_in_view(H, W, t, l):
            d = self.cells.get((page, k, c))
            if not d:
                continue
            src = d.get("source")
            if src == "hover":
                out.append(("hover", rect))
            elif src == "inferred":
                out.append(("inferred", rect))
            elif src is None and d.get("sigs") and not self.is_empty(d, (page, k, c)):
                out.append(("todo", rect))
        return out


def _norm(n):
    return re.sub(r"[^a-z0-9]", "", (n or "").lower())


def detect_repeats(seq, min_names=6):
    """Find a stretch of the kiosk list that repeats an earlier stretch.

    seq: [(key, item_name)] in kiosk order. A correctly sorted list can never
    show the same run of different items twice in the same order, so a repeat
    means the kiosk listed those items twice (a game display bug).
    Inside the repeated stretch, an item counts as a repeat only up to the
    number of tiles it had in the first listing; any extra tiles still count.
    Returns ({repeated key: first key}, [chunk dicts]).
    """
    comp = []                                  # runs of the same name
    for key, name in seq:
        if comp and comp[-1][0] == name:
            comp[-1][1].append(key)
        else:
            comp.append([name, [key]])
    names = [_norm(c[0]) for c in comp]
    chunks = []
    i = 0
    while i < len(names) - min_names:
        hit = None
        for j in range(0, i - min_names):
            if names[j:j + min_names] == names[i:i + min_names]:
                k = min_names
                while i + k < len(names) and j + k < i and names[j + k] == names[i + k]:
                    k += 1
                if not hit or k > hit[1]:
                    hit = (j, k)
        if not hit:
            i += 1
            continue
        chunks.append((hit[0], i, hit[1]))
        i += hit[1]
    if not chunks:
        return {}, []
    r1 = (min(c[0] for c in chunks), max(c[0] + c[2] for c in chunks))
    r2 = (min(c[1] for c in chunks), max(c[1] + c[2] for c in chunks))
    first = defaultdict(list)                  # name -> keys in the first listing
    for n in range(*r1):
        first[names[n]].extend(comp[n][1])
    used = defaultdict(int)
    repeated = {}
    for n in range(*r2):
        nm = names[n]
        for key in comp[n][1]:
            if used[nm] < len(first[nm]):
                repeated[key] = first[nm][used[nm]]
                used[nm] += 1
    out = [{"first": comp[r1[0]][1][0], "first_end": comp[r1[1] - 1][1][-1],
            "repeat": comp[r2[0]][1][0], "repeat_end": comp[r2[1] - 1][1][-1], "tiles": len(repeated)}]
    return repeated, out


def repeats_text(chunks):
    if not chunks:
        return ""
    c = chunks[0]
    return (f"WARNING: {c['tiles']} tiles on pages {c['repeat'][0]}-{c['repeat_end'][0]} repeat items already listed "
            f"on pages {c['first'][0]}-{c['first_end'][0]}, in the same order. The kiosk listed them twice "
            f"(a game display bug). "
            f"They're left out of summary.csv and flagged in inventory.csv. If items you know you have are "
            f"missing (crates last time), close and reopen the kiosk, or check the freight elevator terminal.")

