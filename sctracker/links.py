"""Useful community sites, shown on the dashboard's Links tab and in the README.

Addresses checked against the Star Citizen Tools resources page (Oct 2026).
Suggestions welcome as GitHub issues.
"""

LINKS = [
    ("Ship loadouts", [
        ("Erkul", "https://www.erkul.games", "Build, compare and share ship loadouts. Check the parts here before you buy."),
        ("SPViewer", "https://www.spviewer.eu", "Ship performance and loadout comparisons."),
        ("Star Citizen Armory", "https://armory.thespacecoder.space", "Plan a personal (FPS) loadout and get a shopping list."),
    ]),
    ("Prices, trading and hauling", [
        ("UEX", "https://uexcorp.space", "Commodity and item prices reported by players, trade and mining routes."),
        ("SC Trade Tools", "https://sc-trade.tools", "Trade and mining routes, commodity prices, refinery yields."),
        ("SC Hauling Tools", "https://sc-hauling.tools", "Stop and delivery order for hauling contracts."),
    ]),
    ("Finding items, missions and crafting", [
        ("Cornerstone Item Finder", "https://finder.cstone.space", "Where to buy personal and ship equipment, with stats."),
        ("SC Mission Database", "https://scmdb.net", "Missions, crafting blueprints, resources and mining."),
        ("Star Citizen Wiki API", "https://star-citizen.wiki", "Item data this tracker uses for stats and prices."),
    ]),
    ("Maps and places", [
        ("VerseGuide", "https://verseguide.com", "Find locations in the verse."),
        ("Star Citizen Maps", "https://maps.adi.sc", "3D ship interiors with points of interest."),
    ]),
    ("Wikis and lists", [
        ("Star Citizen Tools wiki", "https://starcitizen.tools", "Community wiki, including a big list of community tools."),
        ("Roberts Space Industries", "https://robertsspaceindustries.com", "The official site, Spectrum forums and patch notes."),
    ]),
]


def as_markdown():
    out = []
    for head, items in LINKS:
        out.append(f"### {head}\n")
        out += [f"- [{n}]({u}): {d}" for n, u, d in items]
        out.append("")
    return "\n".join(out)
