"""The local dashboard: a web page served from this PC only (http://127.0.0.1).

Nothing here is reachable from other machines. Each run uses a fresh random
token, so other web pages open in your browser can't send changes to it.
"""

import json
import re
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from pathlib import Path

from .config import DATA, VERSION

STATIC = Path(__file__).resolve().parent / "static"
SETTINGS = ("overlay", "sound", "track_from_log", "fetch_item_data", "summary_hide_types", "dashboard_with_live",
            "shop_helper")


def start_server(app, open_browser=False):
    token = secrets.token_urlsafe(16)
    port = int(app.cfg.get("dashboard_port", 8765))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _host_ok(self):
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if "json" in ctype or "html" in ctype else ""))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if not self._host_ok():
                return self._send(403, {"error": "local only"})
            path = self.path.split("?")[0]
            qs = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
            if path in ("/", "/index.html"):
                html = (STATIC / "index.html").read_text(encoding="utf-8")
                html = html.replace("__TOKEN__", token).replace("__VERSION__", VERSION)
                return self._send(200, html.encode("utf-8"), "text/html")
            if re.fullmatch(r"/(tips|img)/[a-z0-9-]+\.jpg", path) and (STATIC / path.lstrip("/")).is_file():
                return self._send(200, (STATIC / path.lstrip("/")).read_bytes(), "image/jpeg")
            if path == "/favicon.ico":
                return self._send(200, (STATIC.parent / "assets" / "dashboard.ico").read_bytes(), "image/x-icon")
            if self.headers.get("X-Token") != token:
                return self._send(403, {"error": "bad token"})
            if path == "/api/model":
                return self._send(200, app.refresh())
            if path == "/api/settings":
                return self._send(200, {k: app.cfg.get(k) for k in SETTINGS})
            if path == "/api/links":
                from .links import LINKS
                return self._send(200, [{"head": h, "icon": ic, "items": [dict(name=n, url=u, about=d, icon=c)
                                                                    for n, u, d, c in i]}
                                        for h, ic, i in LINKS])
            if path == "/api/about":
                from . import about
                au = dict(about.AUTHOR)
                au["picture"] = f"/img/{au['picture']}" if au.get("picture") else ""
                return self._send(200, {"author": au, "message": about.MESSAGE, "rules": about.RULES,
                                        "links": about.LINKS,
                                        "wish_intro": about.WISHLIST_INTRO,
                                        "wishlist": [dict(name=n, maker=m, url=u, why=w) for n, m, u, w in about.WISHLIST],
                                        "version": VERSION})
            if path == "/api/suggest":
                return self._send(200, suggest(app, qs.get("q", "")))
            if path == "/api/howto":
                return self._send(200, howto(app, qs.get("id"), qs.get("name")))
            if path == "/api/places":
                return self._send(200, places(app, qs.get("key", "")))
            if path == "/api/vehicles":
                return self._send(200, app.ships.search(qs.get("q", "")) if app.ships else [])
            if path == "/api/ships":
                return self._send(200, my_ships(app))
            if path == "/api/options":
                return self._send(200, options(app, qs.get("type"), qs.get("size")))
            if path == "/api/tips":
                from .tips import PICTURES, TIPS
                return self._send(200, [{"head": h, "items": i,
                                         "pictures": [{"src": f"/tips/{f}", "alt": a} for f, a in PICTURES.get(h, [])]}
                                        for h, i in TIPS])
            return self._send(404, {"error": "not found"})

        def do_POST(self):
            if not self._host_ok() or self.headers.get("X-Token") != token:
                return self._send(403, {"error": "not allowed"})
            try:
                n = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                return self._send(400, {"error": "bad request"})
            try:
                msg = handle_post(app, self.path, body)
            except ValueError as e:
                return self._send(400, {"error": str(e)})
            app.mark_dirty()
            return self._send(200, {"ok": True, "message": msg, "model": app.refresh(sync=False, force=True)})

    server = None
    for p in range(port, port + 10):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            port = p
            break
        except OSError:
            continue
    if server is None:
        raise OSError(f"ports {port}-{port + 9} are all in use")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    if open_browser:
        webbrowser.open(url)
    return server, url


def owned_by_id(app):
    """item id or lower-case name -> [{location, qty}] from the current picture."""
    model = app.refresh(write=False)
    out = {}
    for i in model["items"]:
        if not i["qty"]:
            continue
        for k in filter(None, ((i.get("id") or "").lower(), i["name"].lower())):
            out.setdefault(k, []).append({"location": i["location"], "qty": i["qty"]})
    return out


def suggest(app, q, limit=12):
    """Item names for the wish list box, best first."""
    from rapidfuzz import fuzz, process
    q = (q or "").strip()
    if len(q) < 2:
        return []
    if not hasattr(app, "_plain_names"):
        match_name(app, "x")
    plain = list(app._plain_names)
    hits = process.extract(q.lower(), plain, scorer=fuzz.WRatio, limit=limit * 2)
    owned = owned_by_id(app)
    out, seen = [], set()
    for cand, score, _ in hits:
        name = app._plain_names[cand]
        if score < 60 or name in seen:
            continue
        seen.add(name)
        item_id = app.cat.id_for_name(name)
        have = owned.get(item_id or "", []) or owned.get(name.lower(), [])
        out.append({"name": name, "id": item_id, "have": sum(h["qty"] for h in have)})
        if len(out) >= limit:
            break
    return out


def howto(app, item_id, name=None):
    item_id = (item_id or "").lower() or (app.cat.id_for_name(name) if name else None)
    owned = owned_by_id(app)
    out = {"owned": owned.get(item_id or "", []) or owned.get((name or "").lower(), []), "found": False}
    if not item_id or not app.values:
        return out
    fitted = app.ships.fitted_on.get(item_id) or app.ships.fitted_on.get(item_id + "_scitem") if app.ships else []
    out.update(app.values.howto(item_id, fitted_on=fitted or []))
    if not out.get("found") and not item_id.endswith("_scitem"):
        alt = app.values.howto(item_id + "_scitem", fitted_on=fitted or [])
        if alt.get("found"):
            out.update(alt)
    return out


def places(app, key):
    """Place names from the game text, the most likely matches for this station first."""
    from rapidfuzz import fuzz
    names = sorted({v for _, v in app.locs._places()})
    cur = app.locs.name(key) if key else ""
    ref = (cur + " " + key.replace("_", " ")).lower()
    return sorted(names, key=lambda n: -fuzz.token_set_ratio(n.lower(), ref))


def options(app, typ, size):
    if not app.values or not typ or not size:
        return []
    owned = owned_by_id(app)
    rows = app.values.options(typ, size)
    for r in rows:
        have = owned.get(r["id"], []) or owned.get(r["id"].replace("_scitem", ""), [])
        r["have"] = sum(h["qty"] for h in have)
        r["where"] = have
    return rows


def my_ships(app):
    """Your ships with their slots grouped (two identical coolers shown once, x2)."""
    from .ships import ITEM_TYPE
    if not app.ships:
        return {"ships": [], "loading": False}
    owned = owned_by_id(app)
    out = []
    for s in app.store.ships():
        v = app.ships.detail(s["vehicle"]) or {}
        groups = {}
        for slot in v.get("slots", []):
            if slot["type"] not in ITEM_TYPE:
                continue
            fit = s["fit"].get(slot["port"])
            key = (slot["type"], slot["max"], slot["stock_id"], (fit or {}).get("id"))
            g = groups.setdefault(key, dict(type=slot["type"], item_type=ITEM_TYPE[slot["type"]], label=slot["label"],
                                            size=slot["max"], count=0, slots=[], stock=dict(id=slot["stock_id"],
                                            name=slot["stock_name"]), fitted=fit or dict(id=slot["stock_id"],
                                            name=slot["stock_name"]), changed=bool(fit)))
            g["count"] += 1
            g["slots"].append(slot["port"])
        for g in groups.values():
            fid = (g["fitted"]["id"] or "").lower()
            have = owned.get(fid, []) or owned.get(fid.replace("_scitem", ""), []) or \
                owned.get((g["fitted"]["name"] or "").lower(), [])
            g["have"] = sum(h["qty"] for h in have)
            g["where"] = have
        out.append(dict(s, maker=v.get("maker"), role=v.get("role"), groups=list(groups.values()),
                        url=v.get("url"), fit=None))
    return {"ships": out, "loading": app.ships.loading, "count": len(app.ships.list)}


def match_name(app, text):
    """Closest item name in the game text: (name, item id, score).

    Ignores StarStrings' "Mil/3/C " style prefix, and any model number typed
    (FR-76, S3, 40 cap) must appear in the name it matches.
    """
    from rapidfuzz import fuzz, process
    if text in app.cat.names:
        return text, app.cat.id_for_name(text), 100
    if not hasattr(app, "_plain_names"):
        app._plain_names = {}
        for n in app.cat.names:
            app._plain_names.setdefault(re.sub(r"^[A-Za-z]{3}/\d+/[A-Z] ", "", n).lower(), n)
    plain = list(app._plain_names)
    q = text.lower().strip()
    if q in app._plain_names:
        n = app._plain_names[q]
        return n, app.cat.id_for_name(n), 100
    codes = re.findall(r"[a-z]*\d[\w-]*", q)
    best = None
    for cand, score, _ in process.extract(q, plain, scorer=fuzz.WRatio, limit=15):
        if codes and not all(c in cand for c in codes):
            continue
        score = 0.5 * fuzz.ratio(q, cand) + 0.5 * fuzz.token_set_ratio(q, cand)
        if not best or score > best[1]:
            best = (cand, score)
    if best and best[1] >= (60 if codes else 80):
        n = app._plain_names[best[0]]
        return n, app.cat.id_for_name(n), best[1]
    return text, None, best[1] if best else 0


def handle_post(app, path, b):
    store = app.store
    if path == "/api/adjust":
        delta = int(b.get("delta") or 0)
        if not delta or not b.get("location_key") or not b.get("name"):
            raise ValueError("Pick a station, an item and a change other than 0.")
        store.add_adjustment(b["location_key"], b["name"], delta, b.get("note", ""), source="you",
                             item_id=b.get("id"))
        return f"Recorded {delta:+d} {b['name']}."
    if path == "/api/undo":
        store.undo_adjustment(int(b["adjustment_id"]))
        return "Change undone."
    if path == "/api/note":
        tags = ",".join(t.strip() for t in (b.get("tags") or []) if t.strip())
        store.set_note(b["name"], b.get("note", ""), tags)
        return "Note saved."
    if path == "/api/station_name":
        if not b.get("name") or b["name"] not in {v for _, v in app.locs._places()}:
            raise ValueError("Pick a name from the list.")
        app.locs.set_name(b["key"], b["name"].strip())
        return "Station renamed."
    if path == "/api/event":
        eid, choice = b["event_id"], b["choice"]
        if choice == "ignore":
            store.set_event_choice(eid, "ignore")
            return "Ignored."
        if choice == "location":
            store.set_event_choice(eid, "location", b["location_key"])
            return "Purchase assigned."
        if choice == "item":
            qty = int(b.get("qty") or 0)
            store.add_adjustment(b["location_key"], b["name"], -abs(qty), b.get("note") or "sold (from the log)",
                                 source="log", item_id=b.get("id"), event_id=eid)
            store.set_event_choice(eid, "item", b["name"])
            return "Sale recorded."
        raise ValueError("Unknown choice.")
    if path == "/api/wish_add" and b.get("name") and not b.get("names"):
        name, item_id = b["name"], b.get("id")
        if not item_id:
            name, item_id, _ = match_name(app, name)
        store.wish_add(b.get("list"), name, item_id, int(b.get("qty") or 1), b.get("note", ""))
        return f"Added {name} to {b.get('list') or 'Wish list'}."
    if path == "/api/ship_add":
        v = app.ships.get(b.get("cls")) if app.ships else None
        if not v:
            raise ValueError("Pick a ship from the list.")
        store.ship_add(v["cls"], v["name"], b.get("nickname", ""))
        threading.Thread(target=app.ships.detail, args=(v["cls"],), daemon=True).start()
        return f"Added {v['name']}."
    if path == "/api/ship_delete":
        store.ship_delete(int(b["id"]))
        return "Ship removed."
    if path == "/api/ship_fit":
        for slot in b.get("slots") or []:
            store.ship_fit(int(b["ship_id"]), slot, b.get("item_id"), b.get("item_name"))
        return "Fit saved." if b.get("item_id") else "Back to the stock part."
    if path == "/api/ship_wish":
        n = 0
        for it in b.get("items") or []:
            store.wish_add(b.get("list"), it["name"], it.get("id"), int(it.get("qty") or 1), it.get("note", ""))
            n += 1
        return f"Added {n} part{'s' if n != 1 else ''} to {b.get('list')}."
    if path == "/api/wish_add":
        lines = [x.strip() for x in (b.get("names") or "").splitlines() if x.strip()]
        if not lines:
            raise ValueError("Type an item name, or paste a list (one per line).")
        added, unsure = 0, []
        for line in lines:
            qty = 1
            m = re.match(r"^(\d+)\s*x?\s+(.+)$", line) or re.match(r"^(.+?)\s+x\s*(\d+)$", line)
            if m:
                a, c = m.groups()
                qty, line = (int(a), c) if a.isdigit() else (int(c), a)
            name, item_id, score = match_name(app, line)
            if score < 85:
                unsure.append(line)
            store.wish_add(b.get("list"), name, item_id, qty * int(b.get("qty") or 1), b.get("note", ""))
            added += 1
        msg = f"Added {added} to {b.get('list') or 'Wish list'}."
        if unsure:
            msg += f" Check these names, they weren't a close match: {', '.join(unsure[:5])}"
        return msg
    if path == "/api/wish_update":
        store.wish_update(int(b["id"]), **{k: b[k] for k in ("qty", "note", "done", "list") if k in b})
        return "Wish list updated."
    if path == "/api/wish_delete":
        store.wish_delete(int(b["id"]))
        return "Removed from the wish list."
    if path == "/api/share":
        import datetime as _dt
        from .inventory import share_file
        data = share_file(app.refresh(write=False), b.get("label", ""), bool(b.get("notes")))
        name = f"share_{_dt.date.today().isoformat()}.json"
        (DATA / name).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        return f"Saved data\\{name}. Send that file to whoever you want to share with."
    if path == "/api/fresh_start":
        import time as _t
        store.meta_set("fresh_start", _t.time())
        return "Fresh start: earlier scans and changes are kept in the database but no longer shown."
    if path == "/api/settings":
        cfg_path = DATA / "config.json"
        saved = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
        for k in SETTINGS:
            if k in b:
                app.cfg[k] = b[k]
                saved[k] = b[k]
        cfg_path.write_text(json.dumps(saved, indent=2), encoding="utf-8")
        return "Settings saved. Overlay and sound changes apply next time live mode starts."
    raise ValueError("Unknown request.")
