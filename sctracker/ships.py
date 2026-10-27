"""Ships: the list to pick from, their component slots, and what comes fitted where.

Data from api.star-citizen.wiki (vehicles), downloaded once a week and kept
in the database in a slimmed-down form (about 250 ships).
"""

import json
import re
import threading
import time
import urllib.parse

from .config import say
from .values import API, _get

VEH_API = API.replace("/items", "/vehicles")
SKIP = re.compile(r"_(Display|AI|PU_AI|Template|NPC|Tutorial|Unmanned)(_|$)", re.I)
# Slot types worth showing and changing, in the order players think of them
SLOT_ORDER = ["PowerPlant", "Cooler", "Shield", "QuantumDrive", "JumpDrive", "Radar", "LifeSupportGenerator",
              "WeaponGun", "WeaponMining", "Turret", "TurretBase", "MissileLauncher", "Missile", "WeaponDefensive"]
SLOT_LABEL = {"PowerPlant": "Power plant", "Cooler": "Cooler", "Shield": "Shield generator",
              "QuantumDrive": "Quantum drive", "Radar": "Radar", "LifeSupportGenerator": "Life support",
              "WeaponGun": "Gun", "Turret": "Weapon mount", "TurretBase": "Turret", "MissileLauncher": "Missile rack",
              "WeaponDefensive": "Countermeasures", "WeaponMining": "Mining laser", "Missile": "Missile",
              "JumpDrive": "Jump drive"}
# Slots you'd normally change, and what kind of item goes in them (api.star-citizen.wiki item type)
ITEM_TYPE = {"PowerPlant": "PowerPlant", "Cooler": "Cooler", "Shield": "Shield", "QuantumDrive": "QuantumDrive",
             "JumpDrive": "JumpDrive", "Radar": "Radar", "LifeSupportGenerator": "LifeSupportGenerator",
             "WeaponGun": "WeaponGun", "WeaponMining": "WeaponMining", "Missile": "Missile"}


def slim_vehicle(v):
    slots = []

    def walk(ports, parent=""):
        for p in ports or []:
            it = p.get("equipped_item") or {}
            typ = p.get("type") or ""
            if typ in SLOT_ORDER:
                sizes = p.get("sizes") or {}
                slots.append(dict(port=(parent + "/" if parent else "") + p.get("name", ""), type=typ,
                                  label=SLOT_LABEL.get(typ, typ), min=sizes.get("min"), max=sizes.get("max"),
                                  editable=bool(p.get("editable")), stock_id=(it.get("class_name") or "").lower() or None,
                                  stock_name=it.get("name"), stock_grade=it.get("grade"), stock_size=it.get("size")))
            walk(p.get("ports"), p.get("name", ""))
    walk(v.get("ports"))
    slots.sort(key=lambda s: (SLOT_ORDER.index(s["type"]), s["port"]))
    return dict(cls=v.get("class_name"), uuid=v.get("uuid"), name=v.get("game_name") or v.get("name"),
                short=v.get("name"),
                maker=(v.get("manufacturer") or {}).get("name") if isinstance(v.get("manufacturer"), dict) else
                v.get("manufacturer"), role=v.get("role"), career=v.get("career"),
                size=v.get("size_class"), cargo=v.get("cargo_capacity"), slots=slots, url=v.get("web_url"))


class Ships:
    KEY = "vehicles:all"

    def __init__(self, store, cfg):
        self.store, self.cfg = store, cfg
        self.max_age = 7 * 86400
        self.list = []
        self.by_cls = {}
        self.fitted_on = {}
        self.loading = False
        r = store.q("SELECT data, fetched FROM item_data WHERE item_id=?", (self.KEY,))
        if r:
            try:
                self._use(json.loads(r[0][0]))
            except Exception:
                pass
        if cfg.get("fetch_item_data", True) and (not r or time.time() - r[0][1] > self.max_age):
            threading.Thread(target=self._fetch, daemon=True).start()

    def _use(self, data):
        self.list = data
        self.by_cls = {v["cls"].lower(): v for v in data}
        fitted = {}
        for v in data:
            for s in v["slots"]:
                if s["stock_id"]:
                    fitted.setdefault(s["stock_id"], set()).add(v["short"] or v["name"])
        self.fitted_on = {k: sorted(n) for k, n in fitted.items()}

    def _fetch(self):
        self.loading = True
        try:
            out, page = [], 1
            while page < 20:
                url = f"{VEH_API}?" + urllib.parse.urlencode({"page[size]": 50, "page[number]": page})
                d = _get(url, timeout=60)
                for v in d.get("data") or []:
                    if v.get("class_name") and not SKIP.search(v["class_name"]):
                        out.append(slim_vehicle(v))
                last = (d.get("meta") or {}).get("last_page") or page
                if page >= last:
                    break
                page += 1
                time.sleep(0.5)
            # One entry per ship name, preferring the plainest class name
            best = {}
            for v in sorted(out, key=lambda v: len(v["cls"])):
                best.setdefault(v["name"], v)
            data = sorted(best.values(), key=lambda v: v["name"])
            self.store.q("INSERT OR REPLACE INTO item_data VALUES (?,?,?)", (self.KEY, json.dumps(data), time.time()))
            self._use(data)
            say(f"Ship list updated: {len(data)} ships.")
        except Exception as e:
            say(f"Couldn't download the ship list ({e}). Ships will fill in later.")
        finally:
            self.loading = False

    def search(self, q, limit=15):
        """Ships matching what's typed. Every word typed must appear, in any order, for a top spot."""
        from rapidfuzz import fuzz
        q = (q or "").strip().lower()
        if not q:
            return []
        words = q.split()
        scored = []
        for v in self.list:
            n = v["name"].lower()
            toks = n.replace("-", " ").split()
            hits = sum(1 for w in words if any(t == w or t.startswith(w) for t in toks) or w in n)
            score = fuzz.WRatio(q, n) + 40 * (hits == len(words)) + 10 * hits - 0.2 * len(n)
            scored.append((score, v))
        scored.sort(key=lambda x: -x[0])
        return [dict(cls=v["cls"], name=v["name"], maker=v["maker"], role=v["role"])
                for score, v in scored[:limit] if score > 60]

    def get(self, cls):
        return self.by_cls.get((cls or "").lower())

    def detail(self, cls):
        """Full slot list for one ship (guns inside mounts, missiles), fetched once and kept."""
        key = f"vehicle:{(cls or '').lower()}"
        r = self.store.q("SELECT data, fetched FROM item_data WHERE item_id=?", (key,))
        if r and time.time() - r[0][1] < self.max_age:
            return json.loads(r[0][0])
        v = self.get(cls)
        if not v or not v.get("uuid"):
            return v
        try:
            d = _get(f"{VEH_API}/{v['uuid']}", timeout=60)
            full = slim_vehicle(d.get("data", d))
            self.store.q("INSERT OR REPLACE INTO item_data VALUES (?,?,?)", (key, json.dumps(full), time.time()))
            return full
        except Exception as e:
            say(f"Couldn't fetch details for {v['name']} ({e}).")
            return json.loads(r[0][0]) if r else v
