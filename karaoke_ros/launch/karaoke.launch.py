"""Launch the karaoke player, the RViz visualizer, RViz itself and the rqt remote."""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    song = LaunchConfiguration("song")
    autostart = LaunchConfiguration("autostart")
    rviz = LaunchConfiguration("rviz")
    rqt = LaunchConfiguration("rqt")
    rviz_cfg = PathJoinSubstitution(
        [FindPackageShare("karaoke_ros"), "config", "karaoke.rviz"]
    )

    arguments = [
        DeclareLaunchArgument("song", default_value="ros_song.lrc"),
        DeclareLaunchArgument("autostart", default_value="false"),
        DeclareLaunchArgument("rviz", default_value="true"),
        DeclareLaunchArgument("rqt", default_value="true"),
    ]

    nodes = [
        Node(
            package="karaoke_ros",
            executable="player_node",
            name="karaoke_player",
            namespace="karaoke",
            output="screen",
            parameters=[{"song": song, "autostart": autostart}],
            # Relative topic/service names resolve under the namespace:
            # state -> /karaoke/state, play -> /karaoke/play, sing -> /karaoke/sing
        ),
        Node(
            package="karaoke_ros",
            executable="viz_node",
            name="karaoke_viz",
            output="screen",
        ),
        Node(
            package="rviz2",
            executable="rviz2",
            name="rviz2",
            arguments=["-d", rviz_cfg],
            condition=IfCondition(rviz),
        ),
        Node(
            package="rqt_gui",
            executable="rqt_gui",
            name="rqt_karaoke",
            arguments=["--standalone", "karaoke_ros"],
            condition=IfCondition(rqt),
        ),
    ]

    return LaunchDescription([*arguments, *nodes])
