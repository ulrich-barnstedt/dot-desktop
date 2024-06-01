import json
import math
import sys
from io import BytesIO
import gi
import requests
from PIL import Image

gi.require_version('Playerctl', '2.0')
from gi.repository import Playerctl, GLib

manager = Playerctl.PlayerManager()
last_meta = dict()
last_status = dict()
default_dict = {
    "title": "<No title>",
    "artist": "<No artist>",
    "album": "<No album>",
    "image": "https://placehold.co/256x256",
    "color": "#777777",
    "color_border": "#999999"
}
default_status = True
mpris_keys = {"xesam:title", "xesam:artist", "xesam:album", "mpris:artUrl"}


def log_json():
    players = []
    for key in last_meta.keys() | last_status.keys():
        players.append(
                {"name": key} |
                {"is_playing": last_status.get(key, default_status)} |
                last_meta.get(key, default_dict)
        )

    print(json.dumps(players), flush=True)


def on_status(player, status, manager):
    mapped_status = status.value_nick
    mapped_status = True if mapped_status == "Playing" else False

    last_status[player.props.player_name] = mapped_status
    log_json()


def on_metadata(player, metadata, manager):
    if not mpris_keys.issubset(metadata.keys()):
        return

    mapped_meta = {
        "title": metadata["xesam:title"],
        "artist": ", ".join(metadata["xesam:artist"]),
        "album": metadata["xesam:album"],
        "image": metadata["mpris:artUrl"]
    }

    if mapped_meta["image"] != "":
        response = requests.get(mapped_meta["image"])
        img = Image.open(BytesIO(response.content))
        img.resize((1, 1), resample=0)
        color = img.getpixel((0, 0))

        color_light = "#{:x}{:x}{:x}".format(*color)
        mapped_meta["color_border"] = color_light

        color_dark = "#{:x}{:x}{:x}".format(*[math.floor(a * 0.85) for a in color])
        mapped_meta["color"] = color_dark

    for key in mapped_meta:
        if mapped_meta[key] == "":
            mapped_meta[key] = default_dict[key]

    last_meta[player.props.player_name] = mapped_meta
    log_json()


def init_player(name):
    player = Playerctl.Player.new_from_name(name)
    player.connect('playback-status', on_status, manager)
    player.connect('metadata', on_metadata, manager)
    manager.manage_player(player)


def on_name_appeared(manager, name):
    init_player(name)


def on_player_vanished(manager, player):
    name = player.props.player_name

    if name in last_meta:
        del last_meta[name]
    if name in last_status:
        del last_status[name]
    log_json()


manager.connect('name-appeared', on_name_appeared)
manager.connect('player-vanished', on_player_vanished)

for name in manager.props.player_names:
    init_player(name)

main = GLib.MainLoop()
main.run()
