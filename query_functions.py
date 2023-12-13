from straders_sdk.client_postgres import SpaceTradersPostgresClient as SpaceTraders
from straders_sdk.pathfinder import PathFinder
from straders_sdk.models import Waypoint
from straders_sdk.ship import Ship
from straders_sdk.utils import waypoint_slicer, try_execute_select, waypoint_suffix
from datetime import datetime, timedelta
from math import floor
from dataclasses import dataclass
import json


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


def query_all_exports(client: SpaceTraders, system_symbol: str):
    sql = """SELECT system_symbol
    , market_symbol
    , trade_symbol
    , supply
    , activity
    , purchase_price
    , sell_price
    , market_depth
    , units_sold_recently
    , requirements
	FROM public.export_overview
    where system_symbol = %s"""

    results = try_execute_select(client.connection, sql, (system_symbol,))
    exports = {}
    for e in results:
        ex = Export(e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[9] or [])
        if ex.trade_symbol not in exports:
            exports[ex.trade_symbol] = []
        exports[ex.trade_symbol].append(ex)

    extended_exports = {}
    for key, value in exports.items():
        extended_exports[key] = []
        for ex in value:
            requirements = get_all_export_requirements(ex.trade_symbol, exports)
            ex.requirements_txt = list(set(requirements))
            extended_exports[key].append(ex)

    return_obj = {
        "exports": [e.to_dict() for exes in extended_exports.values() for e in exes],
        "system_symbol": system_symbol,
    }
    return return_obj
    # turn this into json and return


def get_all_export_requirements(export_name: str, exports_map) -> list["Export"]:
    export = exports_map.get(export_name, None)
    if export is None or len(export) == 0:
        return []
    export = export[0]
    return_obj = export.requirements_txt
    for e in export.requirements_txt:
        return_obj += get_all_export_requirements(e, exports_map)
    return return_obj


class Export:
    def __init__(
        self,
        system_symbol: str,
        market_symbol: str,
        trade_symbol: str,
        supply: int,
        activity: str,
        purchase_price: int,
        sell_price: int,
        market_depth: int,
        units_sold_recently: int,
        requirements_txt: str,
    ):
        self.system_symbol = system_symbol
        self.market_symbol = market_symbol
        self.trade_symbol = trade_symbol
        self.supply = supply
        self.activity = activity
        self.purchase_price = purchase_price
        self.sell_price = sell_price
        self.market_depth = market_depth
        self.units_sold_recently = units_sold_recently
        self.requirements_txt = requirements_txt

    def to_dict(self):
        return {
            "system_symbol": self.system_symbol,
            "market_symbol": self.market_symbol,
            "market_suffix": waypoint_suffix(self.market_symbol),
            "trade_symbol": self.trade_symbol,
            "supply": self.supply,
            "activity": self.activity,
            "purchase_price": self.purchase_price,
            "sell_price": self.sell_price,
            "market_depth": self.market_depth,
            "units_sold_recently": self.units_sold_recently,
            "requirements_txt": self.requirements_txt,
        }


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
    return_obj["current_waypoint"] = ship.nav.waypoint_symbol

    return_obj["current_waypoint_suffix"] = waypoint_suffix(ship.nav.waypoint_symbol)
    mounts = [m.name for m in ship.mounts]
    modules = [m for m in ship.modules]
    return_obj["mounts"] = mounts
    return_obj["modules"] = modules

    return_obj["cargo"] = [
        {"name": ci.name, "units": ci.units} for ci in ship.cargo_inventory
    ]
    return_obj["travel_time"] = ship.nav.travel_time_remaining
    t = ship.nav.travel_time_remaining
    return_obj[
        "travel_time_fmt"
    ] = f"{floor(t/3600)}h {floor((t%3600)/60)}m {floor(t%60)}s"
    if ship.nav.status == "IN_TRANSIT":
        return_obj["origin"] = ship.nav.origin.symbol
        return_obj["origin_suffix"] = waypoint_suffix(ship.nav.origin.symbol)
        return_obj["destination"] = ship.nav.destination.symbol
        return_obj["destination_suffix"] = waypoint_suffix(ship.nav.destination.symbol)
        return_obj["distance"] = round(
            PathFinder().calc_distance_between(ship.nav.origin, ship.nav.destination), 2
        )
    return_obj["cooldown_time"] = ship.seconds_until_cooldown
    t = ship.seconds_until_cooldown
    return_obj[
        "cooldown_time_fmt"
    ] = f"{floor(t/3600)}h {floor((t%3600)/60)}m {floor(t%60)}s"

    cargo = {}
    for ci in ship.cargo_inventory:
        cargo[ci.symbol] = ci.units

    if len(cargo) > 0:
        return_obj["cargo"] = cargo

    recent_behaviour_sql = """select 
  event_params ->> 'script_name' as most_recent_behaviour
, event_timestamp
, sb.behaviour_id as regular_behaviour
, sb.behaviour_params
, session_id
from logging l left join ship_behaviours sb on l.ship_symbol = sb.ship_symbol
where l.ship_symbol = %s
and event_name = 'BEGIN_BEHAVIOUR_SCRIPT'
order by event_timestamp desc 
limit 1
"""
    results = try_execute_select(
        client.connection, recent_behaviour_sql, (ship_symbol,)
    )
    if len(results) > 0:
        result = results[0]
        return_obj["most_recent_behaviour"] = result[0]
        return_obj["most_recent_behaviour_ts"] = result[1].strftime(r"%H:%M:%S")
        return_obj["regular_behaviour"] = result[2]
        return_obj["regular_behaviour_params"] = result[3]
        return_obj["session_id"] = result[4]
    incomplete_tasks_and_behaviours_sql = """
    select behaviour_id, priority, behaviour_params from ship_Tasks where claimed_by = %s and completed != True
    union
    select behaviour_id, 99, behaviour_params from ship_behaviours where ship_symbol = %s"""
    results = try_execute_select(
        client.connection,
        incomplete_tasks_and_behaviours_sql,
        (ship_symbol, ship_symbol),
    )
    if len(results) > 0 and results[0][0] is not None:
        return_obj["incomplete_tasks_and_behaviours"] = results
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


def query_session(st: SpaceTraders, session_id):
    sql = """
select * from logging where session_id = %s
order by event_name = 'BEGIN_BEHAVIOUR_SCRIPT', event_Timestamp desc  
limit 100;
"""
    session_id = session_id[5:]
    results = try_execute_select(st.connection, sql, (session_id,))
    response = []
    header = _try_parse_begin_behaviour_script(results[-1][3], results[-1][9])
    for log in results:
        time = log[1]
        if time.date() == datetime.now().date():
            time_fmt = time.strftime(r"%H:%M:%S")
        else:
            time_fmt = time.strftime(r"%Y-%m-%d %H:%M:%S")
        response.append(
            {
                "time": time_fmt,
                "name": log[0],
                "status_code": log[7],
                "error_code": log[8],
                "duration": log[10],
                "params": log[9],
            }
        )

    return {"header": header, "events": response}


def _try_parse_begin_behaviour_script(ship_name, event_params: dict):
    script_name = event_params.get("script_name", None)
    response_lines = []
    if not script_name:
        response_lines.append(
            f"{ship_name} is doing an unknown behaviour! here are the params {json.dumps(event_params, indent=2)}"
        )
    if script_name == "MONITOR_SPECIFIC_WAYPOINT":
        response_lines.append(
            f"{ship_name} is monitoring a specific waypoint for market and shipyard changes"
        )
        pass
    elif script_name == "MONITOR_CHEAPEST_SHIPYARD_PRICE":
        response_lines.append(
            f"{ship_name} is positioning itself at the cheapest shipyard for a given ship"
        )
        pass
    elif script_name == "SINGLE_STABLE_TRADE":
        response_lines.append(
            f"{ship_name} is doing free trading of whatever it finds in-system"
        )
        pass
    elif script_name == "CONSTRUCT_JUMPGATE":
        response_lines.append(f"{ship_name} is getting inexpensive a jumpgate")
    elif script_name == "EXTRACT_AND_SELL":
        response_lines.append(f"{ship_name} is extracting and taking it away to sell")
        pass
    elif script_name == "SCAN_THREAD":
        response_lines.append(f"{ship_name} is scanning everything in the galaxy")
        pass
    elif script_name == "MANAGE_SPECIFIC_EXPORT":
        if "market_wp" in event_params:
            response_lines.append(
                f"{ship_name} is managing {event_params.get('target_tradegood', 'UNKNOWN')} at {event_params.get('market_wp', 'UNKNOWN')}."
            )

        else:
            response_lines.append(
                f"{ship_name} is managing {event_params.get('target_tradegood', 'UNKNOWN')}, it will do so at the first market it finds that exports it."
            )
        response_lines.append(
            "If the market data is old, the ship will travel to the market and update it."
        )
        response_lines.append(
            "If supply is not SCARCE or LIMITED (which means MODERATE, HIGH, ABUNDANT) then it will try and sell the export."
        )
        response_lines.append(
            f" if the selected export is RESTRICTED, it will find required imports that are profitable (any %) and bring them to the exporting market, to enable the market to grow."
        )

    elif script_name == "SIPHON_AND_CHILL":
        response_lines.append(
            f"{ship_name} is siphoning and then waiting till someone takes away its cargo"
        )
        pass
    elif script_name == "TAKE_FROM_EXTRACTORS_AND_GO_SELL_9":
        cargo_to_receive = event_params.get("cargo_to_receive", "UNKNOWN")
        source_wp = event_params.get("asteroid_wp", "UNKNOWN")
        market_wp = event_params.get("market_wp", "UNKNOWN")

        if market_wp and source_wp:
            response_lines.append(
                f"{ship_name} is going to {source_wp} to take {cargo_to_receive} from any idling extractors, and is selling it at {market_wp}."
            )
        elif market_wp:
            response_lines.append(
                f"{ship_name} is going to find idling extractors with {cargo_to_receive}, take it, then selling at {market_wp}."
            )
        elif source_wp:
            response_lines.append(
                f"{ship_name} is going to {source_wp} to take {cargo_to_receive} from any idling extractors, and is selling it at the best market it finds that imports it."
            )
        else:
            response_lines.append(
                f"{ship_name} is finding extractors with {event_params.get('cargo_to_receive', 'UNKNOWN')}, and is selling it "
            )
    elif script_name == "BUY_AND_DELIVER_OR_SELL":
        buy_shorthand = event_params.get("buy_wp", "the best place it can find")
        sell_shorthand = event_params.get("sell_wp", "UNKNOWN")
        fulfill_shorthand = event_params.get("fulfil_wp", None)
        if (
            "buy_wp" in event_params
            and "sell_wp" in event_params
            and waypoint_slicer(buy_shorthand) == waypoint_slicer(sell_shorthand)
        ):
            buy_shorthand = waypoint_suffix(buy_shorthand)
            sell_shorthand = waypoint_suffix(sell_shorthand)
        if (
            "buy_wp" in event_params and "fulfil_wp" in event_params
        ) and waypoint_slicer(buy_shorthand) == waypoint_slicer(fulfill_shorthand):
            buy_shorthand = waypoint_suffix(buy_shorthand)
            fulfill_shorthand = waypoint_suffix(fulfill_shorthand)

        response_lines.append(
            f"{ship_name} is buying {event_params.get('quantity', 1)} {event_params.get('tradegood', 'UNKNOWN')} at {buy_shorthand} and {'delivering to' if fulfill_shorthand else 'selling at'} {fulfill_shorthand or sell_shorthand}."
        )
        if "safety_profit_threshold" in event_params:
            response_text = f"The ship will abort if projected profit is less than {event_params.get('safety_profit_threshold', 0)} when purchasing."
            response_lines.append(response_text)

        pass
    elif script_name == "EXTRACT_AND_CHILL":
        response_lines.append(
            f"{ship_name} is extracting and then waiting till someone takes away its cargo"
        )

    else:
        response_lines.append(
            f"{ship_name} is doing unknown behaviour {script_name}! here are the params {json.dumps(event_params, indent=2)}"
        )

    if "task_hash" in event_params:
        response_lines.append(f"This is a specific task, not a regular behaviour. ")

    if "priority" in event_params:
        response_lines.append(f"Priority: {event_params.get('priority', 'UNKNOWN')}.")
    return response_lines


def query_all_transactions(st: SpaceTraders):
    sql = """
SELECT first_transaction_in_session, ship_symbol, trade_symbol, units, average_sell_price, average_purchase_price, net_change, purchase_wp, sell_wp, session_id
	FROM public.transaction_overview
    where ship_symbol ilike %s
    """
    results = try_execute_select(st.connection, sql, (f"{st.current_agent_symbol}%",))
    transactions = []
    for result in results:
        start_time: datetime = result[0]
        if start_time.date() == datetime.now().date():
            start_time_fmt = start_time.strftime(r"%H:%M:%S")
        else:
            start_time_fmt = start_time.strftime(r"%Y-%m-%d %H:%M:%S")
        transactions.append(
            {
                "start_time": start_time_fmt,
                "ship_symbol": result[1],
                "ship_suffix": waypoint_suffix(result[1]),
                "trade_symbol": result[2],
                "units": result[3],
                "average_sell_price": result[4],
                "average_purchase_price": result[5],
                "net_change": result[6] or 0,
                "purchase_wp": result[7] or "",
                "purchase_wp_suffix": waypoint_suffix(result[7]) if result[7] else "",
                "sell_wp": result[8] or "",
                "sell_wp_suffix": waypoint_suffix(result[8]) if result[8] else "",
                "session_id": result[9],
                "session_id_trunc": result[9][0:5],
            }
        )
    return {"transactions": transactions}


def query_all_ships(
    st: SpaceTraders, partition_by_role: bool = True, partition_by_waypoint: bool = True
):
    # we need a ship's name, fuel, cargo, location / nav details, and behaviour. let's block em into rectangles. maybe 5 in a large?
    sql = """with data as (
select ship_symbol, max(event_timestamp) as timestamp
from logging l 
where event_name = 'BEGIN_BEHAVIOUR_SCRIPT'
and event_timestamp >= now() - interval '1 day'
group by 1 
)
select l.ship_symbol, event_params ->> 'script_name' as script_name from logging l join data d on l.event_timestamp = d.timestamp and d.ship_symbol = l.ship_symbol
order by 1 """
    results = try_execute_select(st.connection, sql, ())
    behaviours = {r[0]: r[1] for r in results}
    if partition_by_role:
        all_ships = st.ships_view().values()

        sorted_ships = {
            "COMMAND": [
                _summarise_ship(s, behaviours) for s in all_ships if s.role == "COMMAND"
            ],
            "TRANSPORT": [
                _summarise_ship(s, behaviours)
                for s in all_ships
                if s.role == "TRANSPORT"
            ],
            "SATELLITE": [
                _summarise_ship(s, behaviours)
                for s in all_ships
                if s.role == "SATELLITE"
            ],
            "HAULER": [
                _summarise_ship(s, behaviours) for s in all_ships if s.role == "HAULER"
            ],
            "REFINERY": [
                _summarise_ship(s, behaviours)
                for s in all_ships
                if s.role == "REFINERY"
            ],
            "EXTRACTOR": [
                _summarise_ship(s, behaviours)
                for s in all_ships
                if s.role == "EXCAVATOR" and s.can_extract
            ],
            "SIPHONER": [
                _summarise_ship(s, behaviours)
                for s in all_ships
                if s.role == "EXCAVATOR" and s.can_siphon
            ],
        }
    elif partition_by_waypoint:
        keys, all_ships = st.ships_view().items()
        sorted_ships = {}
        for ship in all_ships:
            ship: Ship
            sorted_ships[ship.nav.waypoint_symbol] = _summarise_ship(ship, behaviours)

    return {"ships": sorted_ships}


def query_one_type_of_ships(st: SpaceTraders, role: str):
    sql = """with data as (
select ship_symbol, max(event_timestamp) as timestamp
from logging l 
where event_name = 'BEGIN_BEHAVIOUR_SCRIPT'
and event_timestamp >= now() - interval '1 day'
group by 1 
)
select l.ship_symbol, event_params ->> 'script_name' as script_name from logging l join data d on l.event_timestamp = d.timestamp and d.ship_symbol = l.ship_symbol
order by 1 """
    results = try_execute_select(st.connection, sql, ())
    behaviours = {r[0]: r[1] for r in results}
    all_ships = st.ships_view().values()
    if role == "COMMAND":
        sorted_ships = {
            "COMMAND": [
                _summarise_ship(s, behaviours) for s in all_ships if s.role == "COMMAND"
            ]
        }
    elif role == "TRANSPORT":
        sorted_ships = {
            "TRANSPORT": [
                _summarise_ship(s, behaviours)
                for s in all_ships
                if s.role == "TRANSPORT"
            ]
        }
    elif role == "SATELLITE":
        sorted_ships = {
            "SATELLITE": [
                _summarise_ship(s, behaviours)
                for s in all_ships
                if s.role == "SATELLITE"
            ]
        }
    elif role == "HAULER":
        sorted_ships = {
            "HAULER": [
                _summarise_ship(s, behaviours) for s in all_ships if s.role == "HAULER"
            ]
        }
    elif role == "REFINERY":
        sorted_ships = {
            "REFINERY": [
                _summarise_ship(s, behaviours)
                for s in all_ships
                if s.role == "REFINERY"
            ]
        }
    elif role == "EXTRACTOR":
        sorted_ships = {
            "EXTRACTOR": [
                _summarise_ship(s, behaviours)
                for s in all_ships
                if s.role == "EXCAVATOR" and s.can_extract
            ]
        }
    elif role == "SIPHONER":
        sorted_ships = {
            "SIPHONER": [
                _summarise_ship(s, behaviours)
                for s in all_ships
                if s.role == "EXCAVATOR" and s.can_siphon
            ]
        }

        keys, all_ships = st.ships_view().items()
        sorted_ships = {}
        for ship in all_ships:
            ship: Ship
            sorted_ships[ship.nav.waypoint_symbol] = _summarise_ship(ship, behaviours)

    return {"ships": sorted_ships}


def _summarise_ship(ship: Ship, most_recent_behaviours: dict) -> dict:
    most_recent_behaviour = most_recent_behaviours.get(ship.name, None)
    if ship.nav.status == "IN_TRANSIT":
        if waypoint_slicer(ship.nav.origin.symbol) == waypoint_slicer(
            ship.nav.destination.symbol
        ):
            nav_string = f"🌍{waypoint_suffix(ship.nav.origin.symbol)} -> 🌎{waypoint_suffix(ship.nav.destination.symbol)}"
        else:
            nav_string = f"🌍{ship.nav.origin.symbol} -> 🌎{ship.nav.destination.symbol}"
    else:
        nav_string = f"🌏{waypoint_suffix(ship.nav.waypoint_symbol)}"
    return {
        "symbol": waypoint_suffix(ship.name),
        "full_symbol": ship.name,
        "role": ship.role,
        "frame": ship.frame.name,
        "frame_emoji": map_frame(ship.frame.symbol),
        "role_emoji": map_role(ship.role),
        "cargo": ship.cargo_units_used,
        "cargo_max": ship.cargo_capacity,
        "fuel": ship.fuel_current,
        "fuel_max": ship.fuel_capacity,
        "nav": nav_string,
        "nav_status": ship.nav.status,
        "current_waypoint": ship.nav.waypoint_symbol,
        "behaviour": most_recent_behaviour,
    }


def map_role(role) -> str:
    roles = {
        "COMMAND": "👑",
        "EXCAVATOR": "⛏️",
        "HAULER": "🚛",
        "TRANSPORT": "🚚",
        "SATELLITE": "🛰️",
        "REFINERY": "⚙️",
    }
    return roles.get(role, role)


def map_frame(role) -> str:
    frames = {
        "FRAME_DRONE": "⛵",
        "FRAME_PROBE": "⛵",
        "FRAME_SHUTTLE": "⛵",
        "FRAME_MINER": "🚤",
        "FRAME_LIGHT_FREIGHTER": "🚤",
        "FRAME_FRIGATE": "🚤",
        "FRAME_HEAVY_FREIGHTER": "⛴️",
    }
    return frames.get(role, role)
