from straders_sdk import SpaceTraders
from straders_sdk.utils import try_execute_select
from straders_sdk.constants import SUPPLY_LEVELS, ACTIVITY_LEVELS
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.offline import plot
from flask import jsonify
import json
import pandas as pd
import math


def _default_layout(title: str, y_axis_title: str):
    return {
        "title": title,
        "xaxis": {"title": "Time", "color": "white", "gridcolor": "#777"},
        "yaxis": {"title": y_axis_title, "color": "white", "gridcolor": "#777"},
        "paper_bgcolor": "rgb(55,55,55)",
        "plot_bgcolor": "rgb(55,55,55)",
        "font": {"color": "white"},
        "margin": {"t": 40, "b": 40, "l": 40, "r": 40, "pad": 4},
    }


def _trace(x, y, name, yaxis="y1", mode="lines+markers", color=None):
    return_obj = {
        "x": x,
        "y": y,
        "type": "scatter",
        "mode": mode,
        "name": name,
        "yaxis": yaxis,
        # "font": {"color": "white"},
    }
    if color:
        return_obj["marker"] = {"color": color}
    return return_obj


def load_graphs(st: SpaceTraders) -> dict:
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
    results = try_execute_select(query, [], st.connection)

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
        trace = _trace(
            [t.isoformat() for t in credits_df["time"].to_list()],
            cleaned_list,
            agent,
        )
        plotly_data.append(trace)

    layout = _default_layout("Credits Over Time", "Credits")
    layout["yaxis2"] = {"title": "credit_change", "overlaying": "y", "side": "right"}

    return {
        "data": plotly_data,
        "layout": layout,
    }


def json_into_html(plotly_dict: dict):
    layout: dict = plotly_dict.get("layout", {})
    yaxis2 = yaxis3 = None
    # if "yaxis2" in layout:
    #    yaxis2 = layout.get("yaxis2", None)
    #    del layout["yaxis2"]
    # if "yaxis3" in layout:
    #    yaxis3 = layout.get("yaxis3", None)
    #    del layout["yaxis3"]

    fig = go.Figure(data=plotly_dict["data"], layout=layout)
    if yaxis2:
        fig.update_layout(yaxis2=yaxis2)
    if yaxis3:
        fig.update_layout(yaxis3=yaxis3)
    return fig.to_html(full_html=False)


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


def market_listing_over_time(st: SpaceTraders, trade_symbol: str, market_symbol: str):
    sql = """select event_timestamp, SUPPLY, coalesce(activity,'WEAK') as activity
    , (case when type = 'EXPORT' then CURRENT_PURCHASE_PRICE else case when type ='IMPORT' then CURRENT_SELL_PRICE else (current_sell_price+current_purchase_price)/2 end end)::integer as current_impexp_price
    , mc.current_Trade_volume::integer
    from market_changes mc
    where market_symbol = %s
    and trade_symbol = %s
    and event_timestamp >= now() - interval ' 1 day'
    order by 1"""
    results = try_execute_select(sql, (market_symbol, trade_symbol), st.connection)
    df = pd.DataFrame(
        results,
        columns=[
            "event_timestamp",
            "supply",
            "activity",
            "current_impexp_price",
            "current_trade_volume",
        ],
    )
    df["supply_nermic"] = df["supply"].map(SUPPLY_LEVELS)
    df["activity_nermic"] = df["activity"].map(ACTIVITY_LEVELS)
    layout = _default_layout(
        f"{trade_symbol} at {market_symbol}", "import / export price"
    )
    layout["yaxis2"] = {
        "title": "",
        "color": "white",
        "overlaying": "y",
        "side": "right",
    }

    layout["yaxis3"] = {
        "title": "Supply, activity, tradevolume",
        "color": "white",
        "overlaying": "y",
        "side": "right",
    }

    traces = []

    cleaned_price = [
        None if math.isnan(y) else y for y in df["current_impexp_price"].to_list()
    ]
    cleaned_supply = [
        None if math.isnan(y) else y for y in df["supply_nermic"].to_list()
    ]
    cleaned_activity = [
        None if math.isnan(y) else y for y in df["activity_nermic"].to_list()
    ]
    cleaned_volume = [
        None if math.isnan(y) else y for y in df["current_trade_volume"].to_list()
    ]
    cleaned_timestamps = [t.isoformat() for t in df["event_timestamp"].to_list()]
    traces.append(
        _trace(cleaned_timestamps, cleaned_price, "price", color="rgba(255,0,0,1)")
    )
    traces.append(
        _trace(
            cleaned_timestamps,
            cleaned_supply,
            "supply",
            yaxis="y2",
            color="rgba(125, 255, 0, 0.5)",
        )
    )
    traces.append(
        _trace(
            cleaned_timestamps,
            cleaned_activity,
            "activity",
            yaxis="y2",
            color="rgba(0, 255, 125, 0.5)",
        )
    )
    traces.append(
        _trace(
            cleaned_timestamps,
            cleaned_volume,
            "volume",
            yaxis="y3",
            color="rgba(0, 255, 0, 0.5)",
        )
    )

    return {
        "data": traces,
        "layout": layout,
        "page_title": f"Market Listing - {trade_symbol} at {market_symbol}",
    }
