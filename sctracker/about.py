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
     "New players get bonus UEC when they sign up with a referral code."),
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
