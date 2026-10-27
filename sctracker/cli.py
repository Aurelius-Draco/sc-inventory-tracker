"""Command line: live mode, dashboard, exports, and quick edits."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import cv2

from .config import DATA, VERSION, load_config, migrate_v2_data, say

HELP = """
Examples:
  run.bat                                    live mode, while you play
  tracker.py --dashboard                     open the dashboard in your browser
  tracker.py --where "Ripper"                which stations hold an item
  tracker.py --adjust "Alpha" "Gold" -40 --note "sold at Levski"
  tracker.py --export                        rewrite the files in the data folder
"""


def find_station(app, text):
    """A station from part of its name or its log id."""
    model = app.refresh(write=False)
    t = text.lower()
    hits = [s for s in model["stations"] if t == s["key"].lower() or t == s["name"].lower()]
    hits = hits or [s for s in model["stations"] if t in s["name"].lower() or t in s["key"].lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        sys.exit(f"No station matching '{text}'. Known: " + ", ".join(s["name"] for s in model["stations"]))
    sys.exit(f"'{text}' matches several stations: " + ", ".join(s["name"] for s in hits))


def find_item(app, station, text):
    from rapidfuzz import fuzz, process
    model = app.refresh(write=False)
    here = {i["name"]: i for i in model["items"] if i["location_key"] == station["key"]}
    for name in here:
        if name.lower() == text.lower():
            return name, here[name].get("id")
    hit = process.extractOne(text, list(here), scorer=fuzz.WRatio) if here else None
    if hit and hit[1] >= 85:
        return hit[0], here[hit[0]].get("id")
    if text in app.cat.names:
        return text, app.cat.id_for_name(text)
    hit = process.extractOne(text, app.cat._choices, scorer=fuzz.WRatio) if app.cat._choices else None
    if hit and hit[1] >= 90:
        return hit[0], app.cat.id_for_name(hit[0])
    return text, None


def mode_where(app, text):
    model = app.refresh(write=False)
    t = text.lower()
    rows = [i for i in model["items"] if t in i["name"].lower() and (i["qty"] or i["expired"])]
    if not rows:
        print(f"Nothing matching '{text}' in any scanned station.")
        return
    for i in rows:
        st = next(s for s in model["stations"] if s["key"] == i["location_key"])
        age = f", scanned {st['age_days']} days ago" if st["age_days"] is not None else ", not scanned"
        extra = f" (+{i['expired']} expired)" if i["expired"] else ""
        print(f"{i['qty']:>5}  {i['name']}  at {i['location']} ({i['system']}){extra}{age}")


def mode_scan(app):
    from .gamelog import location_at, location_history
    from .kiosk import analyse, describe, read_frame_state, read_qr_time, save_tile
    from .ocr import Reader
    from .scan import Scan
    from .calibrate import apply as apply_calibration
    cfg, store, locs = app.cfg, app.store, app.locs
    reader = Reader()
    hist = location_history(cfg["game_dir"])
    folder = Path(cfg["game_dir"]) / "screenshots"
    files = sorted(folder.glob("*.jpg")) + sorted(folder.glob("*.png"))
    say(f"{len(files)} screenshots in {folder}")
    scans = {}
    found = 0
    for p in files:
        if store.done(p.name):
            continue
        img = cv2.imread(str(p))
        store.mark(p.name)
        if img is None:
            continue
        apply_calibration(cfg, img.shape[1], img.shape[0])
        state = read_frame_state(reader, cfg, img)
        if not state or not state["page"]:
            continue
        when = read_qr_time(img) or p.stat().st_mtime
        loc = location_at(hist, when)
        if not loc:
            continue
        if loc not in scans:
            sid, _ = store.session_for(loc, locs.name(loc), cfg["resume_hours"])
            scans[loc] = Scan(store, cfg, sid, loc, locs.name(loc))
        scan = scans[loc]
        scan.touch(pages=state["pages"])
        if state["scroll"][0] is not None:
            scan.add_view(img, state["page"], *state["scroll"])
        rec = analyse(reader, app.cat, cfg, img, state=state)
        if rec and rec["cell"]:
            scan.add_hover(rec, when)
            save_tile(cfg, rec)
            found += 1
            say(describe(rec))
    for scan in scans.values():
        scan.infer()
        print(scan.completeness_text())
    app.refresh(force=True)
    say(f"{found} items from screenshots. Files updated in the data folder.")


def mode_test(app, image):
    from .gamelog import location_at, location_history
    from .kiosk import analyse, read_frame_state, read_qr_time
    from .ocr import Reader
    cfg = app.cfg
    reader = Reader()
    img = cv2.imread(image)
    from .calibrate import apply as apply_calibration
    apply_calibration(cfg, img.shape[1], img.shape[0])
    t = time.time()
    rec = analyse(reader, app.cat, cfg, img)
    took = time.time() - t
    if rec is None:
        print("No item tooltip found in this image.")
        print("Frame state:", read_frame_state(reader, cfg, img))
        return
    rec.pop("_tile_img", None)
    when = read_qr_time(img)
    loc = location_at(location_history(cfg["game_dir"]), when) if when else None
    rec["location_name"] = app.locs.name(loc)
    rec["analysis_seconds"] = round(took, 2)
    print(json.dumps(rec, indent=2, default=str))


def main():
    ap = argparse.ArgumentParser(description=f"SC Inventory Tracker v{VERSION}", epilog=HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dashboard", action="store_true", help="open the dashboard (no scanning)")
    ap.add_argument("--export", action="store_true", help="rewrite the output files")
    ap.add_argument("--where", metavar="ITEM", help="which stations hold an item")
    ap.add_argument("--adjust", nargs=3, metavar=("STATION", "ITEM", "CHANGE"),
                    help="record a change by hand, e.g. --adjust Alpha Gold -40")
    ap.add_argument("--note", default="", help="note to go with --adjust")
    ap.add_argument("--rename-station", nargs=2, metavar=("STATION", "NAME"), help="set a station's name")
    ap.add_argument("--scan-screenshots", action="store_true", help="read kiosk screenshots instead")
    ap.add_argument("--test", metavar="IMAGE", help="read one screenshot and print what it found")
    ap.add_argument("--calibrate", nargs="*", metavar="IMAGE",
                    help="fit the kiosk layout to a screen that isn't 16:9 (live, or from two screenshots)")
    ap.add_argument("--game-dir")
    ap.add_argument("--db")
    ap.add_argument("--no-overlay", action="store_true")
    args = ap.parse_args()

    cfg = load_config()
    if args.game_dir:
        cfg["game_dir"] = args.game_dir
    if args.no_overlay:
        cfg["overlay"] = False
    db = args.db or migrate_v2_data()
    if not cfg["game_dir"]:
        say("Couldn't find the Star Citizen LIVE folder. Set game_dir in data\\config.json, "
            "e.g. C:\\Program Files\\Roberts Space Industries\\StarCitizen\\LIVE")

    from .app import App
    app = App(cfg, db)

    if args.calibrate is not None:
        from .calibrate import from_frames, save
        if len(args.calibrate) == 2:
            a, b = (cv2.imread(p) for p in args.calibrate)
            try:
                return save(from_frames(a, b))
            except ValueError as e:
                sys.exit(str(e))
        if os.name != "nt":
            sys.exit("Live calibration only runs on Windows. Pass two screenshots instead.")
        from .live import calibrate_live
        return calibrate_live(app)
    if args.test:
        return mode_test(app, args.test)
    if args.scan_screenshots:
        return mode_scan(app)
    if args.where:
        return mode_where(app, args.where)
    if args.adjust:
        st = find_station(app, args.adjust[0])
        try:
            delta = int(args.adjust[2])
        except ValueError:
            sys.exit("CHANGE must be a whole number, e.g. -40 or 3")
        name, item_id = find_item(app, st, args.adjust[1])
        app.store.add_adjustment(st["key"], name, delta, args.note, source="you", item_id=item_id)
        app.mark_dirty()
        app.refresh(force=True)
        return say(f"Recorded {delta:+d} {name} at {st['name']}.")
    if args.rename_station:
        st = find_station(app, args.rename_station[0])
        app.locs.set_name(st["key"], args.rename_station[1])
        app.refresh(force=True)
        return say(f"{st['key']} is now called {args.rename_station[1]}.")
    if args.export:
        m = app.refresh(force=True)
        return say(f"{len(m['items'])} items across {len(m['stations'])} stations written to {DATA}")
    if args.dashboard:
        from .dashboard import start_server
        app.refresh(force=True)
        server, url = start_server(app, open_browser=True)
        say(f"Dashboard at {url}  (Ctrl+C to stop)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.shutdown()
        return
    if os.name != "nt":
        sys.exit("Live mode only runs on Windows.")
    say(f"SC Inventory Tracker v{VERSION}")
    from .live import Live
    Live(app).run()
