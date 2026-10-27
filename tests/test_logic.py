import json

from sctracker import calibrate, kiosk
from sctracker.config import DEFAULT_CONFIG
from sctracker.inventory import tidy_id
from sctracker.scan import detect_repeats


def test_repeat_detection():
    names = [f"Item {c}" for c in "ABCDEFGH"]
    seq = [((1, i, 0), n) for i, n in enumerate(names + names[:7] + ["Item Z"])]
    repeated, chunks = detect_repeats(seq)
    assert chunks and len(repeated) == 7


def test_no_false_repeat_on_sorted_list():
    seq = [((1, i, 0), f"Item {i:03d}") for i in range(60)]
    assert detect_repeats(seq) == ({}, [])


def test_calibration_round_trip():
    s, ox, oy = 1440 / 2160, 880, 0
    a = (s * calibrate.REF_A[0] + ox, s * calibrate.REF_A[1] + oy, 1, 1)
    b = (s * calibrate.REF_B[0] + ox, s * calibrate.REF_B[1] + oy, 1, 1)
    cal = calibrate.solve(a, b, 3440, 1440)
    assert abs(cal["s"] - s) < 1e-3 and abs(cal["ox"] - ox) < 1
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    cfg["calibration"] = cal
    assert calibrate.apply(cfg, 3440, 1440)
    # the first column's left edge, in screen pixels, lands where the hover said
    assert abs(kiosk.GEOM["col_x"][0] * 3440 / 3840 - a[0]) < 1
    calibrate.apply({"regions": {}}, 3840, 2160)       # back to standard for other tests


def test_tidy_id():
    assert tidy_id("Harvestable_JumpingLime") == "Jumping Lime"
    assert tidy_id("Carryable_1H_CY_hadesian_fragment_1_large_flawed_a").startswith("Hadesian")
