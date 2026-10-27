# inventory.json format

The tracker writes `data\inventory.json` every time something changes. It is
the stable way to build on the tracker: dashboards, Discord bots, spreadsheets
or an AI assistant. The `format` field changes if anything breaks
compatibility.

```
format        "sc-inventory-tracker/1"
generated     when the file was written (UTC, ISO 8601)
game_version  the game version from the newest Game.log, e.g. "4.10.197.2878"
stations      one entry per station with storage you've scanned or used
items         one entry per item per station
changes       what changed since each station's last scan, newest first
needs_you     log entries the tracker couldn't place by itself
wishlist      your wish lists
```

There is no player name, account id or anything personal in this file.

## stations[]

| field | meaning |
|---|---|
| `key` | the game's id for the location, e.g. `AsteroidClusterBase_Nyx_Social_Keeger_001` |
| `name` | station name, e.g. "People's Service Station Alpha" |
| `system` | Stanton, Pyro, Nyx... |
| `name_source` | `game` (game text), `rule`, `guess` or `you` (renamed by the user) |
| `scan` | the scan in use, or `null` if never scanned (see below) |
| `items`, `qty` | number of different items, and total quantity |
| `expired` | items locked as expired (not counted in `qty`) |
| `changes` | changes since the scan |
| `untracked_changes` | reserved; always 0 for now (see the roadmap) |
| `age_days` | days since the scan |
| `value` | rough value at best known sell prices (aUEC), when item data is on |

`scan`: `last` (unix time), `complete` (all tiles identified and, where known,
matched against the freight elevator count), `identified`, `total`, `pages`,
`build` (game version at the time), `before_patch` (scanned on an older game
version), `repeat_warning` (the kiosk listed some items twice), `newer_partial`
(a newer scan was started but not finished).

## items[]

| field | meaning |
|---|---|
| `location_key`, `location`, `system` | where it is |
| `name` | display name from the player's game text (StarStrings names if installed, e.g. "Mil/3/C Mercury") |
| `id` | the game's item id (lower case), e.g. `cool_aegs_s03_mercury`. The same id the game log and api.star-citizen.wiki use. May be null for odd items |
| `qty` | how many now: `scanned_qty` + `log_change` + `your_change` |
| `scanned_qty` | count at the last scan (null if it arrived after the scan) |
| `log_change` | net change from the game log since the scan (moves, purchases) |
| `your_change` | net change entered by hand since the scan |
| `changed` | true if either change is non-zero |
| `expired` | how many are locked as expired |
| `registered` | how many show "Registered To You" |
| `tiles` | kiosk tiles it took up |
| `item_type`, `manufacturer`, `size`, `grade`, `item_class` | from the in-game tooltip (or item data). `item_class` is Military, Civilian, Stealth, Industrial or Competition |
| `note`, `tags` | the user's own note and tags |
| `also_at` | other stations holding the same item |
| `last_change` | unix time of the last change |

With item data on (default), items may also have: `value` (aUEC at the best
sell price), `unit_sell`, `sell_spots` and `buy_spots` (up to 5 each:
`terminal`, `place`, `system`, `buy`, `sell`, `date` reported), `craftable`,
`stats` (`coolant`, `power`, `power_use`, `ir`, `em`, `health`, `shield_hp`,
`mass` where they apply), `wiki_type`, `wiki_url`, and for ship components
`compare`: other parts of the same type and size with their main stat, IR,
EM and cheapest buy price.

Prices come from UEX via api.star-citizen.wiki and are reported by players.
Always look at the `date`.

## changes[]

`ts`, `location_key`, `location`, `item`, `delta` (+ in, - out), `source`
(`log` or `you`), `what` (e.g. "moved", "stored", "taken/equipped",
"bought at Weapons Armor Nyx Social", or the user's note).

## wishlist[]

`list` (e.g. "Centaurus refit"), `name`, `item_id`, `qty` wanted, `owned`,
`need`, `where` (stations and quantities), `note`, and when known
`buy_spots` and `craftable`.

## Other files in data\

- `summary.csv`: one row per item per station (items with a quantity; magazines and batteries left out by default)
- `inventory.csv`: every kiosk tile from each station's scan
- `expired.csv`, `changes.csv`
- `inventory.db`: everything, including history (SQLite)
