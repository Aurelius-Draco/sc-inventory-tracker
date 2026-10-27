"""The tracker's database (data\\inventory.db, SQLite)."""

import json
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY, location_key TEXT, location_name TEXT,
  started REAL, last REAL, pages INT, freight_total INT
);
CREATE TABLE IF NOT EXISTS cells (
  session_id INT, page INT, row INT, col INT,
  std REAL, sig BLOB,
  item_name TEXT, item_key TEXT, source TEXT, wide INT,
  qty INT, item_type TEXT, manufacturer TEXT, size TEXT, grade TEXT, class TEXT,
  ammo TEXT, quality INT, ts REAL,
  PRIMARY KEY (session_id, page, row, col)
);
CREATE TABLE IF NOT EXISTS observations (
  id INTEGER PRIMARY KEY, session_id INT, ts REAL, page INT, row INT, col INT,
  ocr_name TEXT, item_name TEXT, item_key TEXT, verified INT, match_score REAL,
  item_type TEXT, manufacturer TEXT, size TEXT, grade TEXT, class TEXT,
  qty INT, ammo TEXT, quality INT, source TEXT
);
CREATE TABLE IF NOT EXISTS processed_files (name TEXT PRIMARY KEY);

-- Things Game.log recorded (storage moves, purchases, sales, station ids)
CREATE TABLE IF NOT EXISTS log_events (
  id TEXT PRIMARY KEY, ts REAL, kind TEXT, loc_key TEXT, inv TEXT,
  item TEXT, qty REAL, detail TEXT
);
CREATE INDEX IF NOT EXISTS log_events_ts ON log_events (ts);
CREATE TABLE IF NOT EXISTS loc_ids (inv TEXT PRIMARY KEY, loc_key TEXT, seen REAL);
CREATE TABLE IF NOT EXISTS log_files_read (name TEXT PRIMARY KEY, size INT, read REAL);

-- Changes you (or an assistant) made by hand, e.g. "sold 40 gold"
CREATE TABLE IF NOT EXISTS adjustments (
  id INTEGER PRIMARY KEY, ts REAL, loc_key TEXT, item_name TEXT, item_id TEXT,
  delta INT, note TEXT, source TEXT, event_id TEXT, undone INT DEFAULT 0
);

-- Your notes and tags on items (kept across scans)
CREATE TABLE IF NOT EXISTS notes (item_name TEXT PRIMARY KEY, note TEXT, tags TEXT, updated REAL);

-- Log changes you've told the tracker to ignore or assigned to an item
CREATE TABLE IF NOT EXISTS event_choices (event_id TEXT PRIMARY KEY, choice TEXT, item_name TEXT, ts REAL);

-- Item data fetched from api.star-citizen.wiki
CREATE TABLE IF NOT EXISTS item_data (item_id TEXT PRIMARY KEY, data TEXT, fetched REAL);

-- Things you want to get, buy or loot, in named lists ("Centaurus refit", "Loot to find")
CREATE TABLE IF NOT EXISTS wishlist (
  id INTEGER PRIMARY KEY, list TEXT, name TEXT, item_id TEXT, qty INT, note TEXT, added REAL, done INT DEFAULT 0
);

-- Your ships, and what you've fitted to each slot (blank = stock)
CREATE TABLE IF NOT EXISTS ships (id INTEGER PRIMARY KEY, vehicle TEXT, name TEXT, nickname TEXT, added REAL);
CREATE TABLE IF NOT EXISTS ship_fit (ship_id INT, slot TEXT, item_id TEXT, item_name TEXT,
  PRIMARY KEY (ship_id, slot));

CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
"""

ITEM_FIELDS = ("item_name", "item_key", "qty", "item_type", "manufacturer", "size",
               "grade", "class", "ammo", "quality", "status", "registered")
CELL_COLS = ("std", "sig", "item_name", "item_key", "source", "wide", "qty", "item_type",
             "manufacturer", "size", "grade", "class", "ammo", "quality", "ts", "status", "registered")

ADDED_COLUMNS = {
    "cells": {"status": "TEXT", "registered": "INT"},
    "observations": {"status": "TEXT", "registered": "INT"},
    "sessions": {"build": "TEXT", "filter": "TEXT", "total_est": "INT"},
}


class Store:
    def __init__(self, path):
        self.path = str(path)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.executescript(SCHEMA)
        for table, cols in ADDED_COLUMNS.items():
            have = {r[1] for r in self.db.execute(f"PRAGMA table_info({table})")}
            for c, t in cols.items():
                if c not in have:
                    self.db.execute(f"ALTER TABLE {table} ADD COLUMN {c} {t}")
        self.db.commit()
        self.lock = threading.RLock()

    def q(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            rows = cur.fetchall()
            self.db.commit()
            return rows

    def many(self, sql, rows):
        with self.lock:
            self.db.executemany(sql, rows)
            self.db.commit()

    # --- scan sessions ----------------------------------------------------

    def new_session(self, loc_key, loc_name, filters=()):
        now = time.time()
        gv = self.meta_get("game_version")
        with self.lock:
            cur = self.db.execute("INSERT INTO sessions (location_key, location_name, started, last, build, filter)"
                                  " VALUES (?,?,?,?,?,?)", (loc_key, loc_name, now, now, gv[0] if gv else None,
                                                            ",".join(filters) or None))
            self.db.commit()
            return cur.lastrowid

    def session_for(self, loc_key, loc_name, resume_hours, filters=()):
        now = time.time()
        r = self.q("SELECT id, last, filter FROM sessions WHERE location_key=? ORDER BY last DESC LIMIT 1", (loc_key,))
        if r and now - r[0][1] < resume_hours * 3600 and (r[0][2] or "") == ",".join(filters):
            return r[0][0], True
        return self.new_session(loc_key, loc_name, filters), False

    def done(self, name):
        return bool(self.q("SELECT 1 FROM processed_files WHERE name=?", (name,)))

    def mark(self, name):
        self.q("INSERT OR IGNORE INTO processed_files VALUES (?)", (name,))

    # --- log events -------------------------------------------------------

    def add_events(self, events):
        rows, ids = [], []
        for e in events:
            if e["kind"] == "version":
                cur = self.meta_get("game_version")
                if not cur or e["ts"] >= cur[1]:
                    self.meta_set("game_version", [e["item"], e["ts"]])
                continue
            if e["kind"] == "loc_id":
                ids.append((e["inv"], e["loc"], e["ts"]))
                continue
            if e["kind"] not in ("move", "buy", "sell", "volume", "location", "freight_total"):
                continue
            detail = {k: v for k, v in e.items() if k not in ("id", "ts", "kind", "loc", "inv", "item", "qty")}
            rows.append((e["id"], e["ts"], e["kind"], e.get("loc"), e.get("inv"), e.get("item"), e.get("qty"),
                         json.dumps(detail) if detail else None))
        if ids:
            self.many("INSERT OR REPLACE INTO loc_ids VALUES (?,?,?)", ids)
        if rows:
            self.many("INSERT OR IGNORE INTO log_events VALUES (?,?,?,?,?,?,?,?)", rows)

    def loc_ids(self):
        return dict(self.q("SELECT inv, loc_key FROM loc_ids"))

    # --- your changes -----------------------------------------------------

    def add_adjustment(self, loc_key, item_name, delta, note="", source="you", item_id=None, event_id=None):
        with self.lock:
            cur = self.db.execute("INSERT INTO adjustments (ts, loc_key, item_name, item_id, delta, note, source,"
                                  " event_id) VALUES (?,?,?,?,?,?,?,?)",
                                  (time.time(), loc_key, item_name, item_id, int(delta), note, source, event_id))
            self.db.commit()
            return cur.lastrowid

    def undo_adjustment(self, adj_id):
        self.q("UPDATE adjustments SET undone=1 WHERE id=?", (adj_id,))

    def set_note(self, item_name, note, tags):
        self.q("INSERT OR REPLACE INTO notes VALUES (?,?,?,?)", (item_name, note or "", tags or "", time.time()))

    def notes(self):
        return {r[0]: {"note": r[1], "tags": [t for t in (r[2] or "").split(",") if t.strip()]}
                for r in self.q("SELECT item_name, note, tags FROM notes")}

    def set_event_choice(self, event_id, choice, item_name=None):
        self.q("INSERT OR REPLACE INTO event_choices VALUES (?,?,?,?)", (event_id, choice, item_name, time.time()))

    def event_choices(self):
        return {r[0]: (r[1], r[2]) for r in self.q("SELECT event_id, choice, item_name FROM event_choices")}

    def wish_add(self, list_name, name, item_id, qty, note=""):
        self.q("INSERT INTO wishlist (list, name, item_id, qty, note, added) VALUES (?,?,?,?,?,?)",
               (list_name or "Wish list", name, item_id, int(qty or 1), note or "", time.time()))

    def wish_update(self, wid, **kw):
        for k, v in kw.items():
            if k in ("qty", "note", "done", "list"):
                self.q(f"UPDATE wishlist SET {k}=? WHERE id=?", (v, wid))

    def wish_delete(self, wid):
        self.q("DELETE FROM wishlist WHERE id=?", (wid,))

    def wishlist(self):
        cols = ("id", "list", "name", "item_id", "qty", "note", "added", "done")
        return [dict(zip(cols, r)) for r in self.q(f"SELECT {','.join(cols)} FROM wishlist ORDER BY list, added")]

    def ship_add(self, vehicle, name, nickname=""):
        self.q("INSERT INTO ships (vehicle, name, nickname, added) VALUES (?,?,?,?)",
               (vehicle, name, nickname or "", time.time()))

    def ship_delete(self, sid):
        self.q("DELETE FROM ships WHERE id=?", (sid,))
        self.q("DELETE FROM ship_fit WHERE ship_id=?", (sid,))

    def ships(self):
        cols = ("id", "vehicle", "name", "nickname", "added")
        out = [dict(zip(cols, r)) for r in self.q(f"SELECT {','.join(cols)} FROM ships ORDER BY added")]
        for s in out:
            s["fit"] = {r[0]: {"id": r[1], "name": r[2]} for r in
                        self.q("SELECT slot, item_id, item_name FROM ship_fit WHERE ship_id=?", (s["id"],))}
        return out

    def ship_fit(self, sid, slot, item_id, item_name):
        if item_id:
            self.q("INSERT OR REPLACE INTO ship_fit VALUES (?,?,?,?)", (sid, slot, item_id, item_name))
        else:
            self.q("DELETE FROM ship_fit WHERE ship_id=? AND slot=?", (sid, slot))

    def meta_get(self, k, default=None):
        r = self.q("SELECT v FROM meta WHERE k=?", (k,))
        return json.loads(r[0][0]) if r else default

    def meta_set(self, k, v):
        self.q("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, json.dumps(v)))
