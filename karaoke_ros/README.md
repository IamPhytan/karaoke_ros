# karaoke_ros

> Bringing karaoke to ROS 2

This package provides ROS 2 nodes for a karaoke player:

- A player node that streams lyrics
- A visualizer that displays everything in RViz
- A RQt plugin to control the player

## Installation and run

### Pixi

You can start everything with Pixi:

```sh
pixi run ros2 launch karaoke_ros karaoke.launch.py
```

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
colcon build --packages-up-to karaoke_ros
```

Launch the player

```sh
. install/local_setup.bash
ros2 launch karaoke_ros karaoke.launch.py
```

## Songs

Songs are [LRC](https://en.wikipedia.org/wiki/LRC_(file_format)) files stored in [`songs`](songs):
 
```
[ti:Title]
[ar:Artist]
[audio:my_song.ogg]
[00:03.00]A simple line
[00:06.00]<00:06.00>Line <00:06.40>with <00:06.90>word <00:07.30>timing
[01:10.00][01:40.00]A chorus line, sung twice
```

- `[audio:...]` is optional : by default, an `.ogg`, `.mp3` or `.wav` file with the same name is used
- Word tags (`<mm:ss.xx>`) are optional, and highlight the current word
- Prefer ASCII for symbols : RViz fonts only cover a limited set of glyphs

For audio, you can add the associated audio file in the same directory:

```sh
karaoke_ros/songs
├── my_song.lrc
├── my_song.mp3
└── ros_song.lrc
```

## License

This package is licensed under a [MIT](LICENSE) license.

