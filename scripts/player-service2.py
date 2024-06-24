import json
import math
import os.path
import PIL
import gi
import requests
from PIL import Image
from io import BytesIO

gi.require_version('Playerctl', '2.0')
from gi.repository import Playerctl, GLib

manager = Playerctl.PlayerManager()
metadata_index = dict()
default_metadata = {
    "title": "<No title>",
    "artist": "<No artist>",
    "album": "<Unknown album>",
    "image": "https://placehold.co/256x265",
    "color": "#777777",
    "color_border": "#999999",
    "dark_text": True
}
border_threshold = 30
dark_threshold = 135
text_limit = 32
dbus_keys = {"xesam:title", "xesam:artist", "xesam:album", "mpris:artUrl"}
interval_func_running = False


# send current data
def send_update():
    collected = []

    for player in manager.props.players:
        metadata = metadata_index.get(player.props.player_name, default_metadata)

        # filter chromium left over empty player
        if player.props.player_name == "chromium":
            if metadata["title"] == default_metadata["title"] and metadata["artist"] == default_metadata["artist"]:#
                continue

        collected.append(
            {
                "name": player.props.player_name,
                "is_playing": player.props.playback_status.value_nick == "Playing",
                "position":
                    round(player.props.position / int(player.props.metadata["mpris:length"]), 2) * 100
                    if player.props.metadata["mpris:length"] != 0 else 0
            } |
            metadata
        )

    print(json.dumps(collected), flush=True)


def interval_function():
    global interval_func_running
    send_update()

    for player in manager.props.players:
        if player.props.playback_status.value_nick == "Playing":
            return True

    interval_func_running = False
    return False


# register sender on play
def on_status(player, status, manager):
    global interval_func_running
    send_update()

    if not interval_func_running:
        for player in manager.props.players:
            if player.props.playback_status.value_nick == "Playing":
                GLib.timeout_add_seconds(
                    2,
                    interval_function
                )
                interval_func_running = True


# remap metadata on update
def on_metadata(player, metadata, manager):
    if not dbus_keys.issubset(metadata.keys()):
        return

    mapped_meta = {
        "title": metadata["xesam:title"].replace("\\", "\\\\"),
        "artist": ", ".join(metadata["xesam:artist"]).replace("\\", "\\\\"),
        "album": metadata["xesam:album"],
        "image": metadata["mpris:artUrl"].replace("\\", "\\\\")
    }

    for prop in ["title", "album", "artist"]:
        if len(mapped_meta[prop]) > text_limit:
            mapped_meta[prop] = mapped_meta[prop][0:text_limit] + "..."

    if mapped_meta["image"] != "":
        loaded_image = True
        if mapped_meta["image"].startswith("file://"):
            path = mapped_meta["image"].replace("file://", "")
            try:
                img = Image.open(path)
            except:
                loaded_image = False
        else:
            response = requests.get(mapped_meta["image"])
            img = Image.open(BytesIO(response.content))

        if loaded_image:
            img = img.resize((3, 3), resample=PIL.Image.Resampling.HAMMING)
            color = img.getpixel((1, 1))
            if isinstance(color, int):
                color = (color, color, color)

            if color[0] < border_threshold and color[1] < border_threshold and color[2] < border_threshold:
                color_light = "#434a57"
            else:
                color_light = "#{:02x}{:02x}{:02x}".format(*color)
            mapped_meta["color_border"] = color_light

            color_dark = [math.floor(a * 0.80) for a in color]
            if color_dark[0] > dark_threshold or color_dark[1] > dark_threshold or color_dark[2] > dark_threshold:
                mapped_meta["dark_text"] = True
            else:
                mapped_meta["dark_text"] = False
            color_dark = "rgba({}, {}, {}, 0.92)".format(*color_dark)
            mapped_meta["color"] = color_dark

    for key in default_metadata:
        if mapped_meta.get(key, "") == "":
            mapped_meta[key] = default_metadata[key]

    metadata_index[player.props.player_name] = mapped_meta
    send_update()


# register player & fake update
def on_name_appeared(manager, name):
    player = Playerctl.Player.new_from_name(name)
    player.connect('playback-status', on_status, manager)
    player.connect('metadata', on_metadata, manager)
    manager.manage_player(player)

    # send "fake" update
    on_metadata(player, player.props.metadata, manager)
    on_status(player, player.props.playback_status, manager)


# delete old players
def on_player_vanished(manager, player):
    if player.props.player_name in metadata_index:
        del metadata_index[player.props.player_name]

    send_update()


manager.connect('name-appeared', on_name_appeared)
manager.connect('player-vanished', on_player_vanished)

for name in manager.props.player_names:
    on_name_appeared(manager, name)

main = GLib.MainLoop()
main.run()
