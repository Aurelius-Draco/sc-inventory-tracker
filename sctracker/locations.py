"""Turn Game.log storage location ids into the station names players know.

Game.log names a storage location by an internal id, e.g.
AsteroidClusterBase_Nyx_Social_Keeger_001. Many of these match a key in the
game's text file (global.ini) directly; others need a rule. Anything still
unknown is tidied up into something readable.

You can override any name in data\\locations.json:
  {"AsteroidClusterBase_Nyx_Social_Keeger_001": {"name": "PSS Alpha", "system": "Nyx"}}
Fixes for names the tracker gets wrong are welcome as GitHub issues.
"""

import json
import re

from .config import DATA

# Log id -> game text key, for ids that don't match a key directly
RULES = [
    (r"^AsteroidClusterBase_Nyx_Social_Keeger_(\d+)$", r"Nyx_SocialStation_\1"),
    (r"^RR_JP_([A-Z][a-z]+)([A-Z][a-z]+)$", r"\1_\2_JPStation"),
    (r"^RR_HUR_LEO$", "Stanton1_Transfer"),
    (r"^RR_CRU_LEO$", "Stanton2_Transfer_Seraphim"),
    (r"^RR_ARC_LEO$", "Stanton3_Transfer"),
    (r"^RR_MIC_LEO$", "Stanton4_Transfer"),
    (r"^RR_(P\d)_LEO$", r"RR_\1"),
    (r"^Nyx_Levski$", "Delamar_Levski"),
    (r"^PrisonMine_Stanton1b$", "Stanton1b_Aberdeen_Prison"),
    (r"^GrimHEX$", "shop_name_grimhex"),
]

# Ids with no game text at all
BUILTIN = {
    "Nyx_Kaboos": "Kaboos",
    "TheCollectorAsteroid_Stanton2": "Wikelo Emporium (Crusader)",
    "INVALID_LOCATION_ID": "Unknown location",
}

SYSTEMS = ("Stanton", "Pyro", "Nyx", "Castra", "Terra", "Magnus")
RR_SYSTEM = {"HUR": "Stanton", "CRU": "Stanton", "ARC": "Stanton", "MIC": "Stanton"}
PLACE_PREFIXES = ("stanton", "pyro", "nyx", "castra", "terra", "magnus", "delamar", "rr_")
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}
STOP = {"outpost", "station", "base", "col", "m", "s", "l", "the", "social", "asteroidclusterbase"}


def system_of(key):
    m = re.match(r"^RR_JP_([A-Z][a-z]+)", key)
    if m:
        return m.group(1)
    m = re.match(r"^RR_([A-Z]{3})_", key)
    if m and m.group(1) in RR_SYSTEM:
        return RR_SYSTEM[m.group(1)]
    if re.match(r"^RR_P\d", key):
        return "Pyro"
    if key in ("GrimHEX", "TheCollectorAsteroid_Stanton2", "PrisonMine_Stanton1b"):
        return "Stanton"
    for s in SYSTEMS:
        if s.lower() in key.lower():
            return s
    return ""


def _words(seg):
    return [w for w in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", seg)]


def _tidy(key):
    s = re.sub(r"^(AsteroidClusterBase|Outpost)_", "", key)
    s = re.sub(r"^RR_", "", s)
    parts = []
    for seg in s.split("_"):
        if seg in SYSTEMS or re.fullmatch(r"(Stanton|Pyro|Nyx|Castra)\d\w?", seg):
            continue
        parts.append(" ".join(_words(seg)) or seg)
    return " ".join(parts).strip() or key


class Locations:
    def __init__(self, cat):
        self.cat = cat
        self.path = DATA / "locations.json"
        self.overrides = {}
        self._cache = {}
        self.reload()

    def reload(self):
        self._cache = {}
        try:
            self.overrides = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self.overrides = {}

    def set_name(self, key, name, system=None):
        self.reload()
        entry = self.overrides.get(key, {})
        entry["name"] = name
        if system:
            entry["system"] = system
        self.overrides[key] = entry
        DATA.mkdir(exist_ok=True)
        self.path.write_text(json.dumps(self.overrides, indent=2, ensure_ascii=False), encoding="utf-8")
        self._cache.pop(key, None)

    def info(self, key):
        """{"key", "name", "system", "source"} where source is you/game/rule/guess."""
        if not key:
            return {"key": key, "name": "Unknown location", "system": "", "source": "guess"}
        if key in self._cache:
            return self._cache[key]
        r = self._resolve(key)
        r["key"] = key
        self._cache[key] = r
        return r

    def name(self, key):
        return self.info(key)["name"]

    def _resolve(self, key):
        system = system_of(key)
        o = self.overrides.get(key)
        if o and o.get("name"):
            return {"name": o["name"], "system": o.get("system", system), "source": "you"}
        cat = self.cat
        t = cat.text(key)
        if t:
            return {"name": t, "system": system, "source": "game"}
        for pat, rep in RULES:
            if re.match(pat, key):
                k2 = re.sub(pat, rep, key)
                t = cat.text(k2)
                if t:
                    if k2.endswith("_JPStation"):
                        t = f"{t} ({system})"      # e.g. Pyro Gateway exists in Stanton and Nyx
                    return {"name": t, "system": system, "source": "rule"}
                if k2.endswith("_JPStation"):
                    dest = re.match(r"^[A-Za-z]+_([A-Za-z]+)_JPStation", k2).group(1)
                    return {"name": f"{dest} Gateway ({system})", "system": system, "source": "guess"}
        if key in BUILTIN:
            return {"name": BUILTIN[key], "system": system, "source": "rule"}
        t = self._outpost(key) or self._search(key)
        if t:
            return {"name": t, "system": system, "source": "rule"}
        return {"name": _tidy(key), "system": system, "source": "guess"}

    def _places(self):
        if not hasattr(self, "_place_vals"):
            self._place_vals = [(k, v) for k, v in self.cat.loc_names.items()
                                if k.lower().startswith(PLACE_PREFIXES)
                                and not re.search(r"clinic|hospital|desc|_add$|mission|obj|marker", k, re.I)]
        return self._place_vals

    def _outpost(self, key):
        # Outpost_PAF_Stanton2b_Lamina_2 -> "Lamina PAF-II", Outpost_OLP_Stanton1b_Ruptura -> "Ruptura OLP"
        m = re.match(r"^Outpost_(PAF|OLP)_[A-Za-z0-9]+_([A-Za-z]+)(?:_(\d))?$", key)
        if not m:
            return None
        kind, place, n = m.groups()
        want = f"{place} {kind}" + (f"-{ROMAN.get(int(n), n)}" if n and kind == "PAF" else "")
        for _, v in self._places():
            if v.lower() == want.lower():
                return v
        return want

    def _search(self, key):
        # Use the most specific part of the id and look for a place name containing it
        segs = [s for s in key.split("_") if s and s.lower() not in STOP and s not in SYSTEMS
                and not re.fullmatch(r"(Stanton|Pyro|Nyx|Castra)\d\w?", s)]
        if not segs:
            return None
        last = segs[-1]
        if re.fullmatch(r"\d+", last) and len(segs) > 1:
            phrase = " ".join(_words(segs[-2]))
            num = last
        else:
            phrase, num = " ".join(_words(last)), None
        if len(phrase) < 4:
            return None
        if re.fullmatch(r"[A-Z]+\d*", segs[-2] if num and len(segs) > 1 else "") and num:
            phrase = f"{segs[-2]}-{num}"           # SM0_18 -> SM0-18
            num = None
        hits = [v for _, v in self._places() if phrase.lower() in v.lower()]
        if num:
            hits = [v for v in hits if re.search(rf"\b0*{int(num)}\b", v)]
        if not hits:
            return None
        return min(hits, key=len)


def tidy_shop(shop):
    """SCShop_WeaponsArmor_NyxSocial -> Weapons Armor Nyx Social"""
    s = re.sub(r"^SCShop_", "", shop or "")
    return " ".join(w for seg in s.split("_") for w in _words(seg)) or shop
