"""Reading Game.log.

The game writes a lot about inventory to Game.log, in plain text, every
session (older sessions are kept in the logbackups folder). The tracker reads
these files only. From them it gets:

- which station's storage you opened (and the inventory id the game uses for it)
- the freight elevator's exact item count
- presses of the kiosk's Stack button
- every item moved in or out of station storage: item id, quantity, success
- shop purchases (they go into the station's storage)
- commodity sales (quantity only, the log doesn't name the commodity)
- the storage's used volume, which shows when something changed that the
  log doesn't otherwise explain (the freight elevator, for example)

Your character name is in these lines too. The tracker never stores or
exports it.
"""

import base64
import datetime as dt
import hashlib
import re
import time
from pathlib import Path

LOG_TS = re.compile(r"^<(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?)Z>")
LOG_LOC = re.compile(r"<RequestLocationInventory> Player\[[^\]]*\] requested inventory for Location\[([^\]]+)\]")
LOG_FREIGHT = re.compile(r"Freight Inventory Grid InventoryDataRequest Successful Inventory\[[^\]]*\].*?"
                         r"HasNextPage\[(\d)\], StartCursor\[([^\]]*)\], EndCursor\[([^\]]*)\]")
LOG_QUERY_LOC = re.compile(r"<Query Inventory> Request\[\d+\] Inventory\[(\d+:Location:\d+)\]")
LOG_QUEUED = re.compile(r"<Inventory Mgmt Request Queued> Queued Request\[(\d+)\] Type\[(\w+)\] for .*?"
                        r"Source Inventory\[([^\]]*)\] Target Inventory\[([^\]]*)\]\. "
                        r"Source\[([^\]]*)\] amount\[(\d+)\].*?Target\[([^\]]*)\] amount\[(\d+)\].*?Item\[([^\]]*)\]")
LOG_DONE = re.compile(r"<Player Inventory Request Complete> Request\[(\d+)\] for .*?Type\[(\w+)\] Result\[(\w+)\]")
LOG_BUY = re.compile(r"Send(?:StandardItem|Shop)BuyRequest> Sending SShopBuyRequest - .*?shopName\[([^\]]*)\] "
                     r"kioskId\[(\d+)\] client_price\[([\d.]+)\] itemClassGUID\[[^\]]*\] itemName\[([^\]]*)\] "
                     r"quantity\[(\d+)\]")
LOG_SHOP_RESULT = re.compile(r"RmShopFlowResponse> Received ShopFlowResponse - .*?kioskId\[(\d+)\].*?"
                             r"result\[(\w+)\] type\[(\w+)\]")
LOG_SELL = re.compile(r"SendCommoditySellRequest> Sending SShopCommoditySellRequest - .*?shopName\[([^\]]*)\] "
                      r"kioskId\[(\d+)\] amount\[([\d.]+)\] resourceGUID\[([^\]]*)\].*?quantity\[(\d+)\]")
LOG_VERSION = re.compile(r"(?:FileVersion|ProductVersion): ([\d.]+)")
LOG_CAPACITY = re.compile(r"<OnDragInventoryItemModifyTarget> Source\[(\d+:Location:\d+)\] Capacity\[\d+\] "
                          r"UsedCapacity\[([\d.]+)\]")


def parse_ts(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=dt.timezone.utc).timestamp()


def cursor_value(c):
    try:
        v = base64.b64decode(c + "=" * (-len(c) % 4)).decode()
        return int(v) if v.isdigit() else None
    except Exception:
        return None


def is_loc(inv):
    return ":Location:" in (inv or "")


def strip_entity(item):
    """behr_smg_ballistic_01_776718675003 -> behr_smg_ballistic_01"""
    return re.sub(r"_\d{9,}$", "", item or "")


class LogParser:
    """Reads one log file's lines in order and turns them into events."""

    def __init__(self):
        self.location = None          # last storage location opened (log id)
        self.loc_ts = 0.0
        self.loc_ids = {}             # inventory id -> location log id
        self._map_next = None         # location opened, waiting for its inventory id
        self.queued = {}              # request number -> queued move
        self.buys = {}                # kiosk id -> [pending purchases]
        self.freight_total = {}       # location -> (count, unix time)
        self.freight_floor = {}       # location -> count known to be exceeded
        self.stack_presses = 0
        self.capacity = {}            # inventory id -> last used volume
        self.version = None           # game version, from the log's first lines

    def feed(self, line):
        """Process one line. Returns a list of event dicts (often empty)."""
        if "<" not in line:
            return []
        m = LOG_TS.match(line)
        ts = parse_ts(m.group(1)) if m else time.time()
        ev = []
        if self.version is None and "Version:" in line:
            m = LOG_VERSION.search(line)
            if m:
                self.version = m.group(1)
                ev.append(self._ev(line, ts, "version", item=m.group(1)))
            return ev

        if "Player Inventory Request Complete" in line:
            m = LOG_DONE.search(line)
            if m:
                req, kind, result = m.groups()
                if kind == "StackAll":
                    self.stack_presses += 1
                q = self.queued.pop(req, None)
                if q and result == "Succeed":
                    ev += self._move_events(q, ts, line)
            return ev

        m = LOG_LOC.search(line)
        if m:
            self.location, self.loc_ts = m.group(1), ts
            self._map_next = (m.group(1), ts)
            ev.append(self._ev(line, ts, "location", loc=m.group(1)))
            return ev

        m = LOG_QUERY_LOC.search(line)
        if m and self._map_next and ts - self._map_next[1] < 10:
            inv = m.group(1)
            if self.loc_ids.get(inv) != self._map_next[0]:
                self.loc_ids[inv] = self._map_next[0]
                ev.append(self._ev(line, ts, "loc_id", inv=inv, loc=self._map_next[0]))
            self._map_next = None
            return ev

        if "Inventory Mgmt Request Queued" in line:
            m = LOG_QUEUED.search(line)
            if m:
                req, kind, src, tgt, s_cls, s_amt, t_cls, t_amt, item = m.groups()
                if is_loc(src) or is_loc(tgt):
                    self.queued[req] = dict(kind=kind, src=src, tgt=tgt, cls=s_cls, amount=int(s_amt),
                                            item=strip_entity(item))
            return ev

        if "Freight Inventory Grid InventoryDataRequest Successful" in line:
            m = LOG_FREIGHT.search(line)
            if m and self.location:
                end = cursor_value(m.group(3))
                if end:
                    if m.group(1) == "1":
                        # More pages follow, so the real total is bigger than this
                        self.freight_floor[self.location] = max(end, self.freight_floor.get(self.location, 0))
                    else:
                        # Last page of a list. Filtered or searched lists give smaller
                        # counts, so only accept it if it beats everything seen so far.
                        prev = self.freight_total.get(self.location, (0, 0))
                        if end > self.freight_floor.get(self.location, 0) and end >= prev[0]:
                            self.freight_total[self.location] = (end, ts)
                            ev.append(self._ev(line, ts, "freight_total", loc=self.location, qty=end))
            return ev

        if "SShopBuyRequest" in line:
            m = LOG_BUY.search(line)
            if m:
                shop, kiosk, price, item, qty = m.groups()
                self.buys.setdefault(kiosk, []).append(dict(shop=shop, price=float(price), item=item,
                                                            qty=int(qty), line=line, ts=ts))
            return ev

        if "Received ShopFlowResponse" in line:
            m = LOG_SHOP_RESULT.search(line)
            if m and m.group(3) == "Buying":
                pend = self.buys.get(m.group(1))
                if pend:
                    b = pend.pop(0)
                    if m.group(2) == "Success":
                        loc = self.location if ts - self.loc_ts < 4 * 3600 else None
                        ev.append(self._ev(b["line"], b["ts"], "buy", loc=loc, item=b["item"], qty=b["qty"],
                                           shop=b["shop"], price=b["price"]))
            return ev

        if "SShopCommoditySellRequest" in line:
            m = LOG_SELL.search(line)
            if m:
                shop, kiosk, amount, guid, qty = m.groups()
                loc = self.location if ts - self.loc_ts < 4 * 3600 else None
                ev.append(self._ev(line, ts, "sell", loc=loc, item=guid, qty=int(qty), shop=shop,
                                   price=float(amount)))
            return ev

        if "OnDragInventoryItemModifyTarget" in line:
            m = LOG_CAPACITY.search(line)
            if m:
                inv, used = m.group(1), float(m.group(2))
                if self.capacity.get(inv) != used:
                    self.capacity[inv] = used
                    ev.append(self._ev(line, ts, "volume", inv=inv, loc=self.loc_ids.get(inv), qty=used))
            return ev
        return ev

    def _move_events(self, q, ts, line):
        """Station storage gained or lost items."""
        kind, src, tgt = q["kind"], q["src"], q["tgt"]
        if kind in ("QueryInventory", "StackAll", "Sort", "OpenNestedInventory", "Split", "AmmoRepool"):
            return []
        if is_loc(src) and is_loc(tgt) and src == tgt:
            return []                               # rearranging within the same storage
        item = q["cls"] if q["cls"] not in ("", "NULL", "null", "none") else q["item"]
        if not item or item == "NONE":
            return []
        n = max(1, q["amount"])
        how = {"Move": "moved", "Stack": "moved", "Store": "stored", "Interaction": "taken/equipped",
               "Drop": "dropped"}.get(kind, kind.lower())
        out = []
        if is_loc(src):
            out.append(self._ev(line, ts, "move", inv=src, loc=self.loc_ids.get(src), item=item, qty=-n,
                                how=how, sub="out"))
        if is_loc(tgt):
            out.append(self._ev(line, ts, "move", inv=tgt, loc=self.loc_ids.get(tgt), item=item, qty=n,
                                how=how, sub="in"))
        return out

    @staticmethod
    def _ev(line, ts, kind, sub="", **kw):
        # A stable id from the line itself, so the same line read again
        # (live, then later from logbackups) is only counted once
        eid = hashlib.sha1((line.strip() + sub).encode("utf-8", "replace")).hexdigest()[:20]
        return dict(id=eid, ts=ts, kind=kind, **kw)


class LogWatcher:
    """Follows the live Game.log while the game runs."""

    def __init__(self, game_dir):
        self.path = Path(game_dir) / "Game.log"
        self.pos = 0
        self.parser = LogParser()
        self.events = []

    # Shortcuts used by live mode
    @property
    def location(self):
        return self.parser.location

    @property
    def freight_total(self):
        return self.parser.freight_total

    @property
    def freight_floor(self):
        return self.parser.freight_floor

    @property
    def stack_presses(self):
        return self.parser.stack_presses

    def poll(self):
        """Read new lines. Returns the new events."""
        if not self.path.exists():
            return []
        size = self.path.stat().st_size
        if size < self.pos:   # game restarted, new log
            self.pos = 0
            self.parser = LogParser()
        if size == self.pos:
            return []
        with open(self.path, encoding="utf-8", errors="replace") as f:
            f.seek(self.pos)
            chunk = f.read()
            self.pos = f.tell()
        new = []
        for line in chunk.splitlines():
            new += self.parser.feed(line)
        return new


def log_files(game_dir):
    """All logs, oldest first: logbackups, then the current Game.log."""
    game_dir = Path(game_dir)
    files = sorted((game_dir / "logbackups").glob("*.log"), key=lambda p: p.stat().st_mtime)
    cur = game_dir / "Game.log"
    if cur.exists():
        files.append(cur)
    return files


def read_log_file(path):
    """All events in one log file."""
    p = LogParser()
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            out += p.feed(line)
    return out


def location_history(game_dir):
    hist = []
    for p in log_files(game_dir):
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = LOG_LOC.search(line)
                if m:
                    ts = LOG_TS.match(line)
                    if ts:
                        hist.append((parse_ts(ts.group(1)), m.group(1)))
    hist.sort()
    return hist


def location_at(hist, when, max_age_s=6 * 3600):
    best = None
    for ts, loc in hist:
        if ts <= when + 5:
            best = (ts, loc)
        else:
            break
    if best and when - best[0] <= max_age_s:
        return best[1]
    return None
