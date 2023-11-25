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
from query_functions import query_waypoint, query_ship, query_market, query_system

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
    elif string[0:5] == "LOGS-" and st.ships_view_one(string[5:]):
        params = query_ship_logs(st, string)
        return render_template("ship_logs.html", **params)
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


@app.route("/")
def index():
    return render_template("main_page.html", **query_system(st, "X1-YG29"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
