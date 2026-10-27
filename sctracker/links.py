"""Useful community sites, shown on the dashboard's Links tab and in the README.

Addresses checked against the Star Citizen Tools resources page (Oct 2026).
Suggestions welcome as GitHub issues.
"""

# (heading, icon, [(name, address, what it is, icon)]). Icons are drawn in the dashboard page.
LINKS = [
    ("Ship loadouts", "ship", [
        ("Erkul", "https://www.erkul.games", "Build, compare and share ship loadouts. Check the parts here before you buy.", "wrench"),
        ("SPViewer", "https://www.spviewer.eu", "Ship performance and loadout comparisons.", "gauge"),
        ("Star Citizen Armory", "https://armory.thespacecoder.space", "Plan a personal (FPS) loadout and get a shopping list.", "shield"),
    ]),
    ("Prices, trading and hauling", "chart", [
        ("UEX", "https://uexcorp.space", "Commodity and item prices reported by players, trade and mining routes.", "chart"),
        ("SC Trade Tools", "https://sc-trade.tools", "Trade and mining routes, commodity prices, refinery yields.", "route"),
        ("SC Hauling Tools", "https://sc-hauling.tools", "Stop and delivery order for hauling contracts.", "crate"),
    ]),
    ("Finding items, missions and crafting", "search", [
        ("Cornerstone Item Finder", "https://finder.cstone.space", "Where to buy personal and ship equipment, with stats.", "search"),
        ("SC Mission Database", "https://scmdb.net", "Missions, crafting blueprints, resources and mining.", "scroll"),
        ("Star Citizen Wiki API", "https://star-citizen.wiki", "Item data this tracker uses for stats and prices.", "data"),
    ]),
    ("Maps and places", "pin", [
        ("VerseGuide", "https://verseguide.com", "Find locations in the verse.", "pin"),
        ("Star Citizen Maps", "https://maps.adi.sc", "3D ship interiors with points of interest.", "cube"),
    ]),
    ("Wikis and lists", "book", [
        ("Star Citizen Tools wiki", "https://starcitizen.tools", "Community wiki, including a big list of community tools.", "book"),
        ("Roberts Space Industries", "https://robertsspaceindustries.com", "The official site, Spectrum forums and patch notes.", "planet"),
    ]),
]


def as_markdown():
    out = []
    for head, _icon, items in LINKS:
        out.append(f"### {head}\n")
        out += [f"- [{n}]({u}): {d}" for n, u, d, _i in items]
        out.append("")
    return "\n".join(out)
