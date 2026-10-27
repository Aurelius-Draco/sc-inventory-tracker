# <img src="sctracker/assets/tracker.png" width="40" align="top" alt=""> SC Inventory Tracker

Keeps track of what you've left in station storage around the Star Citizen
verse. Scan a station's storage kiosk once, and the tracker keeps that station
up to date from the game's own log as you move things in and out, buy things
and sell them. Everything shows up in a dashboard in your browser: search
across every station, see what changed, what things are worth and where to
sell them, and keep wish lists for ship builds and loot.

It runs on your PC only and never touches the game itself.

## What it does

- **Reads the storage kiosk as you hover.** Rest the mouse on each item and the
  tracker reads the tooltip (name, type, size, grade, class), matches it to
  the game's own item names, and marks the tile as done on an overlay. For a
  run of identical items you only hover the first and last.
- **Knows exactly how many items are there** from the freight elevator count
  in Game.log, so you know when a scan is complete.
- **Keeps stations current between scans.** The game logs every move in and
  out of station storage and every shop purchase, with the item and quantity.
  The tracker reads those logs, including sessions when it wasn't running.
- **Dashboard** (runs locally at http://127.0.0.1:8765): search, filters,
  totals per station, how old each station's data is, notes and tags, changes
  you record by hand ("sold 40 gold"), wish lists, best sell spots and
  cheapest buy spots with the date each price was reported, and side by side
  comparisons for ship components.
- **Ships:** add the ships you fly from the full ship list, see each part slot
  with its stock part, plan your fit from everything that fits (stats, cheapest
  price, what you already own), and send the parts you want to your wish list.
- **Wish lists that tell you how to get things:** where to buy an item, how to
  craft it and which contracts give the blueprint, which ships come with it
  fitted, and how many you already have and where.
- **Shop helper:** press Insert at a shop terminal and the overlay labels the
  items on screen that you already have in storage.
- **Category filters:** switch on kiosk filters (Weapons, Vehicles...) before
  you scan to cover just those, and the result slots into your last full scan.
- **Files you can use anywhere:** `inventory.json` (documented in
  [docs/inventory-format.md](docs/inventory-format.md)), plus CSV files for Excel.
- **AI ready:** [ai/instructions.md](ai/instructions.md) lets any AI assistant
  read your inventory and help sort keep/sell/bin, plan pickups, or check an
  Erkul loadout against what you already own.

## Is it safe to use?

{RULES}

It works the same way as other community tools that read Game.log or the
screen. It doesn't automate anything: you do the hovering.

## What you need

- Windows 10 or 11
- Star Citizen in **borderless windowed** mode
- Python 3.12 or 3.13 (setup tells you how to get it if it's missing)
- Any 16:9 screen should work as is. It's been used at 4K and checked with
  screenshots scaled to 1440p and 1080p; reports from real 1440p and 1080p
  screens are welcome. Ultrawide and other shapes need a one-minute
  calibration: `tracker.py --calibrate`.

Linux: the dashboard and log tracking are plain Python and should work, but
reading the kiosk screen isn't supported yet (see the roadmap).

## Install

1. Download the latest release from
   [Releases](https://github.com/Aurelius-Draco/sc-inventory-tracker/releases)
   (or Code, then Download ZIP) and unzip it anywhere, for example next to
   your StarCitizen folder.
2. Double-click **Setup.bat**. It creates a private Python environment in the
   folder, downloads the text reader (about 100 MB) and makes shortcuts with
   icons. Say Y if you also want them on the desktop and in the Start menu.
   If you move the folder later, run Setup.bat again to fix the shortcuts.
3. If your game isn't in a standard place, open `data\config.json` after the
   first run and set `game_dir` to your `StarCitizen\LIVE` folder.

## Use

**Scanning a station:** start **SC Inventory Tracker**, open the storage kiosk in game and
press its **Stack** button. That starts a fresh scan. Hover the items, page by
page. Green dots are done, blue dots were filled in, amber outlines still need
a hover. A chime means a page is complete. Ctrl+C in the tracker window stops
it and prints anything still missing.

**Exact total:** open the freight elevator terminal, clear filters and
scroll its list to the bottom. The tracker takes the exact count from the log.

**Looking things up:** open **SC Inventory Dashboard** (or just leave the
tracker running: the dashboard runs alongside it).

**Other shortcuts:** *SC Inventory Tracker (no overlay)* skips the on-screen
markers if your PC is short on power, and *SC Inventory Screenshot Reader*
reads kiosk screenshots you took in game. The batch files behind every
shortcut are in the `launchers` folder.

**From the command line** (handy for AI assistants with a shell):

```
tracker.py --where "Ripper"                        which stations hold it
tracker.py --adjust "Alpha" "Gold" -40 --note "sold at Levski"
tracker.py --rename-station "Kaboos" "QV Kaboos"
tracker.py --export                                rewrite the files in data\
tracker.py --calibrate                             fit a non-16:9 screen
tracker.py --help
```

## Tips for good scans

{TIPS}

## Files

Everything the tracker writes lives in the `data` folder:

| file | what's in it |
|---|---|
| `inventory.json` | everything, for other tools and AI assistants |
| `summary.csv` | one row per item per station |
| `inventory.csv` | every kiosk tile from each station's last scan |
| `changes.csv`, `expired.csv` | changes since each scan, and locked items |
| `inventory.db` | the full history (SQLite) |
| `config.json` | settings |
| `locations.json` | your own names for stations, if you rename any |

## Useful sites

{LINKS}

## Station names

The game's log uses internal ids for places. The tracker turns them into the
names you know using the game's own text, plus a few rules. If a station shows
up wrong, rename it in the dashboard, and please open an issue with the id and
the right name so everyone gets the fix.

## When a patch breaks it

Game updates can move the kiosk around or change its text. If scans stop
working after a patch, open an issue with your screen size, the game version
and a cropped screenshot of the kiosk (crop out chat so other players' names
aren't shown).

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md).

## About

{ABOUT}

## Licence

MIT, see [LICENSE](LICENSE). Third-party parts are listed in
[THIRD_PARTY.md](THIRD_PARTY.md).

Not affiliated with or endorsed by Cloud Imperium Games. Star Citizen is a
trademark of Cloud Imperium Rights LLC. The tracker never ships any game
files: it reads your own copy of the game's text on your PC.
