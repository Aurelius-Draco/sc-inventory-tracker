"""What you have and where: each station's latest scan plus everything since.

A station's contents = its latest kiosk scan
                     + storage moves and purchases Game.log recorded after the scan
                     + changes you made by hand after the scan.
A new scan replaces all of that, because a scan is what's really there.
"""

import datetime as dt
import json
import re
import time
from collections import defaultdict

from .gamelog import log_files, read_log_file
from .locations import tidy_shop
from .categories import category_of
from .scan import detect_repeats

FORMAT = "sc-inventory-tracker/1"

GENERIC_SHOP_WORDS = {
    "scshop", "admin", "office", "adminoffice", "food", "store", "weapons", "armor", "weaponsarmor", "shop",
    "pharmacy", "cargo", "cargooffice", "commodities", "interior", "refinery", "refineryadmin", "item", "stall",
    "cart", "bar", "juice", "juicebar", "pizza", "pizzabar", "burrito", "burritobar", "coffee", "ellroys",
    "reststop", "truckstop", "livefire", "trdpst", "warehouse", "newdeal", "technotic", "platinumbay",
    "omegapro", "small", "large", "medium", "mrestall", "mrecart", "commex", "tdd", "casaba", "dumpers",
    "garrity", "conscientious", "cubby", "blast", "skutters", "centermass", "tammanyandsons", "cousincrows",
    "kel", "kelto", "aparelli", "ships", "vehicles",
}


def _norm(n):
    return re.sub(r"[^a-z0-9]", "", (n or "").lower())


def tidy_id(item_id):
    """Readable fallback for an item id the game text doesn't name."""
    s = re.sub(r"^(Harvestable_(Mineral_1H_)?|Carryable_1H_[A-Z]{2}_|Carryable_|Mining_Modules_\w+?_)", "", item_id or "")
    s = re.sub(r"_\d{2,}(_\d+)*$", "", s)
    words = []
    for seg in s.split("_"):
        words += re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", seg) or [seg]
    out = " ".join(w if w.isupper() and len(w) <= 4 else w.capitalize() for w in words if w)
    return out or item_id


def sync_logs(store, game_dir, max_age_days=60):
    """Read any log files not read yet. Returns the number of new events."""
    if not game_dir:
        return 0
    read = dict(store.q("SELECT name, size FROM log_files_read"))
    cutoff = time.time() - max_age_days * 86400
    before = store.q("SELECT COUNT(*) FROM log_events")[0][0]
    for p in log_files(game_dir):
        try:
            st = p.stat()
        except OSError:
            continue
        if st.st_mtime < cutoff:
            continue
        key = p.name if p.name != "Game.log" else f"Game.log@{int(st.st_ctime)}"
        if read.get(key) == st.st_size:
            continue
        store.add_events(read_log_file(p))
        store.q("INSERT OR REPLACE INTO log_files_read VALUES (?,?,?)", (key, st.st_size, time.time()))
    return store.q("SELECT COUNT(*) FROM log_events")[0][0] - before


# --------------------------------------------------------------------------
# Scans
# --------------------------------------------------------------------------

def scan_sessions(store, since=0):
    """Per station: the full scan to use, newer filtered scans on top of it, and any newer unfinished scan."""
    rows = store.q("SELECT s.id, s.location_key, s.started, s.last, s.freight_total, s.pages, s.build, s.filter,"
                   " s.total_est,"
                   " (SELECT COUNT(*) FROM cells c WHERE c.session_id=s.id AND c.source IN ('hover','inferred')),"
                   " (SELECT COUNT(*) FROM cells c WHERE c.session_id=s.id AND c.source='hover'),"
                   " (SELECT MAX(o.ts) FROM observations o WHERE o.session_id=s.id)"
                   " FROM sessions s WHERE s.last > ? ORDER BY s.last", (since,))
    by_loc = defaultdict(list)
    for sid, key, started, last, ft, pages, build, flt, est, known, hovered, read in rows:
        if not key or not hovered:
            continue
        # The scan's time is its last hover: just looking at the kiosk later doesn't re-read anything
        last = min(last, read) if read else last
        filters = tuple(f for f in (flt or "").split(",") if f)
        total = ft if (ft and not filters) else est
        if ft and not filters:
            complete = known >= ft
        elif est:
            complete = known >= est
        else:   # older scans from before the total was recorded
            complete = bool(pages and known >= 40 * (pages - 1))
        by_loc[key].append(dict(id=sid, started=started, last=last, freight_total=ft, pages=pages, known=known,
                                total=total, complete=complete, build=build, filters=filters))
    out = {}
    for key, ss in by_loc.items():
        full = [s for s in ss if not s["filters"]]
        done = [s for s in full if s["complete"]]
        base = done[-1] if done else (full[-1] if full else None)
        since_base = [s for s in ss if not base or s["last"] > base["last"]]
        filtered = [s for s in since_base if s["filters"] and s["complete"]]
        partial = [s for s in since_base if not s["complete"]]
        out[key] = dict(base=base, filtered=filtered, newer_partial=bool(partial))
    return out


def scan_tiles(store, sid):
    rows = store.q("SELECT page,row,col,item_name,qty,item_type,manufacturer,size,grade,class,ammo,quality,"
                   "source,ts,item_key,status,registered FROM cells WHERE session_id=? "
                   "AND source IN ('hover','inferred') ORDER BY page,row,col", (sid,))
    cols = ("page", "row", "col", "item_name", "qty", "item_type", "manufacturer", "size", "grade", "class",
            "ammo", "quality", "source", "ts", "item_key", "status", "registered")
    tiles = [dict(zip(cols, r)) for r in rows]
    repeated, chunks = detect_repeats([((t["page"], t["row"], t["col"]), t["item_name"]) for t in tiles])
    for t in tiles:
        first = repeated.get((t["page"], t["row"], t["col"]))
        t["repeat_of"] = f"p{first[0]} r{first[1] + 1}c{first[2] + 1}" if first else ""
    return tiles, chunks


# --------------------------------------------------------------------------
# Building the picture
# --------------------------------------------------------------------------

class Builder:
    def __init__(self, store, cfg, cat, locs, values=None):
        self.store, self.cfg, self.cat, self.locs = store, cfg, cat, locs
        self.values = values

    def item_key(self, item_id=None, name=None):
        return ("id:" + item_id.lower()) if item_id else ("n:" + _norm(name))

    def name_for(self, item_id):
        return self.cat.name_for_id(item_id) or tidy_id(item_id)

    def add_tiles(self, loc, tiles, item):
        for t in tiles:
            if t["repeat_of"]:
                continue
            key = self.item_key(t["item_key"], t["item_name"])
            # Use today's game text for the name, so renamed items follow the game
            now_name = self.cat.by_id.get(t["item_key"].lower()) if t["item_key"] else None
            it = item(loc, key, now_name or t["item_name"])
            it["id"] = it["id"] or (t["item_key"].lower() if t["item_key"] else None)
            n = t["qty"] or 1
            it["tiles"] += 1
            if t["status"] == "expired":
                it["expired"] += n
            else:
                it["scanned_qty"] = (it["scanned_qty"] or 0) + n
            if t["registered"]:
                it["registered"] += n
            for f, g in (("item_type", "item_type"), ("manufacturer", "manufacturer"), ("size", "size"),
                         ("grade", "grade"), ("item_class", "class")):
                it[f] = it[f] or t[g]

    def build(self):
        store, locs = self.store, self.locs
        now = time.time()
        notes = store.notes()
        choices = store.event_choices()
        inv_map = store.loc_ids()
        fresh = store.meta_get("fresh_start", 0) or 0
        sessions = scan_sessions(store, fresh)
        gv = store.meta_get("game_version")
        game_version = gv[0] if gv else None

        def major(v):
            return ".".join((v or "").split(".")[:2])
        stations = {}
        items = {}          # (loc, key) -> item dict
        changes = []
        needs = []

        def station(key):
            if key not in stations:
                info = locs.info(key)
                stations[key] = dict(key=key, name=info["name"], system=info["system"], name_source=info["source"],
                                     scan=None, changes=0, untracked=[], items=0, qty=0, expired=0)
            return stations[key]

        def item(loc, key, name, base=None):
            k = (loc, key)
            if k not in items:
                items[k] = dict(location_key=loc, name=name, id=None, qty=0, scanned_qty=None, log_change=0,
                                your_change=0, expired=0, registered=0, tiles=0, item_type=None,
                                manufacturer=None, size=None, grade=None, item_class=None,
                                last_change=None)
                if base:
                    items[k].update(base)
            return items[k]

        # 1. Scans: the full scan, then newer filtered scans replace their categories
        learned = store.meta_get("category_types", {}) or {}
        learned_before = dict(learned)
        cat_boundary = defaultdict(dict)      # loc -> category -> time of the scan that last covered it
        boundary = {}                          # loc -> time of the full scan
        for loc, grp in sessions.items():
            st = station(loc)
            base = grp["base"]
            summary = base or (grp["filtered"][-1] if grp["filtered"] else None)
            if not summary:
                continue
            warn = False
            st["scan"] = dict(session=summary["id"], started=summary["started"], last=summary["last"],
                              complete=summary["complete"], identified=summary["known"], total=summary["total"],
                              pages=summary["pages"], build=summary.get("build"),
                              newer_partial=grp["newer_partial"], repeat_warning=False,
                              full=bool(base), filtered=[],
                              before_patch=bool(summary.get("build") and game_version
                                                and major(summary["build"]) != major(game_version)))
            if base:
                boundary[loc] = base["last"]
            for sess in ([base] if base else []) + grp["filtered"]:
                tiles, chunks = scan_tiles(store, sess["id"])
                warn = warn or bool(chunks)
                if sess["filters"]:
                    cats = set(sess["filters"])
                    if len(cats) == 1:
                        for t in tiles:
                            if t["item_type"]:
                                learned[t["item_type"].lower()] = next(iter(cats))
                    for k in [k for k, it in items.items()
                              if k[0] == loc and category_of(it["item_type"], learned) in cats]:
                        del items[k]
                    for c in cats:
                        cat_boundary[loc][c] = sess["last"]
                    st["scan"]["filtered"].append(dict(categories=sorted(cats), last=sess["last"],
                                                       identified=sess["known"], total=sess["total"]))
                self.add_tiles(loc, tiles, item)
            st["scan"]["repeat_warning"] = warn
        if learned != learned_before:
            store.meta_set("category_types", learned)

        # Names already known at each station, to match log ids that have no game text
        by_name = defaultdict(dict)
        for (loc, key), it in items.items():
            by_name[loc][_norm(it["name"])] = key

        def log_key(loc, item_id):
            ik = self.item_key(item_id)
            if (loc, ik) in items:
                return ik, items[(loc, ik)]["name"]
            name = self.name_for(item_id)
            alt = by_name[loc].get(_norm(name))
            return (alt or ik), name

        # 2. Game.log since each station's scan
        starts = [g["base"]["started"] for g in sessions.values() if g["base"]] + \
                 [f["started"] for g in sessions.values() for f in g["filtered"]]
        log_since = max(fresh, min(starts, default=now - 14 * 86400))

        def since(loc, it=None):
            """Changes count from the scan that last covered this item's category."""
            b = boundary.get(loc, log_since)
            if it is not None and cat_boundary.get(loc):
                c = category_of(it.get("item_type"), learned)
                b = max(b, cat_boundary[loc].get(c, 0))
            return b
        events = store.q("SELECT id, ts, kind, loc_key, inv, item, qty, detail FROM log_events WHERE ts>=? "
                         "ORDER BY ts", (log_since,))
        evs = []
        for eid, ts, kind, loc, inv, it_id, qty, detail in events:
            d = json.loads(detail) if detail else {}
            loc = loc or inv_map.get(inv)
            evs.append(dict(id=eid, ts=ts, kind=kind, loc=loc, inv=inv, item=it_id, qty=qty, **d))
        opened = [(e["ts"], e["loc"]) for e in evs if e["kind"] == "location" and e["loc"]]

        moves_at = defaultdict(list)
        for e in evs:
            ch = choices.get(e["id"])
            if ch and ch[0] == "ignore":
                continue
            if e["kind"] == "move":
                loc = e["loc"]
                if not loc:
                    continue
                moves_at[loc].append(e["ts"])
                key, name = log_key(loc, e["item"])
                if e["ts"] <= since(loc, items.get((loc, key))):
                    continue
                it = item(loc, key, name)
                it["id"] = it["id"] or e["item"].lower()
                it["log_change"] += int(e["qty"])
                it["last_change"] = e["ts"]
                station(loc)["changes"] += 1
                changes.append(dict(ts=e["ts"], location_key=loc, item=name, delta=int(e["qty"]),
                                    source="log", what=e.get("how", "moved"), event_id=e["id"]))
            elif e["kind"] == "buy":
                loc = (ch[1] if ch and ch[0] == "location" else None) or self.buy_location(e, opened)
                name = self.name_for(e["item"])
                if not self.cat.name_for_id(e["item"]) and re.match(r"^[A-Z]{3,4}_[A-Z]", e["item"] or ""):
                    continue    # a ship or vehicle, not an item for storage
                if not loc:
                    if e["ts"] > log_since:
                        needs.append(dict(kind="buy", event_id=e["id"], ts=e["ts"], item=name, qty=int(e["qty"]),
                                          shop=tidy_shop(e.get("shop")),
                                          text=f"Bought {int(e['qty'])} x {name} at {tidy_shop(e.get('shop'))}. "
                                               f"Which station's storage did it go to?"))
                    continue
                moves_at[loc].append(e["ts"])
                key, name = log_key(loc, e["item"])
                if e["ts"] <= since(loc, items.get((loc, key))):
                    continue
                it = item(loc, key, name)
                it["id"] = it["id"] or e["item"].lower()
                it["log_change"] += int(e["qty"])
                it["last_change"] = e["ts"]
                station(loc)["changes"] += 1
                changes.append(dict(ts=e["ts"], location_key=loc, item=name, delta=int(e["qty"]), source="log",
                                    what=f"bought at {tidy_shop(e.get('shop'))}", event_id=e["id"]))
            elif e["kind"] == "sell":
                loc = e["loc"]
                if ch and ch[0] == "item":
                    continue        # handled as an adjustment when you chose the item
                if loc and e["ts"] <= since(loc):
                    continue
                needs.append(dict(kind="sell", event_id=e["id"], ts=e["ts"], location_key=loc, qty=int(e["qty"]),
                                  shop=tidy_shop(e.get("shop")),
                                  text=f"Sold {int(e['qty'])} units of a commodity at {tidy_shop(e.get('shop'))} "
                                       f"for {e.get('price', 0):,.0f} aUEC. The log doesn't say which. "
                                       f"Pick the item if it came out of station storage."))

        # Storage volume lines in the log aren't a reliable measure (the number changes with what the kiosk
        # is showing), so they're kept but not used to flag changes. See docs/ROADMAP.md.

        # 3. Your changes since each station's scan
        for aid, ts, loc, name, item_id, delta, note, source, event_id in store.q(
                "SELECT id, ts, loc_key, item_name, item_id, delta, note, source, event_id FROM adjustments "
                "WHERE undone=0 ORDER BY ts"):
            key = self.item_key(item_id, name) if item_id else (by_name[loc].get(_norm(name)) or self.item_key(None, name))
            if ts <= fresh or (loc in boundary and ts <= since(loc, items.get((loc, key)))):
                continue
            it = item(loc, key, name)
            it["your_change"] += int(delta)
            it["last_change"] = ts
            station(loc)["changes"] += 1
            changes.append(dict(ts=ts, location_key=loc, item=name, delta=int(delta), source=source or "you",
                                what=note or "changed by hand", adjustment_id=aid))

        # 4. Finish items and stations
        out_items = []
        for (loc, key), it in items.items():
            base = it["scanned_qty"] or 0
            it["qty"] = max(0, base + it["log_change"] + it["your_change"])
            it["changed"] = bool(it["log_change"] or it["your_change"])
            it["scanned"] = bool(stations.get(loc, {}).get("scan"))
            st = station(loc)
            it["location"] = st["name"]
            it["system"] = st["system"]
            n = notes.get(it["name"]) or {}
            it["note"] = n.get("note", "")
            it["tags"] = n.get("tags", [])
            if self.values:
                self.values.annotate(it)
            if it["qty"] == 0 and not it["expired"] and not it["changed"]:
                continue
            st["items"] += 1 if it["qty"] else 0
            st["qty"] += it["qty"]
            st["expired"] += it["expired"]
            out_items.append(it)
        for st in stations.values():
            sc = st["scan"]
            st["age_days"] = round((now - sc["last"]) / 86400, 1) if sc else None
            st["untracked_changes"] = len(st.pop("untracked"))
            if self.values:
                st["value"] = sum(i.get("value") or 0 for i in out_items if i["location_key"] == st["key"])
        changes.sort(key=lambda c: -c["ts"])
        for c in changes:
            c["location"] = stations[c["location_key"]]["name"] if c["location_key"] in stations else c["location_key"]
        for n in needs:
            if n.get("location_key"):
                n["location"] = locs.name(n["location_key"])
        out_items.sort(key=lambda i: (i["system"] or "", i["location"], i["name"].lower()))
        spread = defaultdict(set)
        for i in out_items:
            if i["qty"]:
                spread[i["name"]].add(i["location"])
        for i in out_items:
            others = sorted(spread[i["name"]] - {i["location"]})
            i["also_at"] = others
        # Wish list: how many of each you already own, and where
        wish = []
        for w in store.wishlist():
            key_id = (w["item_id"] or "").lower()
            have = [i for i in out_items if i["qty"] and ((key_id and (i.get("id") or "") == key_id)
                                                          or _norm(i["name"]) == _norm(w["name"]))]
            owned = sum(i["qty"] for i in have)
            row = dict(w, owned=owned, need=max(0, (w["qty"] or 1) - owned),
                       where=[{"location": i["location"], "qty": i["qty"]} for i in have])
            if self.values and key_id:
                self.values.want(key_id)
                d = self.values.get(key_id)
                if d:
                    buys = sorted([s for s in d["spots"] if s["buy"] > 0], key=lambda s: s["buy"])
                    row["buy_spots"] = buys[:3]
                    row["craftable"] = d.get("craftable")
            wish.append(row)
        return {
            "format": FORMAT,
            "wishlist": wish,
            "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "game_version": game_version,
            "stations": sorted(stations.values(), key=lambda s: (s["system"] or "", s["name"])),
            "items": out_items,
            "changes": changes[:500],
            "needs_you": sorted(needs, key=lambda n: -n["ts"]),
        }

    def buy_location(self, e, opened):
        """Which station a purchase went to: the shop's name, else storage opened nearby in time."""
        ts = e["ts"]
        near = [(abs(t - ts), t, loc) for t, loc in opened if abs(t - ts) < 6 * 3600]
        if not near:
            return None
        words = set()
        for seg in re.split(r"[_\-]", e.get("shop") or ""):
            low = seg.lower()
            if len(low) >= 5 and low not in GENERIC_SHOP_WORDS and not low.isdigit():
                words.add(low)
        cands = {loc for _, _, loc in near}
        if words:
            hit = {loc for loc in cands if any(w in _norm(loc) for w in words)}
            if len(hit) == 1:
                return hit.pop()
            if hit:
                return min((d, loc) for d, _, loc in near if loc in hit)[1]
            if any(w in {"levski", "orison", "lorville", "grimhex", "area18", "newbabbage"} for w in words):
                return None     # a city we haven't seen storage opened at
        before = [(ts - t, loc) for d, t, loc in near if t <= ts and ts - t < 2 * 3600]
        if before:
            return min(before)[1]
        after = [(t - ts, loc) for d, t, loc in near if t > ts and t - ts < 2 * 3600]
        return min(after)[1] if after else None


# --------------------------------------------------------------------------
# Files
# --------------------------------------------------------------------------

def write_outputs(model, store, cfg, folder):
    import csv
    folder.mkdir(parents=True, exist_ok=True)
    hide = {h.lower() for h in cfg.get("summary_hide_types", [])}

    def write_csv(name, cols, rows):
        try:
            with open(folder / name, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
                w.writeheader()
                w.writerows(rows)
        except PermissionError:
            from .config import say
            say(f"{name} is open in another program (Excel?). Close it and it'll update next time.")

    try:
        (folder / "inventory.json").write_text(json.dumps(model, indent=1, ensure_ascii=False, default=str),
                                               encoding="utf-8")
    except PermissionError:
        pass
    rows = []
    for i in model["items"]:
        if not i["qty"] or (i.get("item_type") or "").lower() in hide:
            continue
        r = dict(i)
        r["change"] = i["log_change"] + i["your_change"]
        r["tags"] = ", ".join(i["tags"])
        r["also_at"] = "; ".join(i["also_at"])
        rows.append(r)
    write_csv("summary.csv", ["location", "system", "name", "qty", "scanned_qty", "change", "registered",
                              "item_type", "manufacturer", "size", "grade", "item_class", "tiles", "value",
                              "also_at", "note", "tags", "id"], rows)
    write_csv("expired.csv", ["location", "system", "name", "expired", "item_type", "id"],
              [i for i in model["items"] if i["expired"]])
    write_csv("changes.csv", ["ts_local", "location", "item", "delta", "source", "what"],
              [dict(c, ts_local=dt.datetime.fromtimestamp(c["ts"]).strftime("%Y-%m-%d %H:%M")) for c in model["changes"]])
    # Every scanned tile, as before
    tiles = []
    names = {s["key"]: s["name"] for s in model["stations"]}
    for s in model["stations"]:
        if not s["scan"]:
            continue
        ts_rows, _ = scan_tiles(store, s["scan"]["session"])
        for t in ts_rows:
            t = dict(t)
            t["location"] = names[s["key"]]
            t["row"] += 1
            t["col"] += 1
            t["last_seen"] = dt.datetime.fromtimestamp(t.pop("ts") or s["scan"]["last"]).strftime("%Y-%m-%d %H:%M")
            tiles.append(t)
    write_csv("inventory.csv", ["location", "page", "row", "col", "item_name", "qty", "item_type", "manufacturer",
                                "size", "grade", "class", "ammo", "quality", "source", "last_seen", "item_key",
                                "status", "registered", "repeat_of"], tiles)
    return len(tiles), len(rows)


def share_file(model, label="", include_notes=False):
    """A cut-down copy to share with an org or friends: stations and items only.

    No log ids, no change history, no times beyond the scan date, and nothing
    about who you are unless you put it in the label yourself.
    """
    keep = ("name", "id", "qty", "item_type", "manufacturer", "size", "grade", "item_class", "registered")
    out = {
        "format": "sc-inventory-share/1",
        "label": label,
        "game_version": model.get("game_version"),
        "stations": [dict(name=s["name"], system=s["system"],
                          scanned=dt.date.fromtimestamp(s["scan"]["last"]).isoformat() if s["scan"] else None)
                     for s in model["stations"]],
        "items": [],
    }
    for i in model["items"]:
        if not i["qty"]:
            continue
        row = {k: i.get(k) for k in keep}
        row["station"] = i["location"]
        if include_notes:
            row["note"], row["tags"] = i.get("note", ""), i.get("tags", [])
        out["items"].append(row)
    return out
