# display commanders & their contract progress

# display ships & behaviours

# display discovered shipyards & market info (if available)
import psycopg2
import json
from straders_sdk.utils import try_execute_select, waypoint_slicer
from straders_sdk.client_postgres import SpaceTradersPostgresClient as SpaceTraders
from straders_sdk.models import Waypoint
from flask import Flask, render_template
from datetime import datetime, timedelta
from query_functions import query_waypoint, query_ship, query_market

config_file_name = "user.json"
saved_data = json.load(open(config_file_name, "r+"))
db_host = saved_data.get("db_host", None)
db_port = saved_data.get("db_port", None)
db_name = saved_data.get("db_name", None)
db_user = saved_data.get("db_user", None)
db_pass = saved_data.get("db_pass", None)

st = SpaceTraders(db_host, db_name, db_user, db_pass, "CTRI-U-", db_port)
connection = st.connection
cursor = connection.cursor()

app = Flask(__name__)


@app.route("/query/<string>")
def query(string):
    if string[0:4] == "MKT-" and st.system_market(
        st.waypoints_view_one(waypoint_slicer(string[4:]), string[4:])
    ):
        params = query_market(st, string)
        return render_template("market_summary.html", **params)
    wayp = st.waypoints_view_one(waypoint_slicer(string), string)
    if wayp:
        params = query_waypoint(st, string)

        return render_template("waypoint_summary.html", **params)

    ship = st.ships_view_one(string)
    if ship:
        params = query_ship(st, string)
        return render_template("ship_summary.html", **params)
    # if it matches a player - go get the player summary
    # if it matches a ship - go get the ship summary


@app.route("/")
def index():
    syst = st.systems_view_one("X1-YG29")
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
    return render_template("main_page.html", waypoints=waypoints, centre=centre)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
