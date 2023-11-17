from straders_sdk.client_postgres import SpaceTradersPostgresClient as SpaceTraders
from straders_sdk.models import Waypoint
from straders_sdk.utils import waypoint_slicer
from datetime import datetime, timedelta


def query_waypoint(client: SpaceTraders, waypoint: str):
    return_obj = {}
    system_s = waypoint_slicer(waypoint)
    waypoint = client.waypoints_view_one(system_s, waypoint)
    waypoint: Waypoint
    return_obj["waypoint_symbol"] = waypoint.symbol
    return_obj["waypoint_type"] = waypoint.type
    return_obj["waypoint_traits"] = [t.symbol for t in waypoint.traits]
    return_obj["shipyard"] = waypoint.has_shipyard
    return_obj["jumpgate"] = waypoint.has_jump_gate()
    return_obj["market"] = waypoint.has_market

    colocated_waypoints = client.find_waypoints_by_coords(
        system_s, waypoint.x, waypoint.y
    )
    return_obj["co_located_waypoints"] = [w for w in colocated_waypoints]
    if waypoint.has_market:
        market_obj = []
        market = client.system_market(waypoint)
        time_checked = datetime.now()
        for item in market.listings:
            time_checked = min(item.recorded_ts, time_checked)
            market_obj.append(
                {
                    "trade_symbol": item.symbol,
                    "supply": item.supply,
                    "buy_price": item.purchase_price,
                    "sell_price": item.sell_price,
                    "depth": item.trade_volume,
                    "type": item.type,
                    "activity": item.activity,
                }
            )
        return_obj["market_items"] = market_obj
        return_obj["market_checked_ts"] = time_checked
    if waypoint.has_shipyard:
        shipyard_obj = []
        shipyard = client.system_shipyard(waypoint)
        for ship in shipyard.ships.values():
            shipyard_obj.append({"ship_symbol": ship.name, "cost": ship.purchase_price})

        return_obj["shipyard_types"] = shipyard_obj

    return_obj["present_ships"] = [
        "2A⛵⛏️ 65%/10",
        "2D⛵⛏️ 0%/10",
        "26⛵⛏️ 80%/10",
        "23⛵⛏️ 100%/10",
        "4A⛵⛏️ 0%/10",
    ]

    return return_obj
