import dearpygui.dearpygui as dpg
import dearpygui.demo as demo

from straders_sdk.client_postgres import SpaceTradersPostgresClient as SpaceTraders
import straders_sdk.models
from straders_sdk.utils import waypoint_slicer
import json
import logging

from render_system import render_system

dpg.create_context()
dpg.configure_app(manual_callback_management=True)

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


agent = st.view_my_self()
target_system = st.systems_view_one(waypoint_slicer(agent.headquarters))

page_width = 800
page_height = 600
cv = [page_width / 2, page_height / 2]
zoom_scale = 3
with dpg.window(
    label="Tutorial",
    no_collapse=True,
    no_resize=True,
    no_move=True,
    no_scroll_with_mouse=True,
    no_scrollbar=True,
):
    with dpg.drawlist(page_width, page_height - 50):
        with dpg.draw_layer(tag="system_view"):
            render_system(target_system, page_width, page_height, zoom_scale, cv)


def roll_mouse_wheel(sender, app_data):
    logging.info(f"Mouse wheel rolled {app_data}")
    global zoom_scale

    zoom_scale += app_data

    dpg.configure_item("system_view", zoom_scale=zoom_scale)


with dpg.handler_registry():
    dpg.add_mouse_wheel_handler(callback=roll_mouse_wheel)


dpg.create_viewport(title="Custom Title", width=page_width, height=page_height)
dpg.setup_dearpygui()
dpg.show_viewport()
while dpg.is_dearpygui_running():
    jobs = dpg.get_callback_queue()  # retrieves and clears queue
    # dpg.run_callbacks(jobs)
    dpg.render_dearpygui_frame()

dpg.destroy_context()
