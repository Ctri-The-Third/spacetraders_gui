from straders_sdk import SpaceTraders
from straders_sdk.utils import try_execute_select
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import plot
from flask import jsonify
import json
import pandas as pd
import math


def load_graphs(st: SpaceTraders):
    query = """
              with data as (         select date_trunc('hour', event_timestamp) + (date_part('minute', event_timestamp)::integer / 10 * interval '10 minute') AS interval_start
                , agent_name, round(avg(new_credits)) as new_credits from logging 
                where event_name in ('BEGIN_BEHAVIOUR_SCRIPT','END_BEHAVIOUR_SCRIPT')
                and event_timestamp > now() - interval '18 hours'
                group by 1,2 
                order by 1 desc ,2
			  )
			  select *, new_Credits - lag(new_credits) over (partition by agent_name order by interval_start) as credits_change from data 
			  order by 1 desc 
                """
    results = try_execute_select(st.connection, query, [])

    df = pd.DataFrame(results, columns=["time", "agent", "credits", "credits_change"])
    # get all unique agents
    unique_agents = df["agent"].unique()
    credits_df = pd.pivot_table(df, index="time", columns="agent", values="credits")
    credits_change_df = pd.pivot_table(
        df, index="time", columns="agent", values="credits_change"
    )
    credits_df = credits_df.reset_index()
    credits_change_df = credits_change_df.reset_index()
    plotly_data = []
    for agent in unique_agents:
        # I need to replace "nan" with None
        cleaned_list = [
            None if math.isnan(y) else y for y in credits_df[agent].to_list()
        ]
        trace = {
            "x": [t.isoformat() for t in credits_df["time"].to_list()],
            "y": cleaned_list,
            "type": "scatter",
            "mode": "lines+markers",
            "name": agent,
        }
        plotly_data.append(trace)

        # cleaned_list = [
        #    None if math.isnan(y) else y for y in credits_change_df[agent].to_list()
        # ]
        # trace2 = {
        #    "x": [t.isoformat() for t in credits_change_df["time"].to_list()],
        #    "y": cleaned_list,
        #    "type": "scatter",
        #    "mode": "lines+markers",
        #    "name": f"{agent}-changes",
        #    "yaxis": "y2",
        # }
        # plotly_data.append(trace2)

    layout = {
        "title": "Credits and Other Credits Over Time",
        "xaxis": {"title": "Time"},
        "yaxis": {"title": "Credits"},
        "yaxis2": {"title": "credit_change", "overlaying": "y", "side": "right"},
    }
    # Serialize and use jsonify to ensure proper content type
    # output = df.to_json(orient="records")
    # print(json.dumps(df.to_dict(), indent=4))
    return json.dumps(
        {
            "data": plotly_data,
            "layout": layout,
        }
    )


if __name__ == "__main__":
    import json

    saved_data = json.load(open("user.json", "r+"))
    token = None
    user = saved_data.get("saved_data", None)
    token = ""
    db_host = saved_data.get("db_host", None)
    db_port = saved_data.get("db_port", None)
    db_name = saved_data.get("db_name", None)
    db_user = saved_data.get("db_user", None)
    db_pass = saved_data.get("db_pass", None)
    st = SpaceTraders(
        token,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_pass=db_pass,
        current_agent_symbol=user,
    )
    print(load_graphs(st))
