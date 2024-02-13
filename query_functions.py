from straders_sdk.client_postgres import SpaceTradersPostgresClient as SpaceTraders
from straders_sdk.pathfinder import PathFinder
from straders_sdk.models import Waypoint
from straders_sdk.ship import Ship
from straders_sdk.utils import (
    waypoint_slicer,
    try_execute_select,
    try_execute_upsert,
    waypoint_suffix,
)
from datetime import datetime, timedelta
from math import floor
from dataclasses import dataclass
import json
import threading


def query_waypoint(client: SpaceTraders, waypoint: str):
    return_obj = {}
    system_s = waypoint_slicer(waypoint)
    waypoint = client.waypoints_view_one(waypoint)
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
        ships_at_waypoint_sql, (waypoint.symbol,), client.connection
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


def display_ship_controls(client, string):
    return_obj = query_ship(client, string)
    ship = client.ships_view_one(string)
    ship: Ship

    #
    # prices for cargo in the ship
    #
    price_sql = """
select mp.trade_symbol, export_price, import_price from ship_cargo sc join market_prices mp on sc.trade_symbol = mp.trade_symbol
where ship_symbol = %s"""

    results = try_execute_select(price_sql, (ship.name,), client.connection)

    #
    # relevant tradegood stuff
    #
    return_obj["tradegood_prices"] = {
        r[0]: {"export_price": int(r[1] or -1), "import_price": int(r[2] or -1)}
        for r in results
    } or {}
    return_obj["market_data"] = {}
    market_data_sql = """
select "market_symbol",	mtl."trade_symbol",	"supply",	"purchase_price",	"sell_price",	"last_updated",	"market_depth",	mtl."type",	"activity"
from market_tradegood_listings mtl 
join waypoints w on mtl.market_Symbol = w.waypoint_symbol
join ship_cargo sc on sc.trade_symbol = mtl.trade_symbol
where sc.ship_symbol = %s and w.system_symbol = %s
order by type, market_symbol """

    market_data = try_execute_select(
        market_data_sql, (ship.name, ship.nav.system_symbol), client.connection
    )

    for m in market_data:
        if m[1] not in return_obj["market_data"]:
            return_obj["market_data"][m[1]] = []
        market_data = {
            "market_symbol": m[0],
            "supply": m[2],
            "last_updated": m[5],
            "market_depth": m[6],
            "type": m[7],
        }
        if m[7] in ("EXPORT", "EXCHANGE"):
            market_data["purchase_price"] = m[3]
        if m[7] in ("IMPORT", "EXCHANGE"):
            market_data["sell_price"] = m[4]
        if m[7] != "EXCHANGE":
            market_data["activity"] = m[8]
        else:
            market_data["activity"] = "UNKNOWN"
        return_obj["market_data"][m[1]].append(market_data)

    #
    # behaviour stuff
    #

    behaviour_ids = """select behaviour_id, description, default_params from behaviour_Definitions order by 1 """
    results = try_execute_select(behaviour_ids, (), client.connection)
    return_obj["behaviour_ids"] = [
        {"id": r[0], "params": json.dumps(r[2])} for r in results
    ]

    #
    # logs
    #

    sql = """select session_id, event_timestamp, event_name, error_code, event_params from logging 

where ship_symbol = %s
order by event_timestamp desc 
limit 7"""
    results = try_execute_select(sql, (ship.name,), client.connection)
    return_obj["logs"] = [
        {"event_name": r[2], "param_string": json.dumps(r[4]), "error_code": r[3]}
        for r in results
    ]

    sql = """select session_id,  event_params from logging 

where ship_symbol = %s
and event_name = 'BEGIN_BEHAVIOUR_SCRIPT'
order by event_timestamp desc 
limit 4"""
    results = try_execute_select(sql, (ship.name,), client.connection)
    return_obj["sessions"] = []
    for session in results:
        if "script_name" not in session[1]:
            continue
        behaviour_id = session[1]["script_name"]
        del session[1]["script_name"]
        return_obj["sessions"].append(
            {
                "session_id": session[0],
                "behaviour_id": behaviour_id,
                "param_pairs": {k: v for k, v in session[1].items()},
            }
        )
        return_obj["sessions"].reverse()

    #
    # dispatcher info
    #
    sql = """select ship_symbol, behaviour_id, locked_by, locked_until, behaviour_params
    from ship_behaviours
    where ship_symbol = %s 
    """
    results = try_execute_select(sql, (ship.name,), client.connection)
    _, behaviour_id, locked_by, locked_until, behaviour_params = results[0]
    return_obj["dispatcher_process"] = behaviour_id
    return_obj["dispatcher_locked_by"] = locked_by
    return_obj["dispatcher_locked_until"] = locked_until
    return_obj["dispatcher_alarm"] = (
        "text-danger" if locked_until < datetime.now() else "text-success"
    )
    return return_obj


def query_galaxy(client: SpaceTraders):
    min_x = 0
    min_y = 0
    max_x = 0
    max_y = 0
    sql = """select s.system_symbol, sector_symbol, s.type, s.x, s.y, count(wt.*) filter (where w.checked or wt.trait_symbol = 'UNCHARTED') = 0 as charted, w.under_construction
from waypoints w 
join systems s on w.system_Symbol = s.system_Symbol
left join waypoint_traits wt on wt.waypoint_symbol = w.waypoint_symbol
where w.type = 'JUMP_GATE'
group by w.waypoint_symbol, s.system_symbol, s.sector_symbol, s.type, s.x, s.y 
;

        """
    results = try_execute_select(sql, (), client.connection)
    systems = [
        {
            "system_symbol": r[0],
            "type": r[2],
            "x": r[3] / 50,
            "y": r[4] / 50,
            "charted": r[5],
            "under_construction": r[6],
        }
        for r in results
    ]
    sql = """select s_system_symbol, s.x s_x, s.y s_y, d_system_symbol, d.x d_x, d.y d_y
from jumpgate_connections jc 
join systems s on jc.s_system_symbol = s.system_symbol
join systems d on jc.d_system_symbol = d.system_symbol
    """
    results = try_execute_select(sql, (), client.connection)
    connections = [
        {
            "s_system_symbol": r[0],
            "s_x": r[1] / 50,
            "s_y": r[2] / 50,
            "d_system_symbol": r[3],
            "d_x": r[4] / 50,
            "d_y": r[5] / 50,
        }
        for r in results
    ]

    # <!--
    #        -->
    for s in systems:
        if s["x"] < min_x:
            min_x = s["x"]
        if s["y"] < min_y:
            min_y = s["y"]
        if s["x"] > max_x:
            max_x = s["x"]
        if s["y"] > max_y:
            max_y = s["y"]
    centre_x = -min_x - (max_x / 2)
    centre_y = -min_y - (max_y / 2)
    centre = {"x": centre_x, "y": centre_y}
    for s in systems:
        s["x"] -= min_x + (max_x / 2)
        s["y"] -= min_y + (max_y / 2)
    for c in connections:
        c["s_x"] -= min_x + (max_x / 2)
        c["s_y"] -= min_y + (max_y / 2)
        c["d_x"] -= min_x + (max_x / 2)
        c["d_y"] -= min_y + (max_y / 2)
    return {"systems": systems, "connections": connections, "centre": centre}


def query_imports_in_system(client: SpaceTraders, system_symbol: str):
    # SELECT system_symbol, market_symbol, trade_symbol, supply, activity, purchase_price, sell_price, market_depth, units_sold_recently
    # FROM public.import_overview;
    #

    sql = """SELECT system_symbol
    , market_symbol
    , trade_symbol
    , supply
    , activity
    , purchase_price
    , sell_price
    , market_depth
    , units_sold_recently
    from public.import_overview
    where system_symbol = %s"""
    results = try_execute_select(sql, (system_symbol,), client.connection)
    imports = {}
    for i in results:
        im = Import(i[0], i[1], i[2], i[3], i[4], i[5], i[6], i[7], i[8])
        if im.trade_symbol not in imports:
            imports[im.trade_symbol] = []
        imports[im.trade_symbol].append(im)
    return_obj = {
        "imports": [i.to_dict() for imps in imports.values() for i in imps],
        "system_symbol": system_symbol,
    }
    return return_obj


def query_exports_in_system(client: SpaceTraders, system_symbol: str):
    e_sql = """SELECT system_symbol
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

    e_results = try_execute_select(e_sql, (system_symbol,), client.connection)
    i_sql = """SELECT system_symbol, market_symbol, trade_symbol, supply, activity, purchase_price, sell_price, market_depth, units_sold_recently
	FROM public.import_overview
	where system_symbol = %s """
    i_results = try_execute_select(i_sql, (system_symbol,), client.connection)
    i_markets = {}
    for i in i_results:
        im = Import(i[0], i[1], i[2], i[3], i[4], i[5], i[6], i[7], i[8])
        if im.market_symbol not in i_markets:
            i_markets[im.market_symbol] = {}
        i_markets[im.market_symbol][im.trade_symbol] = im

    exports = {}
    for e in e_results:
        ex = Export(e[0], e[1], e[2], e[3], e[4], e[5], e[6], e[7], e[8], e[9] or [])
        for im in ex.requirements_txt:
            im_mkt = i_markets.get(ex.market_symbol, {})
            im_im = im_mkt.get(im, None)
            if im_im is not None:
                ex.requirements.append(im_im)

        if ex.trade_symbol not in exports:
            exports[ex.trade_symbol] = []
        exports[ex.trade_symbol].append(ex)

    return_obj = {
        "exports": [e.to_dict() for exes in exports.values() for e in exes],
        "system_symbol": system_symbol,
    }
    return return_obj
    # turn this into json and return


def get_some_export_requirements(export_name: str, exports_map) -> list["Export"]:
    export = exports_map.get(export_name, None)
    if export is None or len(export) == 0:
        return []
    export = export[0]
    return_obj = export.requirements_txt
    return return_obj


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
        self.units_purchased_recently = units_sold_recently
        self.requirements_txt = requirements_txt
        self.requirements = []

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
            "units_purchased_recently": self.units_purchased_recently,
            "requirements_txt": self.requirements_txt,
            "requirements": [r.to_dict() for r in self.requirements],
        }


@dataclass
class Import:
    system_symbol: str
    market_symbol: str
    trade_symbol: str
    supply: int
    activity: str
    purchase_price: int
    sell_price: int
    market_depth: int
    units_sold_recently: int

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
    return_obj["travel_time_fmt"] = (
        f"{floor(t/3600)}h {floor((t%3600)/60)}m {floor(t%60)}s"
    )
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
    return_obj["cooldown_time_fmt"] = (
        f"{floor(t/3600)}h {floor((t%3600)/60)}m {floor(t%60)}s"
    )

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
        recent_behaviour_sql, (ship_symbol,), client.connection
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
        incomplete_tasks_and_behaviours_sql,
        (ship_symbol, ship_symbol),
        client.connection,
    )
    if len(results) > 0 and results[0][0] is not None:
        return_obj["incomplete_tasks_and_behaviours"] = results
    return return_obj


def query_all_systems(st: SpaceTraders):
    sql = """select mss.system_symbol, ships as system_ships
, coalesce(total_export_tv, 0) as total_export_tv
, coalesce(units_exported, 0) as units_exported
, coalesce(profit_an_hour_ago,0) as profit_an_hour_ago
, fuel_most_expensive_cr
 from mat_system_summary mss
join agents a on mss.agent_name = a.agent_symbol
join waypoints w on w.waypoint_symbol = headquarters
where mss.agent_name = %s
order by w.system_symbol = mss.system_Symbol desc, mss.system_Symbol
"""

    results = try_execute_select(sql, (st.current_agent_symbol,), st.connection)
    if not results:
        st.connection.rollback()
        try_execute_upsert(
            "refresh materialized view mat_system_summary", (), st.connection
        )
        results = try_execute_select(sql, (st.current_agent_symbol,), st.connection)
    systems = []
    for result in results:
        systems.append(
            {
                "system_symbol": result[0],
                "system_ships": result[1],
                "total_export_tv": result[2],
                "units_exported": result[3],
                "profit_an_hour_ago": result[4],
                "fuel_most_expensive_cr": result[5],
            }
        )
    return {
        "systems": systems,
        "agent_name": st.current_agent_symbol,
        "agent_credits": st.view_my_self().credits,
        "agent_faction": st.view_my_self().starting_faction,
    }


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
    sql = """ select ships, total_export_tv,  units_exported, units_extracted, profit_an_hour_ago, last_updated,total_import_tv, fuel_export_symbols, best_export_price, fuel_most_expensive_sym, fuel_most_expensive_cr, number_of_export_markets, number_of_exchange_markets
	FROM public.mat_system_summary
    where agent_name = %s
    and system_symbol = %s"""
    system = {}
    results = try_execute_select(
        sql, (st.current_agent_symbol, syst.symbol), st.connection
    )
    if results and len(results) > 0:
        result = results[0]
        system["symbol"] = syst.symbol
        system["ships"] = result[0]
        system["total_export_tv"] = result[1]
        system["total_import_tv"] = result[6]
        system["units_exported"] = result[2]
        system["units_extracted"] = result[3]
        system["profit_an_hour_ago"] = result[4]
        system["last_updated"] = result[5]
        system["fuel_export_symbol"] = result[7][0] if result[7] else None
        system["fuel_best_export_price"] = result[8]
        system["fuel_most_expensive_sym"] = result[9]
        system["fuel_most_expensive_cr"] = result[10]
        system["number_of_export_markets"] = result[11]
        system["number_of_exchange_markets"] = result[12]
        if result[5] < datetime.now() - timedelta(hours=1):
            refresh_system_summary(st.connection)
    else:
        system["ships"] = 0
        system["total_export_tv"] = 0
        system["total_import_tv"] = 0
        system["units_exported"] = 0
        system["units_extracted"] = 0
        system["profit_an_hour_ago"] = 0
        system["last_updated"] = "never"

    return {"waypoints": waypoints, "centre": centre, "system": system}


def refresh_system_summary(connection):
    thread = threading.Thread(target=_refresh_system_summary, args=(connection,))
    thread.start()


def _refresh_system_summary(connection):
    sql = """refresh materialized view mat_system_summary;"""
    try_execute_upsert(sql, (), connection)


def query_session(client: SpaceTraders, session_id):
    sql = """
select * from logging where session_id = %s
order by event_name = 'BEGIN_BEHAVIOUR_SCRIPT', event_Timestamp desc  
limit 100;
"""
    session_id = session_id[5:]
    results = try_execute_select(sql, (session_id,), client.connection)
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
    elif script_name == "CHAIN_TRADES":
        f"{ship_name} is doing whatever profitable trades it can find, starting a new trade from a close to the end of the old trade as possible."
    elif script_name == "CONSTRUCT_JUMPGATE":
        response_lines.append(f"{ship_name} is getting inexpensive a jumpgate")
    elif script_name == "EXECUTE_CONTRACTS":
        response_lines.append(
            f"{ship_name} is executing any contract it can find, and generating & accepting profitable new ones."
        )
    elif script_name == "MONITOR_SPECIFIC_WAYPOINT":
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


def query_all_transactions(client: SpaceTraders):
    sql = """
SELECT last_transaction_in_session, ship_symbol, trade_symbol, units_sold, average_sell_price, average_purchase_price, net_change, purchase_wp, sell_wp, session_id, units_purchased
	FROM public.transaction_overview
    where ship_symbol ilike %s
    """
    results = try_execute_select(
        sql, (f"{client.current_agent_symbol}%",), client.connection
    )
    params = _process_transactions(client, results)
    params["page_title"] = (
        f"{client.current_agent_symbol} - All Transactions, All Systems"
    )
    return params


def query_system_transactions(client: SpaceTraders, system_symbol: str):
    sql = """
SELECT last_transaction_in_session, ship_symbol, trade_symbol, units_sold, average_sell_price, average_purchase_price, net_change, purchase_wp, sell_wp, session_id, units_purchased
	FROM public.transaction_overview
    where ship_symbol ilike %s
    and purchase_wp ilike %s or sell_wp ilike %s
    """
    results = try_execute_select(
        sql,
        (f"{client.current_agent_symbol}%", f"{system_symbol}%", f"{system_symbol}%"),
        client.connection,
    )
    params = _process_transactions(client, results)
    params["page_title"] = f"Transactions {system_symbol}"
    return params


def _process_transactions(self, results: list):
    transactions = []
    for result in results:
        start_time: datetime = result[0]
        if start_time.date() == datetime.now().date():
            end_time_fmt = start_time.strftime(r"%H:%M:%S")
        else:
            end_time_fmt = start_time.strftime(r"%Y-%m-%d %H:%M:%S")
        purchase_sys = ""
        sell_sys = ""
        transactions.append(
            {
                "end_time": end_time_fmt,
                "ship_symbol": result[1],
                "ship_suffix": waypoint_suffix(result[1]),
                "trade_symbol": result[2],
                "units_sold": result[3],
                "units_purchased": result[10],
                "average_sell_price": result[4],
                "average_purchase_price": result[5],
                "net_change": result[6] or 0,
                "purchase_wp": result[7] or "",
                "purchase_sys": purchase_sys,
                "purchase_wp_suffix": waypoint_suffix(result[7]) if result[7] else "",
                "sell_wp": result[8] or "",
                "sell_sys": sell_sys if sell_sys != purchase_sys else "",
                "sell_wp_suffix": waypoint_suffix(result[8]) if result[8] else "",
                "session_id": result[9],
                "session_id_trunc": result[9][0:5],
            }
        )
    return {"transactions": transactions}


def query_all_ships(client: SpaceTraders):
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
    results = try_execute_select(sql, (), client.connection)
    behaviours = {r[0]: r[1] for r in results}
    all_ships = client.ships_view().values()
    sorted_ships = _process_some_ships(client, all_ships, behaviours)
    return {
        "ships": sorted_ships,
        "total_ships": len(all_ships),
        "page_title": "All Ships, All Systems",
    }


def _process_some_ships(st: SpaceTraders, all_ships: list[Ship], behaviours: dict):
    sorted_ships = {}

    command_ships = [
        _summarise_ship(s, behaviours) for s in all_ships if s.role == "COMMAND"
    ]
    if len(command_ships) > 0:
        sorted_ships["COMMAND"] = command_ships
    transport_ships = [
        _summarise_ship(s, behaviours) for s in all_ships if s.role == "TRANSPORT"
    ]
    if len(transport_ships) > 0:
        sorted_ships["TRANSPORT"] = transport_ships

    #
    # satellite
    satellite_ships = [
        _summarise_ship(s, behaviours) for s in all_ships if s.role == "SATELLITE"
    ]
    if len(satellite_ships) > 0:
        sorted_ships["SATELLITE"] = satellite_ships

    #
    # hauler
    hauler_ships = [
        _summarise_ship(s, behaviours) for s in all_ships if s.role == "HAULER"
    ]
    if len(hauler_ships) > 0:
        sorted_ships["HAULER"] = hauler_ships

    #
    # refinery
    refinery_ships = [
        _summarise_ship(s, behaviours) for s in all_ships if s.role == "REFINERY"
    ]
    if len(refinery_ships) > 0:
        sorted_ships["REFINERY"] = refinery_ships
    explorer_ships = [
        _summarise_ship(s, behaviours) for s in all_ships if s.role == "EXPLORER"
    ]
    if len(explorer_ships) > 0:
        sorted_ships["EXPLORER"] = explorer_ships
    #
    # surveyor
    surveyor_ships = [
        _summarise_ship(s, behaviours) for s in all_ships if s.role == "SURVEYOR"
    ]
    if len(surveyor_ships) > 0:
        sorted_ships["SURVEYOR"] = surveyor_ships

    #
    # extractor
    extractor_ships = [
        _summarise_ship(s, behaviours)
        for s in all_ships
        if s.role == "EXCAVATOR" and s.can_extract
    ]
    if len(extractor_ships) > 0:
        sorted_ships["EXTRACTOR"] = extractor_ships
    siphoner_ships = [
        _summarise_ship(s, behaviours)
        for s in all_ships
        if s.role == "EXCAVATOR" and s.can_siphon
    ]
    if len(siphoner_ships) > 0:
        sorted_ships["SIPHONER"] = siphoner_ships

    return sorted_ships


def query_system_ships(client: SpaceTraders, system_symbol):
    sql = """with data as (
select ship_symbol, max(event_timestamp) as timestamp
from logging l 
where event_name = 'BEGIN_BEHAVIOUR_SCRIPT'
and event_timestamp >= now() - interval '1 day'
group by 1 
)
select l.ship_symbol, event_params ->> 'script_name' as script_name from logging l join data d on l.event_timestamp = d.timestamp and d.ship_symbol = l.ship_symbol
order by 1 """
    results = try_execute_select(sql, (), client.connection)
    behaviours = {r[0]: r[1] for r in results}
    all_ships = [
        s for s in client.ships_view().values() if s.nav.system_symbol == system_symbol
    ]
    return {
        "ships": _process_some_ships(client, all_ships, behaviours),
        "total_ships": len(all_ships),
        "page_title": f"All ships in {system_symbol}",
    }


def query_one_type_of_ships(client: SpaceTraders, role: str):
    sql = """with data as (
select ship_symbol, max(event_timestamp) as timestamp
from logging l 
where event_name = 'BEGIN_BEHAVIOUR_SCRIPT'
and event_timestamp >= now() - interval '1 day'
group by 1 
)
select l.ship_symbol, event_params ->> 'script_name' as script_name from logging l join data d on l.event_timestamp = d.timestamp and d.ship_symbol = l.ship_symbol
order by 1 """
    results = try_execute_select(sql, (), client.connection)
    behaviours = {r[0]: r[1] for r in results}
    all_ships = client.ships_view().values()
    if role in ["EXTRACTOR", "SIPHONER"]:
        all_ships = [s for s in all_ships if s.role == "EXCAVATOR"]
        if role == "EXTRACTOR":
            all_ships = [s for s in all_ships if s.can_extract]
        elif role == "SIPHONER":
            all_ships = [s for s in all_ships if s.can_siphon]
    else:
        all_ships = [s for s in all_ships if s.role == role]

    sorted_ships = _process_some_ships(client, all_ships, behaviours)
    return {
        "ships": sorted_ships,
        "total_ships": len(all_ships),
        "page_title": f"All ships of type {role}",
    }


def _summarise_ship(ship: Ship, most_recent_behaviours: dict) -> dict:
    most_recent_behaviour = most_recent_behaviours.get(ship.name, None)
    ship_travelling_intergaactic = False
    if ship.nav.status == "IN_TRANSIT":
        if waypoint_slicer(ship.nav.origin.symbol) == waypoint_slicer(
            ship.nav.destination.symbol
        ):
            nav_string = f"{waypoint_suffix(ship.nav.origin.symbol)} -> {waypoint_suffix(ship.nav.destination.symbol)}"
            system_string = f"""🌍{ship.nav.system_symbol}-"""
        else:
            nav_string = f"🌌{ship.nav.origin.symbol}->{ship.nav.destination.symbol}"
            system_string = ""
    else:
        system_string = f"{ship.nav.system_symbol}-"
        nav_string = f"{waypoint_suffix(ship.nav.waypoint_symbol)}"
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
        "system_nav": system_string,
        "current_system": ship.nav.system_symbol,
        "current_waypoint": ship.nav.waypoint_symbol,
        "behaviour": most_recent_behaviour,
    }


def map_role(role) -> str:
    roles = {
        "COMMAND": "👑",
        "EXCAVATOR": "⛏️",
        "HAULER": "🚛",
        "TRANSPORT": "🚚",
        "SURVEYOR": "🔬",
        "SATELLITE": "🛰️",
        "REFINERY": "⚙️",
        "EXPLORER": "🗺️",
    }
    return roles.get(role, role)


def map_frame(role) -> str:
    frames = {
        "FRAME_DRONE": "⛵",
        "FRAME_PROBE": "⛵",
        "FRAME_SHUTTLE": "⛵",
        "FRAME_MINER": "🚤",
        "FRAME_LIGHT_FREIGHTER": "🚤",
        "FRAME_EXPLORER": "🚤",
        "FRAME_FRIGATE": "🚤",
        "FRAME_HEAVY_FREIGHTER": "⛴️",
    }
    return frames.get(role, role)
