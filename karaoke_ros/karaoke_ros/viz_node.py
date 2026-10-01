"""Visualization node: turns /karaoke/state into a MarkerArray for RViz.

Markers (frame `world`):
  0  current line     TEXT_VIEW_FACING, large, white
  1  current word     TEXT_VIEW_FACING, yellow (if word timing is available)
  2  next line        TEXT_VIEW_FACING, grey
  3  title + time     TEXT_VIEW_FACING, small
  4  progress bar     CUBE
  5  progress bar background  CUBE
"""

from __future__ import annotations

import rclpy
from geometry_msgs.msg import Point, Vector3
from rclpy.node import Node
from std_msgs.msg import ColorRGBA
from visualization_msgs.msg import Marker, MarkerArray

from karaoke_interfaces.msg import PlayerState


def _rgba(r: float, g: float, b: float, a: float = 1.0) -> ColorRGBA:
    return ColorRGBA(r=float(r), g=float(g), b=float(b), a=float(a))


def _fmt(t: float) -> str:
    """Format seconds as mm:ss."""
    t = max(0, int(t))
    return f"{t // 60:02d}:{t % 60:02d}"


class KaraokeViz(Node):
    def __init__(self) -> None:
        super().__init__("karaoke_viz")
        self.declare_parameter("frame_id", "world")
        self.declare_parameter("text_scale", 0.6)
        self.declare_parameter("bar_width", 6.0)
        self.declare_parameter("publish_rate", 15.0)

        self._state = PlayerState()
        self._state.line_index = -1
        self._pub = self.create_publisher(MarkerArray, "/karaoke/markers", 10)
        self.create_subscription(PlayerState, "/karaoke/state", self._on_state, 10)
        # Publish at a fixed rate, decoupled from the player's tick rate
        self.create_timer(1.0 / self.get_parameter("publish_rate").value, self._publish)

    def _on_state(self, msg: PlayerState) -> None:
        self._state = msg

    # ------------------------------------------------------------ markers
    def _text(self, mid: int, text: str, z: float, scale: float, color: ColorRGBA) -> Marker:
        m = Marker()
        m.header.frame_id = self.get_parameter("frame_id").value
        m.header.stamp = self.get_clock().now().to_msg()
        m.ns, m.id = "karaoke", mid  # stable ids: markers are updated in place
        m.type, m.action = Marker.TEXT_VIEW_FACING, Marker.ADD
        m.pose.position = Point(x=0.0, y=0.0, z=z)
        m.pose.orientation.w = 1.0
        m.scale.z = scale  # only scale.z matters for text (letter height)
        m.color = color
        m.text = text if text else " "  # RViz ignores empty text
        return m

    def _bar(self, mid: int, frac: float, color: ColorRGBA, z: float = 0.0) -> Marker:
        """Horizontal bar, left-aligned, filled to `frac` of bar_width."""
        width = self.get_parameter("bar_width").value
        m = Marker()
        m.header.frame_id = self.get_parameter("frame_id").value
        m.header.stamp = self.get_clock().now().to_msg()
        m.ns, m.id = "karaoke", mid
        m.type, m.action = Marker.CUBE, Marker.ADD
        frac = max(0.0, min(1.0, frac))
        length = max(0.01, width * frac)  # zero-size cubes are not rendered
        m.pose.position = Point(x=-width / 2 + length / 2, y=0.0, z=z)
        m.pose.orientation.w = 1.0
        m.scale = Vector3(x=length, y=0.15, z=0.15)
        m.color = color
        return m

    def _publish(self) -> None:
        s = self._state
        scale = self.get_parameter("text_scale").value
        arr = MarkerArray()

        playing = "▶" if s.playing else "❚❚"
        header = f"{playing}  {s.title or s.song or 'No song'}"
        if s.artist:
            header += f" — {s.artist}"
        header += f"   {_fmt(s.position)} / {_fmt(s.duration)}"

        # Dim the current line when paused
        line_color = _rgba(1, 1, 1) if s.playing else _rgba(0.7, 0.7, 0.7)
        arr.markers.append(self._text(0, s.current_line, 1.6, scale, line_color))
        arr.markers.append(self._text(1, s.current_word, 0.9, scale * 0.8, _rgba(1.0, 0.85, 0.1)))
        arr.markers.append(self._text(2, s.next_line, 0.4, scale * 0.5, _rgba(0.5, 0.5, 0.55)))
        arr.markers.append(self._text(3, header, 2.6, scale * 0.4, _rgba(0.4, 0.8, 1.0)))

        frac = s.position / s.duration if s.duration > 0 else 0.0
        arr.markers.append(self._bar(5, 1.0, _rgba(0.2, 0.2, 0.25, 0.6), z=-0.05))
        arr.markers.append(self._bar(4, frac, _rgba(0.2, 0.9, 0.4), z=0.0))
        self._pub.publish(arr)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = KaraokeViz()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
