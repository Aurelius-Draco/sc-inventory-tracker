"""Live mode: runs beside the game, reads the kiosk as you hover, follows Game.log."""

import threading
import time

import cv2
import numpy as np

from .config import DATA, say
from .gamelog import LogWatcher
from .kiosk import analyse, describe, read_frame_state, save_tile
from .ocr import Reader
from .overlay import Overlay, beep
from .scan import Scan


class Live:
    def __init__(self, app):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.wintypes = ctypes, wintypes
        self.user32 = ctypes.windll.user32
        self.app = app
        self.cfg, self.store = app.cfg, app.store
        self.cat, self.locs = app.cat, app.locs
        self.last_export = 0.0
        self._export_due = False
        self.shop = None
        self.last_filters = ()
        self.shop_markers, self.shop_until, self.shop_time = [], 0.0, 0.0
        self.server = None
        self.SW, self.SH = self.user32.GetSystemMetrics(0), self.user32.GetSystemMetrics(1)
        self.stop_flag = threading.Event()
        self.overlay = None
        self.scan = None
        self.count = 0
        self.stack_time = 0.0

    def export(self, min_gap=3.0):
        """Rewrite the output files, at most every few seconds."""
        now = time.time()
        self.app.mark_dirty()
        if now - self.last_export < min_gap:
            self._export_due = True
            return
        self.last_export = now
        self._export_due = False
        try:
            self.app.refresh(sync=False)
        except Exception as e:
            say(f"Couldn't update the output files ({e}).")

    def shop_read(self, reader, frame):
        """Label the items on a shop screen with what you already own."""
        from .shop import ShopReader, owned_text
        self.shop_time = time.time()
        if self.shop is None:
            self.shop = ShopReader(self.cat)
        H = frame.shape[0]
        s = H / 2160
        lines = reader.read_all(frame, min(1.0, 0.5 / s), s)
        found = self.shop.read(lines, s)
        if not found:
            return False
        model = self.app.refresh(sync=False, write=False)
        markers, said = [], []
        for name, (x0, y0, x1, y1), selected in found:
            text = owned_text(model, name)
            if text:
                markers.append(("label", (x0, y0, x1 - x0, y1 - y0), text))
                said.append(f"{name}: {text}")
            elif selected:
                markers.append(("none", (x0, y0, x1 - x0, y1 - y0), "None in storage"))
        self.shop_markers = markers
        self.shop_until = time.time() + 15
        if said:
            say("Shop: " + "; ".join(said[:6]))
        else:
            say(f"Shop: none of the {len(found)} items on screen are in your storage.")
        return True

    def cursor(self):
        pt = self.wintypes.POINT()
        self.user32.GetCursorPos(self.ctypes.byref(pt))
        return pt.x, pt.y

    def game_focused(self):
        hwnd = self.user32.GetForegroundWindow()
        buf = self.ctypes.create_unicode_buffer(256)
        self.user32.GetWindowTextW(hwnd, buf, 256)
        return "Star Citizen" in buf.value

    def get_scan(self, log, filters=None):
        loc = log.location
        if not loc:
            return None
        if self.scan and self.scan.loc_key == loc:
            return self.scan
        name = self.locs.name(loc)
        filters = tuple(filters or ())
        sid, resumed = self.store.session_for(loc, name, self.cfg["resume_hours"], filters)
        self.scan = Scan(self.store, self.cfg, sid, loc, name)
        say(f"{'Carrying on' if resumed else 'Starting'} scan of {name}" + self.filter_note(filters))
        return self.scan

    @staticmethod
    def filter_note(filters):
        return f" (filter: {', '.join(filters)} only)" if filters else ""

    def restart_scan(self, reason, stack=False, log=None, filters=None):
        """Start a fresh scan: storage changed under us, or Stack was pressed."""
        old = self.scan
        loc_key = old.loc_key if old else (log.location if log else None)
        if not loc_key:
            return None
        loc_name = old.loc_name if old else self.locs.name(loc_key)
        if filters is None:
            filters = self.last_filters
        sid = self.store.new_session(loc_key, loc_name, filters)
        self.scan = Scan(self.store, self.cfg, sid, loc_key, loc_name)
        self.page_done = set()
        self.last_saved = {}
        if reason == "filter":
            say(f"Starting a fresh scan of {loc_name}{self.filter_note(filters)}. Go to page 1 and start hovering.")
            beep(self.cfg, "page")
        elif stack:
            say(f"Stack pressed: starting a fresh scan of {loc_name}{self.filter_note(filters)}. "
                "Go to page 1 and start hovering.")
            beep(self.cfg, "page")
        else:
            say(f"{reason} The storage has changed since the scan began, so it starts again from scratch.")
            say("Start again from page 1. Avoid moving items, the freight elevator or stacking while scanning.")
            beep(self.cfg, "restart")
        return self.scan

    def worker(self):
        cfg = self.cfg
        try:
            grab = make_grabber()
            from .calibrate import apply as apply_calibration
            if apply_calibration(cfg, self.SW, self.SH):
                say("Using your calibrated kiosk layout.")
            say(f"{len(self.cat.names)} item names loaded from global.ini"
                f"{' (StarStrings)' if self.cat.starstrings else ''}")
            reader = Reader()
            log = LogWatcher(cfg["game_dir"])
            self.store.add_events(log.poll())
            self.app.refresh(force=True)
            stacks_seen = log.stack_presses     # ignore presses from before the tracker started
            say(f"Screen {self.SW}x{self.SH}. Last storage location in log: {log.location or 'none yet'}")
            say("Ready. Open a storage kiosk and rest the mouse on items.")
            say("For a run of identical items, hover the first and last. Ctrl+C to stop.")
            rp = cfg["regions"]["right_panel"]
            dwell = cfg["dwell_ms"] / 1000
            key = int(cfg.get("capture_key_vk", 0x2D))
            self.user32.GetAsyncKeyState(key)
            last_pos, still_since, captured_at = None, time.time(), None
            last_log, last_view = 0, 0
            last_state, stable_since = None, 0
            self.last_saved = {}
            self.page_done = set()
            while not self.stop_flag.is_set():
                time.sleep(cfg["poll_ms"] / 1000)
                now = time.time()
                if self._export_due and now - self.last_export > 3:
                    self.export()
                if now - last_log > 1:
                    new = log.poll()
                    last_log = now
                    if new:
                        self.store.add_events(new)
                        if any(e["kind"] in ("move", "buy", "sell") for e in new):
                            self.app.mark_dirty()
                            self.export()
                    if log.stack_presses > stacks_seen:
                        stacks_seen = log.stack_presses
                        if cfg.get("start_on_stack", True) and log.location and now - self.stack_time > 8:
                            # Stacking can merge items, so any earlier freight count is stale
                            log.freight_total.pop(log.location, None)
                            log.freight_floor.pop(log.location, None)
                            self.restart_scan("", stack=True, log=log)
                            self.stack_time = now
                            time.sleep(1.0)          # let the kiosk redraw after stacking
                            last_state = None
                    # Freight elevator count can arrive any time (before or after the scan)
                    sc = self.scan
                    ft = sc and log.freight_total.get(sc.loc_key, (None,))[0]
                    if ft and ft != sc.freight_total:
                        sc.touch(freight_total=ft)
                        say(f"Freight elevator says {sc.loc_name} holds exactly {ft} items.")
                        self.export()
                focused = self.game_focused()
                # --- periodic view check: page, scroll, tile pictures, overlay
                if now - last_view > cfg["view_poll_ms"] / 1000:
                    last_view = now
                    state = None
                    frame = None
                    if focused:
                        frame = grab()
                        if frame is not None:
                            state = read_frame_state(reader, cfg, frame)
                    if not state or state["page"] is None or state["scroll"][0] is None:
                        last_state = None
                        if (frame is not None and not state and cfg.get("shop_helper") == "auto"
                                and now - self.shop_time > 4):
                            self.shop_read(reader, frame)
                        if self.overlay:
                            if now < self.shop_until:
                                self.overlay.show(self.shop_markers, "")
                            else:
                                self.overlay.show([], "")
                    else:
                        sig = (state["page"], state["scroll"])
                        if sig != last_state:
                            last_state, stable_since = sig, now
                        self.last_filters = state.get("filters", ())
                        scan = self.get_scan(log, self.last_filters)
                        if scan and now - stable_since > 0.5 and self.last_filters != scan.filters:
                            scan = self.restart_scan("filter", log=log, filters=self.last_filters)
                        if scan and now - stable_since > 0.5:
                            if scan.pages and state["pages"] and state["pages"] != scan.pages:
                                if now - self.stack_time < 8:
                                    scan.pages = None      # kiosk still settling after Stack
                                else:
                                    scan = self.restart_scan(f"Page count changed from {scan.pages} to "
                                                             f"{state['pages']}.")
                            ft = log.freight_total.get(scan.loc_key, (None,))[0]
                            scan.touch(pages=state["pages"], freight_total=ft)
                            if scan.add_view(frame, state["page"], *state["scroll"]) == "moved":
                                scan = self.restart_scan(f"Page {state['page']} looks different from before.")
                                scan.touch(pages=state["pages"], freight_total=ft)
                                scan.add_view(frame, state["page"], *state["scroll"])
                            if scan.infer():
                                self.export()
                            p = state["page"]
                            r = scan.page_report(p)
                            if r["expected"] and r["known"] >= r["expected"] and p not in self.page_done:
                                self.page_done.add(p)
                                beep(cfg, "page")
                                say(scan.status_line(p))
                        if scan and self.overlay:
                            H, W = frame.shape[:2]
                            self.overlay.show(scan.overlay_markers(state["page"], H, W, *state["scroll"]),
                                              scan.status_line(state["page"]))
                # --- hover capture
                pos = self.cursor()
                forced = self.user32.GetAsyncKeyState(key) & 1
                if not forced:
                    if pos != last_pos:
                        last_pos, still_since, captured_at = pos, now, None
                        continue
                    if captured_at == pos or now - still_since < dwell:
                        continue
                    rx, ry = pos[0] / self.SW, pos[1] / self.SH
                    if not (rp[0] <= rx <= rp[2] and rp[1] <= ry <= rp[3]):
                        continue
                if not focused:
                    continue
                captured_at = pos
                if forced and cfg.get("shop_helper", "key") != "off":
                    frame = grab()
                    if frame is not None and not read_frame_state(reader, cfg, frame):
                        self.shop_read(reader, frame)       # not at a kiosk: maybe a shop terminal
                        continue
                rec = None
                for attempt in range(3):
                    frame = grab()
                    if frame is not None:
                        r = analyse(reader, self.cat, cfg, frame, cursor=None if forced else pos)
                        if r and (not rec or r["verified"] or len(r["ocr_name"]) > len(rec["ocr_name"])):
                            rec = r
                    # Tooltip text can still be appearing; a name that doesn't
                    # match anything gets one more look a moment later
                    if rec and rec["verified"]:
                        break
                    time.sleep(0.3)
                if not rec:
                    if forced:
                        say("Capture key pressed but no item tooltip found on screen.")
                    continue
                scan = self.get_scan(log)
                if not scan:
                    say("No storage location in Game.log yet. Close and reopen the kiosk.")
                    continue
                slot = (rec["page"], rec["cell"])
                sigv = (rec["item_name"], rec["qty"])
                if self.last_saved.get(slot) == sigv:
                    continue
                self.last_saved[slot] = sigv
                if rec["cell"] is None:
                    say("Couldn't place that tile on the grid. Hover it again.")
                    continue
                if scan.add_view(frame, rec["page"], *rec["scroll"]) == "moved":
                    scan = self.restart_scan(f"Page {rec['page']} looks different from before.")
                    scan.add_view(frame, rec["page"], *rec["scroll"])
                scan.add_hover(rec, now)
                scan.touch(pages=rec["pages"])
                scan.infer()
                save_tile(cfg, rec)
                self.export()
                self.count += 1
                beep(cfg, "capture")
                say(describe(rec))
        except Exception as e:
            import traceback
            traceback.print_exc()
            say(f"Tracker stopped on an error: {e}")

    def run(self):
        try:
            self.ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            self.user32.SetProcessDPIAware()
        self.SW, self.SH = self.user32.GetSystemMetrics(0), self.user32.GetSystemMetrics(1)
        t = threading.Thread(target=self.worker, daemon=True)
        if self.cfg.get("dashboard_with_live", True):
            try:
                from .dashboard import start_server
                self.server, url = start_server(self.app, open_browser=False)
                say(f"Dashboard: {url}")
            except Exception as e:
                say(f"Dashboard couldn't start ({e}).")
        if self.cfg.get("overlay"):
            try:
                self.overlay = Overlay(self.SW, self.SH)
            except Exception as e:
                say(f"Overlay unavailable ({e}). Carrying on without it.")
                self.overlay = None
        t.start()
        try:
            while t.is_alive():
                if self.overlay:
                    try:
                        self.overlay.root.update()
                    except Exception as e:
                        # Overlay window failed; keep tracking without it
                        say(f"Overlay stopped ({e}). Carrying on without it.")
                        self.overlay = None
                time.sleep(0.05)
        except KeyboardInterrupt:
            pass
        self.stop_flag.set()
        t.join(3)
        if self.overlay:
            self.overlay.close()
        self.app.mark_dirty()
        model = self.app.refresh(sync=False, force=True)
        n, s = len(model["items"]), len(model["stations"])
        say(f"Stopped. {self.count} items hovered this session.")
        if self.scan:
            print()
            print(self.scan.completeness_text())
            (DATA / "completeness.txt").write_text(self.scan.completeness_text(), encoding="utf-8")
        say(f"{n} items across {s} stations. Files are in the data folder.")
        if self.server:
            self.server.shutdown()


def make_grabber():
    import mss
    sct = mss.MSS() if hasattr(mss, "MSS") else mss.mss()
    mon = sct.monitors[1]

    def grab_mss():
        return cv2.cvtColor(np.array(sct.grab(mon)), cv2.COLOR_BGRA2BGR)

    try:
        import dxcam
        cam = dxcam.create(output_color="BGR")
        last = {"f": None}
        state = {"fn": None}

        def grab_dx():
            for _ in range(10):
                f = cam.grab()
                if f is not None:
                    last["f"] = np.ascontiguousarray(f)
                    return last["f"]
                time.sleep(0.02)
            return last["f"]
        state["fn"] = grab_dx

        def grab():
            try:
                f = state["fn"]()
                if f is not None and f.mean() > 2:
                    return f
            except Exception as e:
                say(f"dxcam failed ({e}), switching to mss")
            state["fn"] = grab_mss
            return grab_mss()
        say("Screen capture: Desktop Duplication (dxcam)")
        return grab
    except Exception as e:
        say(f"Screen capture: mss (dxcam unavailable: {e})")
        return grab_mss



def calibrate_live(app):
    """Two hovers + Insert to fit the kiosk layout to this screen."""
    import ctypes
    from ctypes import wintypes
    from .calibrate import from_frames, save
    user32 = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        user32.SetProcessDPIAware()
    key = int(app.cfg.get("capture_key_vk", 0x2D))
    grab = make_grabber()
    say("Calibration. Open a storage kiosk on page 1, scrolled to the top.")
    shots = []
    for step in ("the TOP-LEFT item", "the item in ROW 2, COLUMN 2"):
        say(f"Rest the mouse on {step} until it lights up, then press Insert.")
        user32.GetAsyncKeyState(key)
        while not user32.GetAsyncKeyState(key) & 1:
            time.sleep(0.05)
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        shots.append((grab(), (pt.x, pt.y)))
        say("Got it.")
    try:
        cal = from_frames(shots[0][0], shots[1][0], shots[0][1], shots[1][1])
    except ValueError as e:
        say(f"Calibration didn't work: {e}")
        return
    save(cal)
    say("Done. Start run.bat as usual.")
