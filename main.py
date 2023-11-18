# display commanders & their contract progress

# display ships & behaviours

# display discovered shipyards & market info (if available)
import psycopg2
import json
from straders_sdk.utils import try_execute_select
from straders_sdk.client_postgres import SpaceTradersPostgresClient as SpaceTraders
from flask import Flask, render_template
from datetime import datetime, timedelta
from query_functions import query_waypoint

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
    params = query_waypoint(st, string)

    return render_template("waypoint_summary.html", **params)
    # if it matches a player - go get the player summary
    # if it matches a ship - go get the ship summary


@app.route("/")
def index():
    return render_template("system_view.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
