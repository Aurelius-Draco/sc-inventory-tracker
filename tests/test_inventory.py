"""The inventory picture: scan + log changes + your changes, and a fresh scan replacing them."""
import time

from sctracker.inventory import Builder
from sctracker.store import Store


class Cat:
    by_id = {"gold_ore": "Gold", "behr_rifle_ballistic_01": "P4-AR Rifle"}
    names = {"Gold": "gold_ore", "P4-AR Rifle": "behr_rifle_ballistic_01"}

    def name_for_id(self, i):
        return self.by_id.get((i or "").lower())


class Locs:
    def info(self, key):
        return {"name": "Test Station", "system": "Nyx", "source": "game"}

    def name(self, key):
        return "Test Station"


def make(tmp_path):
    st = Store(tmp_path / "t.db")
    sid = st.new_session("LOC_A", "Test Station")
    t0 = time.time() - 3600
    st.q("UPDATE sessions SET started=?, last=?, freight_total=3, pages=1 WHERE id=?", (t0, t0, sid))
    for col, (name, key) in enumerate([("Gold", "gold_ore"), ("Gold", "gold_ore"), ("P4-AR Rifle", "behr_rifle_ballistic_01")]):
        st.q("INSERT INTO cells (session_id,page,row,col,item_name,item_key,source,qty,ts) VALUES (?,?,?,?,?,?,?,?,?)",
             (sid, 1, 0, col, name, key, "hover", 10 if name == "Gold" else 1, t0))
    return st, t0


def build(st):
    return Builder(st, {}, Cat(), Locs()).build()


def test_scan_plus_changes(tmp_path):
    st, t0 = make(tmp_path)
    m = build(st)
    gold = next(i for i in m["items"] if i["name"] == "Gold")
    assert gold["qty"] == 20 and m["stations"][0]["scan"]["complete"]
    # the log says 5 gold left storage, and you record selling 3 more
    st.add_events([{"id": "e1", "ts": t0 + 60, "kind": "move", "loc": "LOC_A", "inv": None, "item": "gold_ore",
                    "qty": -5, "how": "moved"}])
    st.add_adjustment("LOC_A", "Gold", -3, "sold")
    gold = next(i for i in build(st)["items"] if i["name"] == "Gold")
    assert (gold["qty"], gold["log_change"], gold["your_change"]) == (12, -5, -3)


def test_new_scan_replaces_edits(tmp_path):
    st, t0 = make(tmp_path)
    st.add_adjustment("LOC_A", "Gold", -3, "sold")
    sid = st.new_session("LOC_A", "Test Station")
    st.q("UPDATE sessions SET freight_total=1, pages=1, last=? WHERE id=?", (time.time() + 5, sid))
    st.q("INSERT INTO cells (session_id,page,row,col,item_name,item_key,source,qty,ts) VALUES (?,?,?,?,?,?,?,?,?)",
         (sid, 1, 0, 0, "Gold", "gold_ore", "hover", 7, time.time()))
    m = build(st)
    gold = next(i for i in m["items"] if i["name"] == "Gold")
    assert gold["qty"] == 7 and gold["your_change"] == 0


def test_filtered_scan_replaces_only_its_category(tmp_path):
    st, t0 = make(tmp_path)
    st.q("UPDATE cells SET item_type='Rifle' WHERE item_name='P4-AR Rifle'")
    st.q("UPDATE cells SET item_type='Commodity' WHERE item_name='Gold'")
    # later, a scan with only the Weapons filter on finds 2 rifles
    sid = st.new_session("LOC_A", "Test Station", ("Weapons",))
    st.q("UPDATE sessions SET pages=1, total_est=2, last=? WHERE id=?", (time.time(), sid))
    for col in range(2):
        st.q("INSERT INTO cells (session_id,page,row,col,item_name,item_key,source,qty,item_type,ts) "
             "VALUES (?,?,?,?,?,?,?,?,?,?)",
             (sid, 1, 0, col, "P4-AR Rifle", "behr_rifle_ballistic_01", "hover", 1, "Rifle", time.time()))
    m = build(st)
    q = {i["name"]: i["qty"] for i in m["items"]}
    assert q == {"Gold": 20, "P4-AR Rifle": 2}
    assert m["stations"][0]["scan"]["filtered"][0]["categories"] == ["Weapons"]
