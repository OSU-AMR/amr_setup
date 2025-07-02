#!/bin/bash

# Default Linux installation doesn't have pip. Install and update for both Python versions for good measure
sudo apt-get install python3-pip --yes
python3 -m pip install --upgrade pip
sudo python3 -m pip install vcstool

#add ubuntu unverise repo
sudo apt-get install -y software-properties-common
sudo add-apt-repository universe

#add ros2 keys
sudo apt-get update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg

#add ros2 repo to sources list
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

#update
sudo apt update
sudo apt -y upgrade

#install ros2
sudo apt-get install -y ros-humble-desktop
sudo apt-get install -y ros-dev-tools

#install apriltag detector
pip install dt-apriltags

#install tf
sudo apt-get install -y ros-humble-tf-transformations

#install vision msgs
sudo apt-get install -y ros-humble-vision-msgs

#install ffmpeg
sudo apt-get install ffmpeg

#install colcon
sudo apt-get install -y python3-colcon-common-extensions

#install zenoh
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
sudo apt update
sudo apt-get install -y ros-humble-rmw-zenoh-cpp 

#install htop
sudo apt-get install htop

sudo apt-get install -y git fakeroot kernel-package

sudo apt-get install -y build-essential libncurses-dev flex bison libssl-dev libelf-dev dwarves




