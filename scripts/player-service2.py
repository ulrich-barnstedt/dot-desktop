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
    "album": "<No album>",
    "image": "https://placehold.co/256x265",
    "color": "#777777",
    "color_border": "#999999"
}
dbus_keys = {"xesam:title", "xesam:artist", "xesam:album", "mpris:artUrl"}
interval_func_running = False


# send current data
def send_update():
    collected = []

    for player in manager.props.players:
        collected.append(
            {
                "name": player.props.player_name,
                "is_playing": player.props.playback_status.value_nick == "Playing",
                "position":
                    round(player.props.position / player.props.metadata["mpris:length"], 2)
                    if player.props.metadata["mpris:length"] != 0 else 0
            } |
            metadata_index.get(player.props.player_name, default_metadata)
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
        "title": metadata["xesam:title"],
        "artist": ", ".join(metadata["xesam:artist"]),
        "album": metadata["xesam:album"],
        "image": metadata["mpris:artUrl"]
    }

    if mapped_meta["image"] != "":
        loaded_image = True
        if mapped_meta["image"].startswith("file://"):
            path = mapped_meta["image"].replace("file://", "")
            if os.path.isfile(path):
                img = Image.open(path)
            else:
                loaded_image = False
        else:
            response = requests.get(mapped_meta["image"])
            img = Image.open(BytesIO(response.content))

        if loaded_image:
            img.resize((1, 1), resample=PIL.Image.Resampling.HAMMING)
            color = img.getpixel((0, 0))

            color_light = "#{:02x}{:02x}{:02x}".format(*color)
            mapped_meta["color_border"] = color_light

            color_dark = "#{:02x}{:02x}{:02x}".format(*[math.floor(a * 0.85) for a in color])
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
