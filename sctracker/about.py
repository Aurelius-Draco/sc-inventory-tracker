"""Who made the tracker, and the ground rules it keeps. Shown on the About tab and in the README."""

AUTHOR = {
    "name": "Aurelius_Draco",
    "handle": "",            # same as name; kept for anyone forking with a different in-game name
    "org": "",
    "repo": "https://github.com/Aurelius-Draco/sc-inventory-tracker",
    "picture": "aurelius-draco.jpg",   # in sctracker/static/img
}

# Shown on the About tab and in the README: (link text, address, note)
LINKS = [
    ("My citizen page on RSI", "https://robertsspaceindustries.com/en/citizens/Aurelius_Draco",
     "Add me as a friend or send me a message in game."),
    ("New to Star Citizen? Sign up with my referral code STAR-VD9W-346V",
     "https://www.robertsspaceindustries.com/enlist?referral=STAR-VD9W-346V",
     "New players get 50,000 UEC to start with when they sign up with a referral code."),
]

# Ships on my wish list: (ship, maker, RSI store page, why)
WISHLIST_INTRO = ("Nobody has to get me anything. But if you're ever feeling generous, these are the ships I'd love to "
                  "fly. Message me on my RSI page first so we can sort out the gift.")
WISHLIST = [
    ("Idris-P", "Aegis Dynamics", "https://robertsspaceindustries.com/pledge/ships/aegis-idris/Idris-P",
     "A frigate of my own. Dream big."),
    ("Polaris", "Roberts Space Industries", "https://robertsspaceindustries.com/pledge/ships/polaris/Polaris",
     "A corvette with torpedoes and its own hangar."),
    ("Perseus", "Roberts Space Industries", "https://robertsspaceindustries.com/pledge/ships/perseus/Perseus",
     "Huge turret cannons on a gunship hull."),
    ("890 Jump", "Origin Jumpworks", "https://robertsspaceindustries.com/pledge/ships/890-jump/890-Jump",
     "The luxury yacht. Hauling gold in style."),
    ("Hammerhead", "Aegis Dynamics", "https://robertsspaceindustries.com/pledge/ships/hammerhead/Hammerhead",
     "Turrets on every side."),
    ("Ironclad Assault", "Drake Interplanetary",
     "https://robertsspaceindustries.com/pledge/ships/ironclad/Ironclad-Assault",
     "An armoured hauler that hits back."),
    ("Reclaimer", "Aegis Dynamics", "https://robertsspaceindustries.com/pledge/ships/reclaimer/Reclaimer",
     "Salvage my own construction materials."),
    ("600i Explorer", "Origin Jumpworks", "https://robertsspaceindustries.com/pledge/ships/600i/600i-Explorer",
     "The comfortable way to see the verse."),
    ("Paladin", "Anvil Aerospace", "https://robertsspaceindustries.com/pledge/ships/paladin/Paladin",
     "A proper heavy gunship."),
    ("Corsair", "Drake Interplanetary", "https://robertsspaceindustries.com/pledge/ships/drake-corsair/Corsair",
     "Guns everywhere, built for the frontier."),
]

MESSAGE = [
    "I built this to keep track of what I'd left at stations around the verse, and it turned out useful "
    "enough to share. It's free and always will be.",
    "The only thing I ask in return: if you see me in game or in chat, say hi, and if you're running team "
    "gameplay, invite me along.",
]

RULES = [
    "It only reads your screen, Game.log and the game's text file. It never touches the game's memory or "
    "network traffic, and never sends mouse or keyboard input.",
    "Nothing about you leaves your PC. The only network use is fetching public item data and prices from "
    "api.star-citizen.wiki, by item id, and you can turn that off in Settings.",
    "The dashboard only answers this PC (127.0.0.1).",
    "Not affiliated with or endorsed by Cloud Imperium Games. Star Citizen is a trademark of Cloud Imperium "
    "Rights LLC.",
]
