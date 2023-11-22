from straders_sdk.client_postgres import SpaceTradersPostgresClient as SpaceTraders
from straders_sdk.models import Waypoint
from straders_sdk.utils import waypoint_slicer, try_execute_select
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
    if len(colocated_waypoints) > 1:
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
    ships_at_waypoint_sql = """select s.ship_symbol, ship_role, sfl.frame_symbol
, round((s.cargo_in_use::numeric/greatest(s.cargo_capacity,1))*100,2) as cargo_percentage
, s.cargo_capacity
from ships s 
join ship_nav sn on s.ship_symbol = sn.ship_symbol
join ship_frame_links sfl on sfl.ship_symbol = s.ship_symbol
where waypoint_symbol = %s
"""
    results = try_execute_select(
        client.connection, ships_at_waypoint_sql, (waypoint.symbol,)
    )
    return_obj["present_ships"] = []
    for result in results:
        # ship suffix is result 0 - the length of current_agent_symbol

        ship_suffix = result[0][len(client.current_agent_symbol) + 1 :]
        return_obj["present_ships"].append(
            {
                "ship_symbol": f"{result[0]}",
                "display_string": f"{ship_suffix}{map_role(result[1])}{map_frame(result[2])} {result[3]}%/{result[4]}",
            }
        )

    return return_obj


def query_ship(client: SpaceTraders, ship_symbol: str):
    return {}


def query_market(cliet: SpaceTraders, market_symbol: str):
    return {}


def map_role(role) -> str:
    roles = {
        "COMMAND": "👑",
        "EXCAVATOR": "⛏️",
        "HAULER": "🚛",
        "SATELLITE": "🛰️",
        "REFINERY": "⚙️",
    }
    return roles.get(role, role)


def map_frame(role) -> str:
    frames = {
        "FRAME_DRONE": "⛵",
        "FRAME_PROBE": "⛵",
        "FRAME_MINER": "🚤",
        "FRAME_LIGHT_FREIGHTER": "🚤",
        "FRAME_FRIGATE": "🚤",
        "FRAME_HEAVY_FREIGHTER": "⛴️",
    }
    return frames.get(role, role)
