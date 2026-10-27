"""Build README.md from the template and the lists the dashboard uses."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sctracker import about, links, tips  # noqa: E402

t = (ROOT / "tools" / "README.template.md").read_text(encoding="utf-8")
au = about.AUTHOR
who = f"Made by {au['name']}" + (f", in game as **{au['handle']}**" if au["handle"] else "") + "."
about_md = who + "\n\n" + "\n\n".join(about.MESSAGE)
t = t.replace("{RULES}", "\n".join(f"- {r}" for r in about.RULES))
t = t.replace("{TIPS}", tips.as_markdown().strip())
t = t.replace("{LINKS}", links.as_markdown().strip())
t = t.replace("{ABOUT}", about_md)
(ROOT / "README.md").write_text(t, encoding="utf-8")
print("README.md written")
