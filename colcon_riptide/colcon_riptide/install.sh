#!/bin/bash

#install this where it needs to go

#to remove remove, pip uninstall colcon_riptide, pip cache purge, pip list

#to install (cough cough register), pip install -e . (do this in the colcon riptide_directory)
#be sure to 

#to copy the code where it needs to go, run this script (run with superuser permissions)

rm -rf /usr/lib/python3/dist-packages/colcon_riptide

cp -r /home/hollis/AMR/amr_setup/colcon_riptide/colcon_riptide /usr/lib/python3/dist-packages/

