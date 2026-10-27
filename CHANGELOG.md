# Changelog

## 3.0 (first public release)

- Dashboard in your browser (local only): search, filters, station list with data age, item panel with
  notes, tags and hand-recorded changes, wish lists, tips, useful links, settings.
- Stations stay current between scans from Game.log: moves in and out of storage, shop purchases.
  Commodity sales and freight elevator changes are flagged for you to sort out.
- Proper station names from the game's own text (e.g. People's Service Station Alpha, Pyro Gateway (Nyx)),
  with renaming.
- "Registered To You" items flagged; expired items counted but listed separately.
- Prices, best sell and cheapest buy spots, stats and component comparisons from api.star-citizen.wiki.
- inventory.json with a documented format; AI assistant instructions and a Claude skill.
- Calibration for screens that aren't 16:9; softer tile detection at 1080p.
- Game version recorded per scan; renamed items follow the game's text; fresh start after a wipe.
- Share file for orgs and friends (no names, ids or history).
- Ships tab: add your ships from the full ship list, see every part slot with the stock part, plan your fit
  from the parts that fit each slot (stats, cheapest price, what you already own), and send parts to your
  wish list.
- Wish list: search items as you type, and see how to get each one: where to buy it, how to craft it and which
  contracts give the blueprint, which ships come with it fitted, and what you already have where.
- Kiosk category filters: scan just the categories you switch on; the result slots into your last full scan.
- Shop helper: press Insert at a shop terminal and the overlay labels items you already own.
- Station names are picked from the game's own place names.
- Data now lives in the `data` folder; v2 data is copied across on first run.
- Setup makes shortcuts with icons (SC Inventory Tracker, SC Inventory Dashboard and two more), and can add
  them to the desktop and Start menu. The batch files behind them are in the `launchers` folder.
- New dashboard look, and a design preview with sample data in the `design` folder.

## 2.3

- Kiosk scanning with run fill-in, repeat detection, Stack button starts a scan, freight elevator totals.
