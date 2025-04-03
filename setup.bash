#!/bin/bash

# Default Linux installation doesn't have pip. Install and update for both Python versions for good measure
sudo apt-get install python3-pip --yes
python3 -m pip install --upgrade pip
sudo python3 -m pip install vcstool

#add ubuntu unverise repo
sudo apt install -y software-properties-common
sudo add-apt-repository universe

#add ros2 keys
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

#add ros2 repo to sources list
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

#update
sudo apt update
sudo apt -y upgrade

#install ros2
sudo apt install -y ros-humble-desktop
sudo apt install -y ros-dev-tools

#install colcon
sudo apt install -y python3-colcon-common-extensions


