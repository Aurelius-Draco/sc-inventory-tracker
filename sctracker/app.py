"""Everything the tracker's parts share: settings, database, names, and the current picture."""

import threading
import time

from .catalogue import Catalogue
from .config import DATA, say
from .inventory import Builder, sync_logs, write_outputs
from .locations import Locations
from .store import Store


class App:
    def __init__(self, cfg, db_path):
        self.cfg = cfg
        self.store = Store(db_path)
        self.cat = Catalogue(cfg["game_dir"], cfg.get("language", "english"))
        self.locs = Locations(self.cat)
        self.values = None
        if cfg.get("fetch_item_data", True):
            try:
                from .values import Values
                self.values = Values(self.store, cfg)
                self.values.on_update = self.mark_dirty
            except Exception as e:      # optional extra; the tracker works without it
                say(f"Item data unavailable ({e}).")
        self.ships = None
        try:
            from .ships import Ships
            self.ships = Ships(self.store, cfg)
        except Exception as e:
            say(f"Ship data unavailable ({e}).")
        self.lock = threading.RLock()
        self.model = None
        self.model_time = 0.0
        self._dirty = True

    def mark_dirty(self):
        self._dirty = True

    def refresh(self, sync=True, write=True, force=False):
        """Rebuild the picture of what's where, and rewrite the output files."""
        with self.lock:
            if not force and not self._dirty and self.model and time.time() - self.model_time < 30:
                return self.model
            if sync and self.cfg.get("track_from_log", True):
                try:
                    sync_logs(self.store, self.cfg["game_dir"])
                except Exception as e:
                    say(f"Couldn't read the game logs ({e}).")
            self.model = Builder(self.store, self.cfg, self.cat, self.locs, self.values).build()
            self.model_time = time.time()
            self._dirty = False
            if write:
                write_outputs(self.model, self.store, self.cfg, DATA)
            return self.model
