"""The kiosk's category filters, and which item types belong to each.

The kiosk has ten filter buttons. When some are on, the list only shows
those categories, so a scan covers just them. To combine that with an older
full scan, the tracker needs to know which category each item type is in.
Types seen in a filtered scan are learned automatically; the keywords below
cover the rest.
"""

CATEGORIES = ["Armor", "Clothing", "Weapons", "Utility", "Ammo", "Vehicles", "Sustenance", "Container",
              "Other", "Missions"]

# Checked in order: ship weapons before personal weapons
KEYWORDS = [
    ("Vehicles", ["cooler", "power plant", "shield", "quantum", "cannon", "repeater", "gatling", "scattergun",
                  "missile", "torpedo", "rack", "turret", "mining module", "mining laser", "emp", "livery", "paint",
                  "jump module", "radar", "weapon mount", "countermeasure", "ordnance", "ship"]),
    ("Ammo", ["magazine", "battery", "ammo"]),
    ("Armor", ["armor", "armour", "undersuit", "helmet", "backpack", "flair"]),
    ("Clothing", ["shirt", "jacket", "hat", "glove", "pants", "legwear", "footwear", "shoes", "boots", "eyewear",
                  "glasses", "clothing", "headwear"]),
    ("Weapons", ["rifle", "pistol", "smg", "shotgun", "sniper", "lmg", "launcher", "knife", "bat", "melee",
                 "grenade", "throwable", "optic", "barrel", "underbarrel", "weapon attachment"]),
    ("Utility", ["utility", "medical", "medgel", "multi-tool", "multitool", "tractor", "cryptokey", "gadget",
                 "technology", "tool"]),
    ("Sustenance", ["food", "drink", "sustenance"]),
    ("Container", ["container", "commodity", "crate", "cargo", "canister", "box"]),
    ("Missions", ["mission"]),
]


def category_of(item_type, learned=None):
    if not item_type:
        return None
    t = item_type.lower()
    if learned and t in learned:
        return learned[t]
    for cat, words in KEYWORDS:
        if any(w in t for w in words):
            return cat
    return "Other"
