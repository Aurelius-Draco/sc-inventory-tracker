"""Dashboard preview with sample data, for design work without the game or the server.

    python tools/make_preview.py           build design/dashboard-preview.html from the real page
    python tools/make_preview.py --apply   copy design changes back into the real page

The preview is sctracker/static/index.html with design/sample-data.html added
just before the app's script. The sample block fakes the server's /api/* replies.
--apply strips that block out again and writes the result to the real page.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "sctracker" / "static" / "index.html"
SAMPLE = ROOT / "design" / "sample-data.html"
PREVIEW = ROOT / "design" / "dashboard-preview.html"
BLOCK = re.compile(r"<!-- DEMO MOCK START.*?<!-- DEMO MOCK END -->\n?", re.S)


def check(html):
    for need in ("__TOKEN__", "__VERSION__"):
        if need not in html:
            sys.exit(f"The page has lost the {need} placeholder. The server needs it.")
    if re.search(r"""(src|href)\s*=\s*["']?(https?:)?//""", html, re.I) and "<link" in html.lower():
        print("Warning: the page may load something from the internet. It must not.")


def build():
    html = PAGE.read_text(encoding="utf-8")
    if "DEMO MOCK" in html:
        sys.exit("The real page has sample data in it. Run --apply first.")
    at = html.index("<script>", html.index("<body"))
    PREVIEW.write_text(html[:at] + SAMPLE.read_text(encoding="utf-8") + html[at:], encoding="utf-8")
    print(f"Wrote {PREVIEW.relative_to(ROOT)}. Open it in a browser.")


def apply():
    html = PREVIEW.read_text(encoding="utf-8")
    m = BLOCK.search(html)
    if not m:
        sys.exit("No sample data block found in the preview. Nothing applied.")
    SAMPLE.write_text(m.group(0), encoding="utf-8")
    page = BLOCK.sub("", html, count=1)
    check(page)
    PAGE.write_text(page, encoding="utf-8")
    print(f"Updated {PAGE.relative_to(ROOT)} and {SAMPLE.relative_to(ROOT)} from the preview.")


if __name__ == "__main__":
    apply() if "--apply" in sys.argv else build()
