"""The dashboard page must stay a single offline file the server can fill in."""
import re
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "sctracker" / "static" / "index.html").read_text(encoding="utf-8")


def test_placeholders_kept():
    assert "__TOKEN__" in PAGE and "__VERSION__" in PAGE


def test_no_sample_data_in_real_page():
    assert "DEMO MOCK" not in PAGE and "__MOCK__" not in PAGE


def test_nothing_loaded_from_the_internet():
    assert not re.search(r"""<(script|link|img|iframe)[^>]+(src|href)\s*=\s*["']?(https?:)?//""", PAGE, re.I)
    assert not re.search(r"""@import|url\(\s*["']?(https?:)?//""", PAGE, re.I)
