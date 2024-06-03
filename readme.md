
# Desktop dotfiles

This repo contains the dotfiles for my personal desktop widget layout.

![Demonstration](./demo.png)


## Features:

- Live clock and weather
- System info (user, host, uptime, distro, ...)
- System stats (CPU, RAM, storage, battery, temperature)
- Current media display (all players which support DBUS MPRIS, such as Spotify, Chrome, ...) with adaptive colors
- Shortcut menu for shutdown, logout, update, ...


## Dependencies

*CAUTION:* Many paths are currently hardcoded because of issues resolving them.
Weather location is also currently hardcoded.

- `eww` widget system
- `playerctl`
- `python3` with `Pillow`
