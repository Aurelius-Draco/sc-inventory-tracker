"""Build README.md from the template and the lists the dashboard uses."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from sctracker import about, links, tips  # noqa: E402

t = (ROOT / "tools" / "README.template.md").read_text(encoding="utf-8")
au = about.AUTHOR
who = f"Made by {au['name']}" + (f", in game as **{au['handle']}**" if au["handle"] else "") + "."
pic = (f'<img src="sctracker/static/img/{au["picture"]}" width="120" align="left" alt="">\n\n'
       if au.get("picture") else "")
about_md = pic + who + "\n\n" + "\n\n".join(about.MESSAGE) + '\n<br clear="left">\n\n' + "\n".join(
    f"- **{l['title']}** [{l['text']}]({l['url']}). {l['about']}" for l in about.LINKS)
about_md += "\n\n### Ships on my wish list\n\n" + about.WISHLIST_INTRO + "\n\n" + "\n".join(
    f"- [{n}]({u}) ({m}). {w}" for n, m, u, w in about.WISHLIST)
t = t.replace("{RULES}", "\n".join(f"- {r}" for r in about.RULES))
t = t.replace("{TIPS}", tips.as_markdown().strip())
t = t.replace("{LINKS}", links.as_markdown().strip())
t = t.replace("{ABOUT}", about_md)
(ROOT / "README.md").write_text(t, encoding="utf-8")
print("README.md written")
