"""Settings, folders and small helpers shared by every part of the tracker."""

import datetime as dt
import json
import os
import shutil
import string
from pathlib import Path

VERSION = "3.0"

# The tool's own folder (where tracker.py lives) and its data folder
HERE = Path(__file__).resolve().parent.parent
DATA = HERE / "data"

DEFAULT_CONFIG = {
    # Folder holding Game.log, Data\Localization and screenshots (StarCitizen\LIVE).
    # Leave blank and the tracker looks for it.
    "game_dir": "",
    # Game language folder under Data\Localization
    "language": "english",
    # Screen regions as fractions of the screen (x0, y0, x1, y1).
    # Measured on a 16:9 4K screen with the 4.x inventory UI.
    "regions": {
        "right_panel": [0.730, 0.205, 0.975, 0.845],
        "tooltip_band": [0.495, 0.100, 0.745, 0.920],
        "page": [0.825, 0.840, 0.865, 0.865],
        "header": [0.800, 0.100, 0.910, 0.135],
        "footer": [0.540, 0.950, 0.650, 0.990],
        "scrollbar": [0.968, 0.200, 0.978, 0.870],
    },
    "dwell_ms": 350,
    "poll_ms": 50,
    "view_poll_ms": 400,
    "min_match_score": 80,
    "items_per_page": 40,
    # Run fill-in needs the tile's icon to match the run at least this well
    "icon_match": 0.85,
    # Tiles this plain are empty slots
    "empty_std": 4.0,
    # Manual capture key (Windows virtual key code). 0x2D = Insert.
    "capture_key_vk": 45,
    "overlay": True,
    "sound": True,
    "save_tile_images": True,
    # Item types left out of summary.csv (still in inventory.csv and the dashboard)
    "summary_hide_types": ["Magazine", "Battery"],
    # A scan at the same location within this many hours carries on the last one
    "resume_hours": 3,
    # Pressing the kiosk's Stack button starts a fresh scan
    "start_on_stack": True,
    # At a shop terminal: "key" = press the capture key (Insert) to label items you already own,
    # "auto" = check every few seconds (uses more CPU), "off"
    "shop_helper": "key",
    # Keep stations up to date from Game.log between scans
    "track_from_log": True,
    # Local dashboard (only reachable from this PC)
    "dashboard_port": 8765,
    "dashboard_with_live": True,
    # Item data and prices from api.star-citizen.wiki (public, no account needed)
    "fetch_item_data": True,
    "item_data_max_age_days": 7,
}


def say(msg):
    """Print a message, and keep it in data\\tracker.log for checking a run later."""
    line = f"[{dt.datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        log = DATA / "tracker.log"
        if log.exists() and log.stat().st_size > 2_000_000:
            log.replace(DATA / "tracker.old.log")
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now():%Y-%m-%d} {line}\n")
    except Exception:
        pass


def crop_rel(img, region):
    H, W = img.shape[:2]
    x0, y0, x1, y1 = region
    return img[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)]


def _is_game_dir(p):
    p = Path(p)
    return (p / "Game.log").exists() or (p / "Data" / "Localization").exists() or (p / "Data.p4k").exists()


def find_game_dir():
    """Look for the StarCitizen\\LIVE folder in the usual places."""
    cands = [HERE.parent / "StarCitizen" / "LIVE", HERE.parent / "LIVE", HERE.parent]
    tails = [r"Program Files\Roberts Space Industries\StarCitizen\LIVE",
             r"Roberts Space Industries\StarCitizen\LIVE",
             r"Games\Roberts Space Industries\StarCitizen\LIVE",
             r"StarCitizen\LIVE", r"Games\StarCitizen\LIVE", r"Games\StarCitizen\StarCitizen\LIVE"]
    if os.name == "nt":
        for d in string.ascii_uppercase[2:]:
            root = Path(f"{d}:\\")
            if root.exists():
                cands += [root / t for t in tails]
    for c in cands:
        if _is_game_dir(c):
            return c
    return None


def load_config():
    DATA.mkdir(exist_ok=True)
    cfg_path = DATA / "config.json"
    old_cfg = HERE / "config.json"
    if not cfg_path.exists() and old_cfg.exists():
        shutil.copy2(old_cfg, cfg_path)       # carried over from v2
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if cfg_path.exists():
        try:
            user = json.loads(cfg_path.read_text(encoding="utf-8"))
        except Exception:
            user = {}
        for k, v in user.items():
            if k == "regions":
                cfg["regions"].update(v)
            else:
                cfg[k] = v
    # Keep config.json current with any new settings, keeping user values
    try:
        cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except Exception:
        pass
    if not cfg.get("game_dir") or not _is_game_dir(cfg["game_dir"]):
        found = find_game_dir()
        cfg["game_dir"] = str(found) if found else ""
    # Old region values from v1 that picked up the wrong things
    if cfg["regions"].get("scrollbar") == [0.965, 0.200, 0.980, 0.870]:
        cfg["regions"]["scrollbar"] = DEFAULT_CONFIG["regions"]["scrollbar"]
    if cfg["regions"].get("right_panel") == [0.730, 0.220, 0.975, 0.840]:
        cfg["regions"]["right_panel"] = DEFAULT_CONFIG["regions"]["right_panel"]
    return cfg


def migrate_v2_data():
    """Copy a v2 database into the data folder the first time v3 runs."""
    DATA.mkdir(exist_ok=True)
    new_db = DATA / "inventory.db"
    old_db = HERE / "inventory_v2.db"
    if not new_db.exists() and old_db.exists():
        shutil.copy2(old_db, new_db)
        say("Copied your v2 scans into data\\inventory.db (the old file is left as it was).")
    tiles_old, tiles_new = HERE / "tiles", DATA / "tiles"
    if tiles_old.exists() and not tiles_new.exists():
        shutil.copytree(tiles_old, tiles_new)
    return new_db
