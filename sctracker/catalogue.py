"""Item and place names from the game's own text file (global.ini).

Works with the standard game text or a language pack such as StarStrings.
The tracker only reads the copy on your PC; it never ships CIG's files.
"""

import re
from pathlib import Path

from .config import say


class Catalogue:
    PREFIXES = ("item_name", "items_commodities_", "item_mining_consumable_")

    def __init__(self, game_dir, language="english"):
        self.names = {}       # display name -> item key (the game's id for the item)
        self.by_id = {}       # item id (lower case) -> display name
        self.extra = set()    # any other short display string (verification only)
        self.loc_names = {}   # other text keys -> text (place names live here)
        self.starstrings = False
        self._choices = []
        self._extra = []
        path = Path(game_dir or ".") / "Data" / "Localization" / language / "global.ini"
        self.path = path
        if not path.exists():
            say(f"No global.ini at {path}. Names will be recorded as read, unmatched.")
            return
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                if "=" not in line:
                    continue
                key, _, val = line.rstrip("\n").partition("=")
                key = key.split(",")[0]
                val = val.strip()
                low = key.lower()
                prefix = next((p for p in self.PREFIXES if low.startswith(p)), None)
                if prefix:
                    if low.endswith("_short") or "_desc" in low:
                        continue
                    item_id = key[len(prefix):].lstrip("_")
                    if val and len(val) < 80:
                        if val not in self.names:
                            self.names[val] = item_id
                        self.by_id.setdefault(item_id.lower(), val)
                elif 2 < len(val) <= 60 and "\\n" not in val and "<" not in val and "~" not in val:
                    self.extra.add(val)
                    if "_" in key:
                        self.loc_names[key] = val
                if key == "Frontend_PU_Version" and "MrKraken" in val:
                    self.starstrings = True
        self._choices = list(self.names.keys())
        self._extra = list(self.extra)
        self._loc_lower = {k.lower(): v for k, v in self.loc_names.items()}

    def match(self, options):
        """Best match for the OCR readings. Returns (name, key, score, verified)."""
        from rapidfuzz import fuzz, process
        best = (None, None, 0.0)
        for t in options:
            t = t.strip()
            if not t:
                continue
            if "PLACEHOLDER" in t.upper():
                return "Unnamed item (game placeholder)", None, 100.0, True
            if t in self.names:
                return t, self.names[t], 100.0, True
            if self._choices:
                hit = process.extractOne(t, self._choices, scorer=fuzz.ratio)
                if hit and hit[1] > best[2]:
                    best = (hit[0], self.names[hit[0]], float(hit[1]))
        if best[2] >= 90:
            return best[0], best[1], best[2], True
        # A near-exact match to other game text beats a loose item match
        # (e.g. "Aurora Mk II DM Module" is not an item key, but is game text)
        for t in options:
            if self._extra:
                hit = process.extractOne(t.strip(), self._extra, scorer=fuzz.ratio)
                if hit and hit[1] >= 95:
                    return hit[0], None, float(hit[1]), True
        if best[2] >= 80:
            return best[0], best[1], best[2], True
        return best[0], best[1], best[2], False

    def text(self, key):
        """Game text for a key, ignoring case. None if there isn't any."""
        return self.loc_names.get(key) or getattr(self, "_loc_lower", {}).get(key.lower())

    def name_for_id(self, item_id):
        """Display name for an item id from Game.log (e.g. behr_rifle_ballistic_03_mag)."""
        if not item_id:
            return None
        low = item_id.lower()
        if low in self.by_id:
            return self.by_id[low]
        # Commodities and mining items use slightly different ids in the log
        for pat in (r"^harvestable_(?:mineral_1h_)?", r"^mining_modules_(?:active|passive)_", r"^carryable_1h_\w\w_"):
            base = re.sub(pat, "", low)
            if base != low:
                for cand in (base, base + "pod", base + "_ore", base + "_raw"):
                    if cand in self.by_id:
                        return self.by_id[cand]
        return None

    def id_for_name(self, name):
        key = self.names.get(name)
        return key.lower() if key else None
