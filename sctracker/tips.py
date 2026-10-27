"""Tips for getting good scans. Shown on the dashboard and copied into the README."""

TIPS = [
    ("Before you scan", [
        "Take your backpack off, or at least anything bright. The item tooltip appears over your character, "
        "and a yellow or white backpack behind it makes the text much harder to read.",
        "Run the game in borderless windowed mode so the tracker can see the screen.",
        "Graphics: set Chromatic Aberration to 0 and turn Film Grain off. Keep \"Session Information QR Code\" "
        "on, it lets the tracker date screenshots.",
        "Turn the overlay off in Settings if your game stutters while the tracker runs. Clicks and chimes still work.",
    ]),
    ("Starting a scan", [
        "Open the storage kiosk, then press its Stack button. That starts a fresh scan (you'll hear a chime).",
        "Stack sometimes needs a few presses before it works. Presses close together count as one.",
        "Check the list looks complete before you start. The kiosk sometimes leaves items out (crates are the "
        "usual ones). If something you know you have is missing, press Stack again or close and reopen the kiosk.",
        "Keep the right panel on your station's storage (LOCAL). Don't change the sort order mid-scan.",
        "Only after some of your things? Switch on one or more category filters (Armor, Weapons, Vehicles and so on) "
        "before you press Stack. The tracker sees which are on, scans just those, and slots the result into your "
        "last full scan. Use a whole category (All Categories in its menu), not part of one. Changing a filter "
        "mid-scan starts a fresh scan of the new selection.",
    ]),
    ("Scanning quickly", [
        "Rest the mouse on each item for about half a second. A click sound and a green dot mean it's recorded.",
        "For a run of identical items, hover only the first and the last. Everything between is filled in "
        "(blue dot) because the kiosk sorts by name. It works across pages too.",
        "Amber outlines are tiles still to hover. Scroll each page to the bottom so the tracker sees every tile. "
        "Scrolling back and hovering again never double counts.",
        "Locked (expired) items still need a hover so the count comes out right. For a two-slot locked item, "
        "hover its left half.",
        "If a name comes out cut off, the tooltip was still appearing. Hold still a moment longer; the tracker "
        "has another look by itself. Press Insert to force a capture.",
        "Don't move items in or out, stack, or use the freight elevator while scanning. The list changes and "
        "the scan starts again.",
    ]),
    ("At shops", [
        "At a shop terminal, press Insert and the overlay labels every item on screen that you already have in "
        "storage, with how many and where. Set it to automatic in Settings if you don't mind the extra CPU.",
    ]),
    ("Getting the exact total", [
        "Open the freight elevator terminal, clear any filter or search, and scroll its list to the very bottom. "
        "The game logs the exact item count and the tracker uses it to confirm the scan is complete.",
    ]),
    ("Between scans", [
        "Items you move in or out of station storage, and things you buy at shops, are picked up from the game's "
        "log automatically, even for sessions when the tracker wasn't running.",
        "The log can't see freight elevator moves or which commodity you sold. The dashboard flags those so you "
        "can fix them by hand or rescan.",
        "A fresh scan always replaces earlier edits for that station, because a scan shows what's really there.",
        "If Excel has a CSV file open, the tracker can't update it. Close it and it updates next time.",
    ]),
]


# Pictures from the game for each section (files in sctracker/static/tips)
PICTURES = {
    "Before you scan": [
        ("backpack.jpg", "A bright backpack behind the tooltip makes it hard to read"),
        ("graphics.jpg", "Graphics settings: Chromatic Aberration 0, Film Grain off, QR code on"),
    ],
    "Starting a scan": [
        ("kiosk.jpg", "The storage kiosk: Stack, category filters, the tooltip and the page number"),
        ("filters.jpg", "Filtering by a whole category"),
    ],
    "Scanning quickly": [
        ("locked.jpg", "Locked (expired) items"),
    ],
    "At shops": [
        ("shop.jpg", "A shop terminal"),
    ],
    "Getting the exact total": [
        ("freight.jpg", "The freight elevator terminal"),
    ],
}


def as_markdown():
    out = []
    for head, items in TIPS:
        out.append(f"### {head}\n")
        out += [f"- {t}" for t in items]
        out.append("")
        for f, alt in PICTURES.get(head, []):
            out.append(f'<img src="sctracker/static/tips/{f}" width="640" alt="{alt}">\n')
    return "\n".join(out)
