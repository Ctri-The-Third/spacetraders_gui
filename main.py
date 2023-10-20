import dearpygui.dearpygui as dpg
import dearpygui.demo as demo

from straders_sdk.client_postgres import SpaceTradersPostgresClient as SpaceTraders
from straders_sdk.utils import waypoint_slicer
import json

config = {}
with open("user.json") as f:
    config = json.load(f)

st = SpaceTraders(
    config["db_host"],
    config["db_name"],
    config["db_user"],
    config["db_pass"],
    config["agent_name"],
    db_port=config["db_port"],
)

dpg.create_context()


agent = st.view_my_self()
target_system = st.systems_view_one(waypoint_slicer(agent.headquarters))

page_height = 600
page_width = 800
zoom_scale = 5
with dpg.window(tag="Tutorial"):
    with dpg.drawlist(width=800, height=600):
        dpg.draw_circle(
            [0 + page_width / 2, 0 + page_height / 2], 5, fill=[0, 255, 0], thickness=1
        )
        for waypoint in target_system.waypoints:
            dpg.draw_circle(
                [
                    (waypoint.x * zoom_scale) + (page_height / 2),
                    (waypoint.y * zoom_scale) + (page_width / 2),
                ],
                5,
                fill=[255, 0, 0, 255],
                thickness=1,
            )
            dpg.draw_text(
                [
                    (waypoint.x * zoom_scale) + (page_height / 2) + 5,
                    (waypoint.y * zoom_scale) + (page_width / 2) + 5,
                ],
                waypoint.symbol,
                color=[255, 255, 255, 255],
                size=14,
            )
            print(waypoint.symbol, waypoint.x, waypoint.y)

dpg.create_viewport(title="Custom Title", width=800, height=600)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
