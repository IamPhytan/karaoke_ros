"""Karaoke player node.

Services  : /karaoke/play, /karaoke/pause, /karaoke/toggle, /karaoke/stop (std_srvs/Trigger)
            /karaoke/load_song (karaoke_interfaces/LoadSong)
            /karaoke/list_songs (karaoke_interfaces/ListSongs)
Action    : /karaoke/sing (karaoke_interfaces/SingSong) - feedback on every line / word
Topic     : /karaoke/state (karaoke_interfaces/PlayerState) at tick_rate Hz
Parameters: songs_dir, song (reloaded live via rqt_reconfigure),
            tick_rate, play_audio, autostart
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

import rclpy
from ament_index_python.packages import get_package_share_directory
from rcl_interfaces.msg import SetParametersResult
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.action.server import ServerGoalHandle
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_srvs.srv import Trigger

from karaoke_interfaces.action import SingSong
from karaoke_interfaces.msg import PlayerState
from karaoke_interfaces.srv import ListSongs, LoadSong

from .lrc import Song, parse_lrc

try:  # audio optionnel
    import pygame  # type: ignore

    pygame.mixer.init()
    _HAS_AUDIO = True
except Exception:  # pragma: no cover
    _HAS_AUDIO = False


class KaraokePlayer(Node):
    def __init__(self) -> None:
        super().__init__("karaoke_player")
        default_dir = str(Path(get_package_share_directory("karaoke_ros")) / "songs")
        self.declare_parameter("songs_dir", default_dir)
        self.declare_parameter("song", "ros_song.lrc")
        self.declare_parameter("tick_rate", 20.0)
        self.declare_parameter("play_audio", True)
        self.declare_parameter("autostart", False)

        self._lock = threading.Lock()
        self._song: Optional[Song] = None
        self._song_name = None
        self._position = 0.0
        self._playing = False
        self._last_tick = self.get_clock().now()
        self._audio_loaded = False

        cbg = ReentrantCallbackGroup()
        self._state_pub = self.create_publisher(PlayerState, "~/state", 10)

        for name, fn in (
            ("play", self._srv_play),
            ("pause", self._srv_pause),
            ("toggle", self._srv_toggle),
            ("stop", self._srv_stop),
        ):
            self.create_service(Trigger, f"~/{name}", fn, callback_group=cbg)
        self.create_service(LoadSong, "~/load_song", self._srv_load, callback_group=cbg)
        self.create_service(
            ListSongs, "~/list_songs", self._srv_list, callback_group=cbg
        )

        self._action = ActionServer(
            self,
            SingSong,
            "~/sing",
            execute_callback=self._execute_sing,
            goal_callback=lambda _: GoalResponse.ACCEPT,
            cancel_callback=lambda _: GoalResponse.ACCEPT,
            callback_group=cbg,
        )

        self.add_on_set_parameters_callback(self._on_params)
        rate = self.get_parameter("tick_rate").value
        self.create_timer(1.0 / rate, self._tick, callback_group=cbg)

        self._load(self.get_parameter("song").value)
        if self.get_parameter("autostart").value:
            self._set_playing(True)
        self.get_logger().info("Karaoke player ready")

    # ------------------------------------------------------------ helpers
    def _songs_dir(self) -> Path:
        return Path(self.get_parameter("songs_dir").value).expanduser()

    def _resolve(self, name: str) -> Path:
        p = Path(name).expanduser()
        return p if p.is_absolute() else self._songs_dir() / name

    def _load(self, name: str) -> tuple[bool, str]:
        path = self._resolve(name)
        if not path.exists():
            return False, f"Unfound file: {path}"
        try:
            song = parse_lrc(path)
        except Exception as e:
            return False, f"Parsing error : {e}"
        if not song.lines:
            return False, "No lyrics lines in the file"

        with self._lock:
            self._stop_audio()
            self._song = song
            self._song_name = path.name
            self._position = 0.0
            self._playing = False
            self._audio_loaded = False
            if _HAS_AUDIO and self.get_parameter("play_audio").value and song.audio:
                try:
                    pygame.mixer.music.load(str(song.audio))
                    self._audio_loaded = True
                except Exception as e:  # noqa: BLE001
                    self.get_logger().warn(f"Audio not loaded : {e}")
        self.get_logger().info(
            f"Loaded '{song.title}' ({len(song.lines)} lines, {song.duration:.0f}s)"
        )
        return True, f"Loaded {path.name}"

    def _set_playing(self, playing: bool) -> None:
        with self._lock:
            if self._song is None:
                return
            if playing == self._playing:
                return
            self._playing = playing
            self._last_tick = self.get_clock().now()
            if self._audio_loaded:
                if playing:
                    if self._position <= 0.01:
                        pygame.mixer.music.play()
                    else:
                        pygame.mixer.music.unpause()
                else:
                    pygame.mixer.music.pause()

    def _stop_audio(self) -> None:
        if _HAS_AUDIO and self._audio_loaded:
            pygame.mixer.music.stop()

    def _rewind(self) -> None:
        with self._lock:
            self._position = 0.0
            self._playing = False
            self._stop_audio()

    def _state_msg(self) -> PlayerState:
        msg = PlayerState()
        with self._lock:
            song, pos = self._song, self._position
            msg.playing = self._playing
            msg.song = self._song_name
        if song is None:
            msg.line_index = -1
            return msg
        idx = song.line_index_at(pos)
        msg.title, msg.artist = song.title, song.artist
        msg.position, msg.duration = float(pos), float(song.duration)
        msg.line_index, msg.line_count = idx, len(song.lines)
        msg.current_line = song.lines[idx].text if idx >= 0 else ""
        msg.current_word = song.word_at(idx, pos)
        msg.next_line = song.lines[idx + 1].text if idx + 1 < len(song.lines) else ""
        return msg

    # ------------------------------------------------------------ timer
    def _tick(self) -> None:
        """Advance the playback clock and publish the state."""
        now = self.get_clock().now()
        with self._lock:
            if self._playing and self._song is not None:
                self._position += (now - self._last_tick).nanoseconds * 1e-9
                if self._position >= self._song.duration:  # End of song
                    self._position = self._song.duration
                    self._playing = False
                    self._stop_audio()
            self._last_tick = now
        self._state_pub.publish(self._state_msg())

    # ------------------------------------------------------------ services
    def _srv_play(
        self,
        _req: Trigger.Request,
        res: Trigger.Response,
    ) -> Trigger.Response:
        self._set_playing(True)
        res.success, res.message = True, "play"
        return res

    def _srv_pause(
        self,
        _req: Trigger.Request,
        res: Trigger.Response,
    ) -> Trigger.Response:
        self._set_playing(False)
        res.success, res.message = True, "pause"
        return res

    def _srv_toggle(
        self,
        _req: Trigger.Request,
        res: Trigger.Response,
    ) -> Trigger.Response:
        self._set_playing(not self._playing)
        res.success, res.message = True, "play" if self._playing else "pause"
        return res

    def _srv_stop(
        self,
        _req: Trigger.Request,
        res: Trigger.Response,
    ) -> Trigger.Response:
        self._rewind()
        res.success, res.message = True, "stop"
        return res

    def _srv_load(
        self,
        req: LoadSong.Request,
        res: LoadSong.Response,
    ) -> LoadSong.Response:
        raise NotImplementedError()
        return res

    def _srv_list(
        self,
        req: ListSongs.Request,
        res: ListSongs.Response,
    ) -> ListSongs.Response:
        raise NotImplementedError()
        return res

    def _on_params(self, params):
        # Reject the parameter change if the song cannot be loaded
        for p in params:
            if p.name == "song":
                ok, msg = self._load(p.value)
                if not ok:
                    return SetParametersResult(successful=False, reason=msg)
        return SetParametersResult(successful=True)

    # ------------------------------------------------------------ action
    def _execute_sing(self, goal: ServerGoalHandle):
        """Start playback and stream lyrics as feedback until the song ends."""
        req: SingSong.Goal = goal.request
        result = SingSong.Result()

        if req.song:
            ok, msg = self._load(req.song)
            if not ok:
                goal.abort()
                result.message = msg
                return result
            raise NotImplementedError()


def main():
    rclpy.init()
    node = KaraokePlayer()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
