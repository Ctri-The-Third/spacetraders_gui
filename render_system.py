import straders_sdk.models as models
import dearpygui.dearpygui as dpg


orbitals = ["ORBITAL_STATION", "MOON"]


def render_system(system: models.System, width, height, zoom_scale=3, cv=[0, 0]):
    dpg.draw_circle([0 + cv[0], 0 + cv[1]], 5, fill=[0, 255, 0], thickness=1)

    for w in [t for t in system.waypoints if t.type not in orbitals]:
        w: models.Waypoint
        distance = (w.x**2 + w.y**2) ** 0.5
        dpg.draw_circle(
            [
                (w.x * zoom_scale) + cv[0],
                (w.y * zoom_scale) + cv[1],
            ],
            5,
            fill=[255, 0, 0, 255],
            thickness=1,
            tag=w.symbol,
        )
        try:
            import sys

            # lots of issues here, something to do with the difference between
            # dpg.tooltip and dpg.add_tooltip, withs, yields, etc...
            ttip_int = dpg.add_tooltip(w.symbol)
            val = dpg.add_text(
                f"Symbol: {w.symbol}\nType: {w.type}\nLocation: {w.x}, {w.y}\nTraits: {[t.name for t in w.traits]}",
                parent=ttip_int,
            )

        except SystemError as err:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            print(exc_type, exc_value, exc_traceback)
        dpg.draw_text(
            [
                (w.x * zoom_scale) + cv[0] + 5,
                (w.y * zoom_scale) + cv[1] + 5,
            ],
            w.symbol,
            color=[255, 255, 255, 255],
            size=14,
        )
        dpg.draw_circle(
            [0 + cv[0], 0 + cv[1]],
            distance * zoom_scale,
            thickness=1,
            color=[255, 255, 255, 25],
        )
        print(w.symbol, w.x, w.y)
