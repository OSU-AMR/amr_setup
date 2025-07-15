#!/bin/bash

#magic file that builds, translates and configures

#process selected packages
args=("$@")
packages=()
found=0

for arg in "${args[@]}"; do
    if [[ "$found" -eq 1 ]]; then
        if [[ "$arg" == --* ]]; then
            break
        fi
        packages+=("$arg")
    fi
    if [[ "$arg" == "--packages-select" ]]; then
        found=1
    fi
done

#add the packages select string
package_select_str=""
if [[ "$found" -eq 1 ]]; then
    package_select_str="--packages-select"

    for package in "${packages[@]}"; do
        package_select_str+=" $package"
    done
fi

cd ~/AMR

#launch a zenoh router
ros2 run rmw_zenoh_cpp rmw_zenohd &

#colcon build
colcon build $package_select_str

#launch the path planner
ros2 run amr_central path_planner.py &

#translate the blueprint
ros2 run amr_central translate_blueprint.py --ros-args -p blueprint_filename:=map_a.yaml -p command_list_filename:=command_list.yaml

#terminate the zenoh router
pkill rmw_zenohd

#configure the launcher
ros2 run amr_launcher configure_for_launch.py

