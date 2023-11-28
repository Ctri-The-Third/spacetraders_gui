# display commanders & their contract progress

# display ships & behaviours

# display discovered shipyards & market info (if available)
import psycopg2
import base64
import json
from straders_sdk.utils import try_execute_select, waypoint_slicer
from straders_sdk import SpaceTraders
from straders_sdk.models import Waypoint
from flask import Flask, render_template, request
from datetime import datetime, timedelta
from query_functions import (
    query_waypoint,
    query_ship,
    query_market,
    query_system,
    query_all_ships,
)

config_file_name = "user.json"
saved_data = json.load(open(config_file_name, "r+"))
db_host = saved_data.get("db_host", None)
db_port = saved_data.get("db_port", None)
db_name = saved_data.get("db_name", None)
db_user = saved_data.get("db_user", None)
db_pass = saved_data.get("db_pass", None)


app = Flask(__name__)
users_and_clients = {}


@app.route("/query/<string>")
def query(string):
    st = setup_st(request)
    if string[0:4] == "MKT-" and st.system_market(
        st.waypoints_view_one(waypoint_slicer(string[4:]), string[4:])
    ):
        params = query_market(st, string)
        return render_template("market_summary.html", **params)
    elif string[0:5] == "LOGS-" and st.ships_view_one(string[5:]):
        params = query_ship_logs(st, string)
        return render_template("ship_logs.html", **params)
    elif string == "HQ_SYSTEM":
        hq = st.view_my_self().headquarters
        string = waypoint_slicer(hq)
    elif string == "ALL_SHIPS":
        params = query_all_ships(st)

        return render_template("all_ships.html", **params)

    wayp = st.waypoints_view_one(waypoint_slicer(string), string)
    if wayp:
        params = query_waypoint(st, string)
        return render_template("waypoint_summary.html", **params)
    syst = st.systems_view_one(string)
    if syst:
        params = query_system(st, string)
        return render_template("system_view.html", **params)
    ship = st.ships_view_one(string)
    if ship:
        params = query_ship(st, string)
        return render_template("ship_summary.html", **params)
    # if it matches a player - go get the player summary
    # if it matches a ship - go get the ship summary


def setup_st(request) -> SpaceTraders:
    # Split the JWT into its three components
    token = request.headers.get("Authorization")
    if not token:
        return None
    # take the "Bearer " off the front
    token = token[7:]
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
