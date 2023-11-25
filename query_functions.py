from straders_sdk.client_postgres import SpaceTradersPostgresClient as SpaceTraders
from straders_sdk.models import Waypoint
from straders_sdk.utils import waypoint_slicer, try_execute_select, waypoint_suffix
from datetime import datetime, timedelta


def query_waypoint(client: SpaceTraders, waypoint: str):
    return_obj = {}
    system_s = waypoint_slicer(waypoint)
    waypoint = client.waypoints_view_one(system_s, waypoint)
    waypoint: Waypoint
    return_obj["waypoint_symbol"] = waypoint.symbol
    return_obj["waypoint_suffix"] = waypoint_suffix(waypoint.symbol)
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
        exports = []
        imports = []
        exchanges = []
        for item in market.listings:
            time_checked = min(item.recorded_ts, time_checked)
            tmp_obj = {
                "trade_symbol": item.symbol,
                "supply": item.supply,
                "buy_price": item.purchase_price,
                "sell_price": item.sell_price,
                "depth": item.trade_volume,
                "type": item.type,
                "activity": item.activity,
            }
            if item.type == "EXPORT":
                exports.append(tmp_obj)
            elif item.type == "IMPORT":
                imports.append(tmp_obj)
            elif item.type == "EXCHANGE":
                exchanges.append(tmp_obj)

        market_obj += exports
        market_obj += imports
        market_obj += exchanges

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
    ship = client.ships_view_one(ship_symbol)

    return_obj = {
        "ship_symbol": ship_symbol,
        "ship_role": ship.role,
        "ship_frame": ship.frame.name,
    }
    return_obj["cur_fuel"] = ship.fuel_current
    return_obj["max_fuel"] = ship.fuel_capacity
    return_obj["cur_cargo"] = ship.cargo_units_used
    return_obj["max_cargo"] = ship.cargo_capacity
    return_obj["current_system"] = ship.nav.system_symbol
    return_obj["current_waypoint_suffix"] = waypoint_suffix(ship.nav.waypoint_symbol)
    mounts = [m.name for m in ship.mounts]
    modules = [m for m in ship.modules]
    return_obj["mounts"] = mounts
    return_obj["modules"] = modules

    return_obj["current_system"] = ship.nav.system_symbol
    return_obj["current_waypoint"] = ship.nav.waypoint_symbol

    return_obj["cargo"] = [
        {"name": ci.name, "units": ci.units} for ci in ship.cargo_inventory
    ]

    recent_behaviour_sql = """select 
  event_params ->> 'script_name' as most_recent_behaviour
, event_timestamp
, sb.behaviour_id as regular_behaviour
, sb.behaviour_params
from logging l left join ship_behaviours sb on l.ship_symbol = sb.ship_symbol
where l.ship_symbol = 'CTRI-U--1'
and event_name = 'BEGIN_BEHAVIOUR_SCRIPT'
order by event_timestamp desc 
limit 1
"""
    results = try_execute_select(client.connection, recent_behaviour_sql, ())
    if len(results) > 0:
        result = results[0]
        return_obj["most_recent_behaviour"] = result[0]
        return_obj["most_recent_behaviour_ts"] = result[1]
        return_obj["regular_behaviour"] = result[2]
        return_obj["regular_behaviour_params"] = result[3]

    return return_obj


def query_market(cliet: SpaceTraders, market_symbol: str):
    return {}


def query_system(st: SpaceTraders, system_symbol: str):
    syst = st.systems_view_one(system_symbol)
    wayps = st.waypoints_view(syst.symbol)
    waypoints = []
    min_x = 0
    min_y = 0
    max_x = 0
    max_y = 0

    for wayp_symbol, wayp in wayps.items():
        wayp: Waypoint
        if wayp.type == "MOON":
            continue
        waypoints.append(
            {
                "symbol": wayp_symbol,
                "type": wayp.type,
                "x": wayp.x,
                "y": wayp.y,
                "distance": (wayp.x**2 + wayp.y**2) ** 0.5,
            }
        )
        if wayp.x < min_x:
            min_x = wayp.x
        if wayp.y < min_y:
            min_y = wayp.y
        if wayp.x > max_x:
            max_x = wayp.x
        if wayp.y > max_y:
            max_y = wayp.y
    for wayp in waypoints:
        wayp["x"] -= min_x + (max_x / 2)
        wayp["y"] -= min_y + (max_y / 2)
    centre = {
        "x": -min_x - (max_x / 2),
        "y": -min_y - (max_y / 2),
        "symbol": syst.symbol,
    }
    return {"waypoints": waypoints, "centre": centre}


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
