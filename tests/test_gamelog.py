"""Game.log parsing, on made-up lines shaped like the real ones (no real player data)."""
from sctracker.gamelog import LogParser, cursor_value, strip_entity

P = "PlayerName"
LOC = "1000:Location:1234567890"


def feed(lines):
    p = LogParser()
    out = []
    for l in lines:
        out += p.feed(l)
    return p, out


def test_location_and_inventory_id():
    p, ev = feed([
        f"<2026-10-26T07:38:33.718Z> [Notice] <RequestLocationInventory> Player[{P}] requested inventory for Location[AsteroidClusterBase_Nyx_Social_Keeger_001] [Team]",
        f"<2026-10-26T07:38:33.718Z> [Notice] <Query Inventory> Request[22] Inventory[{LOC}] [Team]",
    ])
    assert p.location == "AsteroidClusterBase_Nyx_Social_Keeger_001"
    assert p.loc_ids[LOC] == "AsteroidClusterBase_Nyx_Social_Keeger_001"
    assert [e["kind"] for e in ev] == ["location", "loc_id"]


def test_move_out_counts_only_on_success():
    queued = (f"<2026-10-26T07:38:41.037Z> [Notice] <Inventory Mgmt Request Queued> Queued Request[24] Type[Move] "
              f"for '{P}' [1000] Source Inventory[{LOC}] Target Inventory[2000:Container:0]. "
              f"Source[behr_rifle_ballistic_03_mag] amount[31] rank[x]. Target[NULL] amount[0] rank[y]. "
              f"Item[NONE] action[None]. RequestInProgress[1] CurrentProcess[] [Team]")
    ok = f"<2026-10-26T07:38:41.978Z> [Notice] <Player Inventory Request Complete> Request[24] for '{P}' [1000] Type[Move] Result[Succeed] Item[0] CanLockQueue[Yes]. [Team]"
    bad = ok.replace("Succeed", "Failed")
    _, ev = feed([queued, ok])
    moves = [e for e in ev if e["kind"] == "move"]
    assert len(moves) == 1 and moves[0]["qty"] == -31 and moves[0]["item"] == "behr_rifle_ballistic_03_mag"
    _, ev = feed([queued, bad])
    assert not [e for e in ev if e["kind"] == "move"]


def test_store_uses_item_field():
    q = (f"<2026-10-03T00:16:48.723Z> [Notice] <Inventory Mgmt Request Queued> Queued Request[31] Type[Store] "
         f"for '{P}' [1000] Source Inventory[INVALID] Target Inventory[{LOC}]. Source[NULL] amount[0] . "
         f"Target[NULL] amount[0] . Item[behr_smg_ballistic_01_776718675003] action[None]. [Team]")
    done = f"<2026-10-03T00:16:49.000Z> [Notice] <Player Inventory Request Complete> Request[31] for '{P}' [1000] Type[Store] Result[Succeed] Item[0] CanLockQueue[Yes]. [Team]"
    _, ev = feed([q, done])
    m = [e for e in ev if e["kind"] == "move"][0]
    assert m["item"] == "behr_smg_ballistic_01" and m["qty"] == 1


def test_freight_total_ignores_filtered_lists():
    def line(more, end):
        return (f"<2026-10-27T03:00:00.000Z> [Notice] <InventoryManagement> Freight Inventory Grid InventoryDataRequest "
                f"Successful Inventory[{LOC}] Elapsed[0.5]. Page info: HasPreviousPage[0], HasNextPage[{more}], "
                f"StartCursor[MA==], EndCursor[{end}]")
    loc = f"<2026-10-27T02:59:00.000Z> [Notice] <RequestLocationInventory> Player[{P}] requested inventory for Location[X_Station]"
    p, _ = feed([loc, line(1, "MjUw"), line(0, "NDc0"), line(0, "NDg=")])   # 250 more..., 474 total, then a filter: 48
    assert p.freight_total["X_Station"][0] == 474


def test_buy_needs_success():
    buy = ("<2026-10-26T07:38:03.467Z> [Notice] <CEntityComponentShopUIProvider::SendShopBuyRequest> Sending SShopBuyRequest "
           "- playerId[1000] shopId[5] shopName[SCShop_WeaponsArmor_NyxSocial] kioskId[77] client_price[9083.000000] "
           "itemClassGUID[abc] itemName[behr_rifle_ballistic_03_mag] quantity[31]  [Team]")
    res = ("<2026-10-26T07:38:04.230Z> [Notice] <CEntityComponentShopUIProvider::RmShopFlowResponse> Received ShopFlowResponse "
           "- playerId[1000] shopId[5] shopName[SCShop_WeaponsArmor_NyxSocial] kioskId[77] kioskState[BuyRequestProcessing] "
           "result[Success] type[Buying] [Team]")
    _, ev = feed([buy, res])
    b = [e for e in ev if e["kind"] == "buy"][0]
    assert b["qty"] == 31 and b["shop"] == "SCShop_WeaponsArmor_NyxSocial"


def test_same_line_same_id():
    l = f"<2026-10-26T07:38:33.718Z> [Notice] <RequestLocationInventory> Player[{P}] requested inventory for Location[A_B]"
    assert feed([l])[1][0]["id"] == feed([l])[1][0]["id"]


def test_helpers():
    assert cursor_value("NDc0") == 474
    assert strip_entity("cds_core_01_901170999268") == "cds_core_01"
