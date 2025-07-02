#!/bin/bash

#magic file that builds, translates and configures

cd ~/AMR

#colcon build
colcon build

#launch the path planner
ros2 run amr_central path_planner.py &

#translate the blueprint
ros2 run amr_central translate_blueprint.py --ros-args -p blueprint_filename:=map_a.yaml -p command_list_filename:=command_list.yaml

#configure the launcher
ros2 run amr_launcher configure_for_launch.py

