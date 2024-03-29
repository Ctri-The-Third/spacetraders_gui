# display commanders & their contract progress

# display ships & behaviours

# display discovered shipyards & market info (if available)
import psycopg2
import base64
import json
from straders_sdk.utils import try_execute_select, waypoint_slicer
from straders_sdk import SpaceTraders
from straders_sdk.models import Waypoint
from flask import Flask, render_template, request, send_from_directory
from datetime import datetime, timedelta

import query_functions as qf
import behaviour_functions as bf
import static.scripts.load_graphs as lg
import os

config_file_name = "user.json"
saved_data = json.load(open(config_file_name, "r+"))
db_host = os.environ.get("ST_DB_HOST", None)
db_port = os.environ.get("ST_DB_PORT", None)
db_name = os.environ.get("ST_DB_NAME", None)
db_user = os.environ.get("ST_DB_USER", None)
db_pass = os.environ.get("ST_DB_PASS", None)
if not db_pass:
    db_pass = os.environ.get("ST_DB_PASSWORD", None)


app = Flask(__name__)
users_and_clients = {}


@app.route("/query/<string>")
def query(string):
    st = setup_st(request)

    params = query_params(st, string)
    return render_template(params["_template"], **params)


@app.route("/small_window/<string>/")
def small_window(string):
    st = setup_st(request)
    params = query_params(st, string)
    return render_template("small_page.html", **params)


@app.route("/large_window/<string>/")
def marge_window(string):
    st = setup_st(request)
    params = query_params(st, string)
    return render_template("large_page.html", **params)


@app.route("/icons/<string>")
def load_icon(string):
    return send_from_directory("icons", string)


def query_params(st: SpaceTraders, string):
    st = setup_st(request)
    if string == "ALL_SYSTEMS":
        params = qf.query_all_systems(st)
        params["_template"] = "all_systems.html"
        params["_query"] = string
        return params
    elif string in ("GALAXY", "ALL_SYSTEMS"):
        params = qf.query_galaxy(st)
        params["_template"] = "galaxy_view.html"
        params["_query"] = string
        return params

    elif string == "HQ_SYSTEM":
        hq = st.view_my_self().headquarters
        string = waypoint_slicer(hq)
    # starts with "SHIPS_"
    elif string == "ALL_SHIPS":
        params = qf.query_all_ships(st)
        params["_template"] = "all_ships.html"
        params["_query"] = string
        return params
    elif string == "ALL_EXPORTS":
        params = qf.query_exports_in_system(
            st, waypoint_slicer(st.view_my_self().headquarters)
        )
        params["_template"] = "all_exports.html"
        params["_query"] = string

        return params
    elif string == "ALL_IMPORTS":
        params = qf.query_imports_in_system(
            st, waypoint_slicer(st.view_my_self().headquarters)
        )
        params["_template"] = "all_imports.html"
        params["_query"] = string
        return params
    elif string == "ALL_TRANSACTIONS":
        params = qf.query_all_transactions(st)
        params["_template"] = "all_transactions.html"
        params["_query"] = string
        return params
    # if string begins "CONTROL-"
    elif string[0:8] == "CONTROL-":
        params = qf.display_ship_controls(st, string[8:])
        params["_template"] = "ship_controls.html"
        params["_query"] = string
        return params
    elif string[0:5] == "SESH-":
        params = qf.query_session(st, string)
        params["_template"] = "session_summary.html"
        params["_query"] = string
        return params
    elif string[0:10] == "SHIP-ROLE-":
        ship_type = string[10:]
        params = qf.query_one_type_of_ships(st, ship_type)
        params["_template"] = "all_ships.html"
        params["_query"] = string
        return params
    # starts with ships-
    elif string[0:6] == "SHIPS-":
        system = string[6:]
        params = qf.query_system_ships(st, system)
        params["_template"] = "all_ships.html"
        params["_query"] = string
        return params
    # if string starts with "EXPORTS-"
    elif string[0:8] == "EXPORTS-":
        system = string[8:]
        params = qf.query_exports_in_system(st, system)
        params["_template"] = "all_exports.html"
        params["_query"] = string
        return params
    elif string[0:8] == "IMPORTS-":
        system = string[8:]
        params = qf.query_imports_in_system(st, system)
        params["_template"] = "all_imports.html"
        params["_query"] = string
        return params
    # TRANSACTIONS-
    elif string[0:13] == "TRANSACTIONS-":
        system = string[13:]
        params = qf.query_system_transactions(st, system)
        params["_template"] = "all_transactions.html"
        params["_query"] = string
        return params
    wayp = st.waypoints_view_one(string)
    if wayp:
        params = qf.query_waypoint(st, string)
        params["_template"] = "waypoint_summary.html"
        params["_query"] = string
        return params
    syst = st.systems_view_one(string)
    if syst:
        params = qf.query_system(st, string)
        params["_template"] = "system_view.html"
        params["_query"] = string
        return params
    ship = st.ships_view_one(string)
    if ship:
        params = qf.query_ship(st, string)
        params["_template"] = "ship_summary.html"
        params["_query"] = string
        return params
    raise FileNotFoundError


@app.route("/query/tradegood/<mkt_sym>/<tg_sym>")
def query_market_tradegood(tg_sym, mkt_sym):
    params = lg.market_listing_over_time(setup_st(request), tg_sym, mkt_sym)
    params["_query"] = f"/query/tradegood/{mkt_sym}/{tg_sym}"
    return json.dumps(params)
    # if it matches a player - go get the plaer summary
    # if it matches a ship - go get the ship summary


@app.route("/behaviour/submit/<ship_symbol>/<behaviour_id>", methods=["POST"])
def log_task_for_ship(ship_symbol, behaviour_id):

    st = setup_st(request)
    if not st:
        return "no token"
    params = dict(request.get_json())

    should_log_task = "behaviourOrTask" in params
    for param, value in params.items():
        try:
            params[param] = float(value)
        except:
            pass

    if ship_symbol == "undefined" or behaviour_id == "undefined":
        return "No ship or behaviour specified"
    if len(params) == 0:
        return "No parameters supplied"
    if should_log_task:
        bf.log_task(
            st.connection,
            behaviour_id,
            [],
            None,
            agent_symbol=st.current_agent_symbol,
            specific_ship_symbol=ship_symbol,
            behaviour_params=dict(params),
            expiry=datetime.now() + timedelta(hours=1),
        )
    else:
        bf.set_behaviour(st.connection, ship_symbol, behaviour_id, params)

    return "Task logged!"


# I wa
@app.route("/graph_window/query/tradegood/<mkt_sym>/<tg_sym>")
def graph_window_query_market_tradegood(mkt_sym, tg_sym):
    st = setup_st(request)

    params = {
        "_graph": lg.json_into_html(lg.market_listing_over_time(st, tg_sym, mkt_sym))
    }
    return render_template("graph_window.html", **params)
    # turn the params into a plotly graph then pass to the graph window


@app.route("/scripts/<script_file>")
def fetch_script(script_file):
    return send_from_directory("scripts", script_file)


@app.route("/css/<css_file>")
def fetch_css(css_file):
    return send_from_directory("css", css_file)


@app.route("/graph_template/")
def graph_template():
    return render_template("graph_template.html")


@app.route("/graph_content/")
def graph_content():
    raw_graph = lg.load_graphs(setup_st(request))
    return json.dumps(raw_graph)


@app.route("/graph_window/graph_content/")
def graph_window_graph_content():
    st = setup_st(request)
    params = {"_graph": lg.json_into_html(lg.load_graphs(setup_st(request)))}
    params["_query"] = f"/graph_content"
    return render_template("graph_window.html", **params)


def setup_st(request) -> SpaceTraders:
    # Split the JWT into its three components
    token = request.headers.get("Authorization")
    if token and "Bearer " in token and token != "Bearer null":
        token = token[7:]

    elif "sTradersToken" in request.cookies:
        token = request.cookies.get("sTradersToken")

    if not token:
        return None
    # take the "Bearer " off the front

    header_b64, payload_b64, signature = token.split(".")

    # Base64 decode the header and payload
    header = json.loads(base64.urlsafe_b64decode(header_b64 + "=="))
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))

    identifier = payload.get("identifier", None)
    if users_and_clients.get(identifier, None):
        return users_and_clients.get(identifier, None)
    st = SpaceTraders(
        token,
        db_host=db_host,
        db_name=db_name,
        db_user=db_user,
        db_pass=db_pass,
        current_agent_symbol=identifier,
        db_port=db_port,
    )
    users_and_clients[identifier] = st
    return st


@app.route("/")
def index():
    return render_template("main_page.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
