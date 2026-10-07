# karaoke_ros

[![ROS 2 Humble](https://img.shields.io/badge/ROS%202-Humble-22314E?logo=ros)](https://docs.ros.org/en/humble/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Yes, ROS 2 is jazzy and lyrical, but can it karaoke?

This repo contains two packages:
* [`karaoke_interfaces`](karaoke_interfaces/)
* [`karaoke_ros`](karaoke_ros/)

## Installation and running

### Pixi

You can start everything with Pixi:

```sh
git clone https://github.com/IamPhytan/karaoke_ros.git
cd karaoke_ros/
pixi run launch
```

This starts the player and visualizer nodes, RViz and the rqt controller.
On the first run, pixi creates the environment and builds the packages with the [`pixi-build-ros`](https://pixi.sh/latest/build/backends/pixi-build-ros/) backend, which can take a few minutes.

### Build from source

Create a workspace:

```sh
mkdir -p ~/karaoke_ws/src
cd ~/karaoke_ws/src
git clone https://github.com/IamPhytan/karaoke_ros.git
```

Build the package:

```sh
cd ~/karaoke_ws
rosdep install --from-paths src -y --ignore-src
colcon build --symlink-install --packages-up-to karaoke_ros
```

Launch the player

```sh
. install/local_setup.bash
ros2 launch karaoke_ros karaoke.launch.py
```

## Songs

Songs are [LRC](https://en.wikipedia.org/wiki/LRC_(file_format)) files stored in [`songs`](karaoke_ros/songs/):
 
```
[ti:Title]
[ar:Artist]
[audio:my_song.ogg]
[00:03.00]A simple line
[00:06.00]<00:06.00>Line <00:06.40>with <00:06.90>word <00:07.30>timing
[01:10.00][01:40.00]A chorus line, sung twice
```

- `[audio:...]` is optional: by default, an `.ogg`, `.mp3` or `.wav` file with the same name is used
- Word tags (`<mm:ss.xx>`) are optional and highlight the current word
- Prefer ASCII for symbols: RViz fonts only cover a limited set of glyphs

For audio, you can add the associated audio file in the same directory:

```sh
karaoke_ros/songs
├── my_song.lrc
├── my_song.mp3
└── ros_song.lrc
```

## License

This repo is licensed under a [MIT](LICENSE) license.

