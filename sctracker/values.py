"""Item data and prices from api.star-citizen.wiki (public, no account).

This is the tracker's only network use, and it only sends item ids (never
anything about you). Turn it off with "fetch_item_data": false in config.json.
Prices there come from UEX (crowd-sourced) and carry the date they were
reported, so treat old ones with care.
"""

import json
import queue
import threading
import time
import urllib.parse
import urllib.request

from .config import VERSION, say

API = "https://api.star-citizen.wiki/api/items"
UA = f"SC-Inventory-Tracker/{VERSION} (local inventory tool)"

# Component types worth comparing, and the stat that matters most for each
COMPARE = {
    "Cooler": ("coolant", "Coolant output"),
    "PowerPlant": ("power", "Power output"),
    "Shield": ("shield_hp", "Shield health"),
    "QuantumDrive": ("qt_speed", "Quantum speed"),
}


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def key_stats(d):
    """The few numbers worth showing for an item."""
    rn = d.get("resource_network") or {}
    gen = rn.get("generation") or {}
    use = (rn.get("usage") or {})
    em = d.get("emission") or {}
    shield = d.get("shield") or {}
    qd = d.get("quantum_drive") or d.get("quantumdrive") or {}
    out = {
        "coolant": gen.get("coolant"),
        "power": gen.get("power"),
        "power_use": ((use.get("power") or {}).get("max")),
        "ir": em.get("ir"),
        "em": em.get("em_max"),
        "health": (d.get("durability") or {}).get("health"),
        "shield_hp": shield.get("max_health") or shield.get("health"),
        "qt_speed": (qd.get("standard_jump") or {}).get("speed") if isinstance(qd, dict) else None,
        "mass": d.get("mass"),
    }
    return {k: v for k, v in out.items() if v not in (None, 0)}


def slim(d):
    """Keep what the tracker uses from an API item."""
    prices = (d.get("uex_prices") or {}).get("purchase") or []
    spots = []
    for p in prices:
        loc = p.get("starmap_location") or {}
        spots.append(dict(buy=p.get("price_buy") or 0, sell=p.get("price_sell") or 0,
                          terminal=p.get("terminal_name"), place=loc.get("name"),
                          system=loc.get("star_system_name"), date=(p.get("date_updated") or "")[:10]))
    bp = d.get("blueprint") or []
    return dict(name=d.get("name"), type=d.get("type"), sub_type=d.get("sub_type"), size=d.get("size"),
                lootable=bool(d.get("is_lootable")), events=d.get("event_source") or [],
                bp_link=(bp[0].get("link") if bp and isinstance(bp[0], dict) else None),
                grade=d.get("grade"), item_class=d.get("class"), craftable=bool(d.get("is_craftable")),
                blueprint=bool(d.get("blueprint")), manufacturer=(d.get("manufacturer") or {}).get("name"),
                class_name=d.get("class_name"), stats=key_stats(d), spots=spots,
                game_version=d.get("version"), web_url=d.get("web_url"))


class Values:
    def __init__(self, store, cfg):
        self.store, self.cfg = store, cfg
        self.max_age = cfg.get("item_data_max_age_days", 7) * 86400
        self.cache = {}
        for item_id, data, fetched in store.q("SELECT item_id, data, fetched FROM item_data"):
            try:
                self.cache[item_id] = (json.loads(data), fetched)
            except Exception:
                pass
        self.todo = queue.Queue()
        self.queued = set()
        self.on_update = None
        self.failures = 0
        threading.Thread(target=self._worker, daemon=True).start()

    # --- fetching ------------------------------------------------------

    def want(self, item_id):
        if not item_id or item_id in self.queued:
            return
        hit = self.cache.get(item_id)
        if hit:
            age = time.time() - hit[1]
            if age < (2 * 86400 if hit[0].get("missing") else self.max_age):
                return
        self.queued.add(item_id)
        self.todo.put(item_id)

    def _worker(self):
        while True:
            item_id = self.todo.get()
            try:
                data = self._fetch(item_id)
                self.failures = 0
            except Exception as e:
                self.failures += 1
                if self.failures == 3:
                    say(f"Item data site not reachable ({e}). Prices will fill in later.")
                time.sleep(min(60, 5 * self.failures))
                self.queued.discard(item_id)
                continue
            now = time.time()
            self.cache[item_id] = (data, now)
            self.store.q("INSERT OR REPLACE INTO item_data VALUES (?,?,?)", (item_id, json.dumps(data), now))
            if self.on_update:
                self.on_update()
            time.sleep(0.4)                 # be polite to a community-run site

    def _fetch(self, item_id):
        if item_id.startswith("bp:"):
            d = _get(item_id[3:])
            d = d.get("data", d)
            return dict(missions=[dict(title=m.get("title"), chance=m.get("chance"), url=m.get("web_url"))
                                  for m in d.get("unlocking_missions") or []],
                        default=bool(d.get("is_available_by_default")), time=d.get("craft_time_label"),
                        ingredients=[dict(name=c.get("name"), scu=c.get("quantity_scu"), qty=c.get("quantity"))
                                     for g in d.get("requirement_groups") or [] for c in g.get("children") or []],
                        url=d.get("web_url"))
        if item_id.startswith("type:"):
            _, typ, size = item_id.split(":")
            url = f"{API}?" + urllib.parse.urlencode({"filter[type]": typ, "filter[size]": size, "page[size]": 100})
            rows = _get(url).get("data") or []
            return {"list": [slim(r) for r in rows]}
        url = f"{API}?" + urllib.parse.urlencode({"filter[class_name]": item_id, "page[size]": 25})
        rows = _get(url).get("data") or []
        # The filter matches parts of names too, so pick the exact one
        want = {item_id.lower(), item_id.lower() + "_scitem"}
        exact = [r for r in rows if (r.get("class_name") or "").lower() in want]
        return slim(exact[0]) if exact else {"missing": True}

    def fetch_now(self, item_id, timeout=8):
        """Fetch one entry straight away (for a page waiting on it)."""
        hit = self.cache.get(item_id)
        if hit and time.time() - hit[1] < self.max_age:
            return hit[0]
        try:
            data = self._fetch(item_id)
        except Exception:
            return hit[0] if hit else None
        now = time.time()
        self.cache[item_id] = (data, now)
        self.store.q("INSERT OR REPLACE INTO item_data VALUES (?,?,?)", (item_id, json.dumps(data), now))
        return data

    def options(self, typ, size):
        """Every item of a type and size (e.g. all size 2 coolers), with key stats and cheapest price."""
        lst = self.fetch_now(f"type:{typ}:{size}") or {}
        rows = []
        for r in lst.get("list", []):
            cheapest = min((s["buy"] for s in r["spots"] if s["buy"] > 0), default=None)
            rows.append(dict(name=r["name"], id=(r["class_name"] or "").lower(), grade=r["grade"],
                             item_class=r["item_class"], maker=r.get("manufacturer"), stats=r["stats"],
                             cheapest=cheapest, craftable=r.get("craftable")))
        return rows

    def howto(self, item_id, owned=None, fitted_on=None):
        """Ways to get an item, in plain words, from the item data."""
        d = self.fetch_now(item_id)
        out = {"buy": [], "craft": None, "loot": False, "ships": fitted_on or [], "events": [], "found": bool(d)}
        if not d or d.get("missing"):
            return out
        out["name"] = d.get("name")
        out["buy"] = sorted([s for s in d["spots"] if s["buy"] > 0], key=lambda s: s["buy"])[:5]
        out["sell"] = sorted([s for s in d["spots"] if s["sell"] > 0], key=lambda s: -s["sell"])[:3]
        out["loot"] = d.get("lootable")
        out["events"] = d.get("events") or []
        if d.get("craftable") and d.get("bp_link"):
            out["craft"] = self.fetch_now("bp:" + d["bp_link"]) or {"missions": [], "ingredients": []}
        out["stats"] = d.get("stats")
        out["grade"], out["item_class"], out["size"], out["type"] = (d.get("grade"), d.get("item_class"),
                                                                    d.get("size"), d.get("type"))
        out["url"] = d.get("web_url")
        return out

    # --- using it ------------------------------------------------------

    def get(self, item_id):
        hit = self.cache.get(item_id)
        if not hit or hit[0].get("missing"):
            return None
        return hit[0]

    def annotate(self, it):
        """Add price and stat info to an item in the inventory picture."""
        item_id = it.get("id")
        if not item_id:
            return
        self.want(item_id)
        d = self.get(item_id)
        if not d:
            return
        sells = sorted([s for s in d["spots"] if s["sell"] > 0], key=lambda s: -s["sell"])
        buys = sorted([s for s in d["spots"] if s["buy"] > 0], key=lambda s: s["buy"])
        it["sell_spots"] = sells[:5]
        it["buy_spots"] = buys[:5]
        it["unit_sell"] = sells[0]["sell"] if sells else None
        it["value"] = round(sells[0]["sell"] * (it["qty"] or 0)) if sells else None
        it["craftable"] = d.get("craftable")
        it["stats"] = d.get("stats")
        it["wiki_type"] = d.get("type")
        it["wiki_url"] = d.get("web_url")
        for f, g in (("size", "size"), ("grade", "grade"), ("item_class", "item_class"),
                     ("manufacturer", "manufacturer")):
            if not it.get(f) and d.get(g) is not None:
                it[f] = str(d[g])
        if d.get("type") in COMPARE and d.get("size") is not None:
            key = f"type:{d['type']}:{d['size']}"
            self.want(key)
            lst = self.cache.get(key)
            if lst:
                stat, label = COMPARE[d["type"]]
                rows = []
                for r in lst[0]["list"]:
                    cheapest = min((s["buy"] for s in r["spots"] if s["buy"] > 0), default=None)
                    rows.append(dict(name=r["name"], class_name=r["class_name"], grade=r["grade"],
                                     item_class=r["item_class"], main=r["stats"].get(stat),
                                     ir=r["stats"].get("ir"), em=r["stats"].get("em"),
                                     power_use=r["stats"].get("power_use"), health=r["stats"].get("health"),
                                     cheapest=cheapest,
                                     this=(r["class_name"] or "").lower() in (item_id.lower(), item_id.lower() + "_scitem")))
                rows.sort(key=lambda r: -(r["main"] or 0))
                it["compare"] = {"label": label, "rows": rows[:25]}
