"""rqt plugin: karaoke remote control.

Run with:  rqt --standalone karaoke_ros   (or via Plugins > Karaoke in rqt)
"""

from __future__ import annotations

from python_qt_binding.QtCore import QTimer
from python_qt_binding.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from rqt_gui_py.plugin import Plugin
from std_srvs.srv import Trigger

from karaoke_interfaces.msg import PlayerState
from karaoke_interfaces.srv import ListSongs, LoadSong


class KaraokePlugin(Plugin):
    def __init__(self, context):
        super().__init__(context)
        self.setObjectName("KaraokePlugin")
        self._node = context.node  # node provided and spun by rqt
        self._state = None
        self._last_songs: list[str] = []

        # --- service clients / subscriber
        self._cli = {n: self._node.create_client(Trigger, f"/karaoke/{n}") for n in ("play", "pause", "toggle", "stop")}
        self._cli_load = self._node.create_client(LoadSong, "/karaoke/load_song")
        self._cli_list = self._node.create_client(ListSongs, "/karaoke/list_songs")
        self._sub = self._node.create_subscription(PlayerState, "/karaoke/state", self._on_state, 10)

        # --- UI
        self._widget = QWidget()
        self._widget.setWindowTitle("Karaoke")
        root = QVBoxLayout(self._widget)

        # Row 1: song selector
        row = QHBoxLayout()
        self._combo = QComboBox()
        self._btn_refresh = QPushButton("↻")
        self._btn_refresh.setFixedWidth(32)
        self._btn_load = QPushButton("Load")
        row.addWidget(QLabel("Song"))
        row.addWidget(self._combo, 1)
        row.addWidget(self._btn_refresh)
        row.addWidget(self._btn_load)
        root.addLayout(row)

        # Row 2: transport buttons
        row = QHBoxLayout()
        self._btn_play = QPushButton("▶ Play")
        self._btn_pause = QPushButton("❚❚ Pause")
        self._btn_stop = QPushButton("■ Stop")
        for b in (self._btn_play, self._btn_pause, self._btn_stop):
            row.addWidget(b)
        root.addLayout(row)

        # Progress + lyrics preview
        self._progress = QProgressBar()
        self._progress.setRange(0, 1000)
        self._progress.setTextVisible(False)
        root.addWidget(self._progress)

        self._lbl_title = QLabel("—")
        self._lbl_line = QLabel("")
        self._lbl_line.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self._lbl_line.setWordWrap(True)
        self._lbl_time = QLabel("00:00 / 00:00")
        root.addWidget(self._lbl_title)
        root.addWidget(self._lbl_line)
        root.addWidget(self._lbl_time)

        # Distinguish multiple instances of the plugin
        if context.serial_number() > 1:
            self._widget.setWindowTitle(f"Karaoke ({context.serial_number()})")
        context.add_widget(self._widget)

        # --- signals
        self._btn_play.clicked.connect(lambda: self._call("play"))
        self._btn_pause.clicked.connect(lambda: self._call("pause"))
        self._btn_stop.clicked.connect(lambda: self._call("stop"))
        self._btn_refresh.clicked.connect(self._refresh_songs)
        self._btn_load.clicked.connect(self._load_selected)

        # ROS callbacks run outside the Qt thread: refresh the UI from a QTimer
        self._timer = QTimer(self._widget)
        self._timer.timeout.connect(self._update_ui)
        self._timer.start(150)
        self._refresh_songs()

    # ------------------------------------------------------------ ROS
    def _on_state(self, msg: PlayerState) -> None:
        self._state = msg  # just store; never touch widgets from here

    def _call(self, name: str) -> None:
        cli = self._cli[name]
        if not cli.service_is_ready():
            self._node.get_logger().warn(f"Service /karaoke/{name} unavailable")
            return
        cli.call_async(Trigger.Request())  # fire-and-forget

    def _refresh_songs(self) -> None:
        if not self._cli_list.service_is_ready():
            return
        fut = self._cli_list.call_async(ListSongs.Request())
        fut.add_done_callback(self._on_songs)

    def _on_songs(self, fut) -> None:
        try:
            res = fut.result()
        except Exception:  # noqa: BLE001
            return
        self._last_songs = list(res.songs)  # applied on the next Qt tick

    def _load_selected(self) -> None:
        name = self._combo.currentText()
        if not name or not self._cli_load.service_is_ready():
            return
        req = LoadSong.Request()
        req.song = name
        self._cli_load.call_async(req)

    # ------------------------------------------------------------ Qt
    def _update_ui(self) -> None:
        # Rebuild the combo box only if the song list actually changed
        if self._last_songs is not None and self._last_songs != [
            self._combo.itemText(i) for i in range(self._combo.count())
        ]:
            cur = self._combo.currentText()
            self._combo.clear()
            self._combo.addItems(self._last_songs)
            if cur in self._last_songs:
                self._combo.setCurrentText(cur)

        s = self._state
        if s is None:
            return
        title = s.title or s.song or "—"
        if s.artist:
            title += f" — {s.artist}"
        self._lbl_title.setText(("▶ " if s.playing else "❚❚ ") + title)
        line = s.current_line
        if s.current_word:
            line += f"   [{s.current_word}]"
        self._lbl_line.setText(line)
        self._lbl_time.setText(f"{_fmt(s.position)} / {_fmt(s.duration)}   line {s.line_index + 1}/{s.line_count}")
        self._progress.setValue(int(1000 * s.position / s.duration) if s.duration > 0 else 0)
        # Keep the combo in sync with the loaded song, unless the user is interacting
        if s.song and self._combo.findText(s.song) >= 0 and not self._combo.hasFocus():
            self._combo.setCurrentText(s.song)

    def shutdown_plugin(self) -> None:
        # Clean up ROS entities: the rqt node outlives the plugin
        self._timer.stop()
        self._node.destroy_subscription(self._sub)
        for c in list(self._cli.values()) + [self._cli_load, self._cli_list]:
            self._node.destroy_client(c)


def _fmt(t: float) -> str:
    """Format seconds as mm:ss."""
    t = max(0, int(t))
    return f"{t // 60:02d}:{t % 60:02d}"
