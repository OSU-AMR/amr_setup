# Copyright 2016-2018 Dirk Thomas
# Copyright 2021 Ruffin White
# Copyright 2022 Cole Tucker
# Copyright 2025 Alex Schuler
# Licensed under the Apache License, Version 2.0
from colcon_core.plugin_system import satisfies_version
from colcon_core.verb import VerbExtensionPoint
from colcon_core.package_selection import get_packages
from colcon_core.package_selection import add_arguments \
    as add_packages_arguments
from colcon_core.argument_parser.destination_collector import \
    DestinationCollectorDecorator
from colcon_core.task import add_task_arguments
from importlib.resources import files

from subprocess import Popen, PIPE, call
from datetime import datetime
from fabric import Connection
import os, stat

HOSTNAME_PREFIXES = ["Robot", "robot"]
HOSTNAME_SUFFIXES = ["wired", "wireless", "Wired", "Wireless"]

class SetupAMRVerb(VerbExtensionPoint):
    """deploys package workspaces."""

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(VerbExtensionPoint.EXTENSION_POINT_VERSION, '^1.0')

    def add_arguments(self, *, parser):  # noqa: D102

        # enforce hostname
        parser.add_argument('hostname')

        # support a configurable username
        parser.add_argument(
            '--username',
            default='dev',
            help='The username to use on login '
                 '(default: ros)'
        )

        parser.add_argument(
            '--update_bashrc_only',
            action='store_true',
            help='The username to use on login '
                 '(default: ros)'
        )

        parser.add_argument(
            '--install_battery',
            action='store_true',
            help='Wether to install the battery spoofer!'
        )

        parser.add_argument(
            '--deploy-list',
            action='store_true',
            help='Wether to deploy to a single host or a list of hosts define in the deploy lists folder'
        )

        add_packages_arguments(parser)

        decorated_parser = DestinationCollectorDecorator(parser)
        add_task_arguments(decorated_parser, 'colcon_core.task.setupAMR')
        self.task_argument_destinations = decorated_parser.get_destinations()
  
    def main(self, *, context):  # noqa: D102

        USERNAME = context.args.username
        HOSTNAME = context.args.hostname
        DEPLOY_LISTS = context.args.deploy_list
        UPDATE_BASHRC_ONLY = context.args.update_bashrc_only
        INSTALL_BATTERY = context.args.install_battery

        sample_bashrc_path = files('colcon_riptide').joinpath("AMR_bashrc")
        sample_rc_local_path = files('colcon_riptide').joinpath("AMR_rc_local")
        can_bringup_script_path = files('colcon_riptide').joinpath("AMR_CAN_bringup")
        battery_install_script = files('colcon_riptide').joinpath("AMR_setup_battery")
        etc_environment_path = files('colcon_riptide').joinpath("AMR_etc_environment")
        generate_zenoh_config_script = files('colcon_riptide').joinpath("AMR_generate_zenoh_config")
        generate_zenoh_config_script_base = files('colcon_riptide').joinpath("AMR_generate_zenoh_config_base")

        targets = [HOSTNAME]
    
        #read the deploy list and set the target
        if(DEPLOY_LISTS == True):
            try:
                list_text = files('colcon_riptide.deploy_lists').joinpath(f'{HOSTNAME}.txt').read_text()
                targets = list_text.split("\n")
            except FileNotFoundError:
                print(f"No file found for deploy lists at {files('colcon_riptide.deploy_lists').joinpath(f'{HOSTNAME}.txt')}")
                return

        for target in targets:

            target_number = getNumberFromHostname(target)
            if(target_number < 0):
                print(f"Failed to get amr number from hostname {target}. Not setting up")
                continue

            #get the hostname environment string
            number_env_str = get_amr_number_env_string(target_number)

            #copy ssh key
            execute(["ssh-copy-id", f"{USERNAME}@{target}"], True)

            #only update the bashrc file then quit
            if(UPDATE_BASHRC_ONLY):
                execute(["scp", sample_bashrc_path, f"{USERNAME}@{target}:.bashrc"], True)

                #copy over the AMR rc local
                execute(["scp", sample_rc_local_path, f"{USERNAME}@{target}:tempfile"], True)
                execute(["ssh", f"{USERNAME}@{target}", "sudo", "mv", "tempfile", "/etc/rc.local"], True)
                execute(["ssh", f"{USERNAME}@{target}", "chmod", "a+x", "/etc/rc.local"], True)

                #copy over the can bringup command
                execute(["scp", can_bringup_script_path, f"{USERNAME}@{target}:tempfile"], True)
                execute(["ssh", f"{USERNAME}@{target}", "sudo", "mv", "tempfile", "/bin/can_up.sh"], True)
                execute(["ssh", f"{USERNAME}@{target}", "chmod", "a+x", "/bin/can_up.sh"], True)

                #copy over ssh environment
                execute(["scp", etc_environment_path, f"{USERNAME}@{target}:tempfile"], True)
                #add the hostname export
                execute(["ssh", f"{USERNAME}@{target}", "echo", f'"{number_env_str}"', ">>", "tempfile"], True)
                execute(["ssh", f"{USERNAME}@{target}", "sudo", "mv", "tempfile", "/etc/environment"], True)
                execute(["ssh", f"{USERNAME}@{target}", "chmod", "a+x", "/etc/environment"], True)

                #copy over the zenoh_config base
                execute(["scp", generate_zenoh_config_script_base, f"{USERNAME}@{target}:AMR/amr_config_zenoh_base.json"], True)
                execute(["ssh", f"{USERNAME}@{target}", "chmod", "a+rw", "AMR/amr_config_zenoh_base.json"], True)

                #copy over the zenoh_config generator
                execute(["scp", generate_zenoh_config_script, f"{USERNAME}@{target}:AMR/generate_zenoh_config.sh"], True)
                execute(["ssh", f"{USERNAME}@{target}", "chmod", "a+x", "AMR/generate_zenoh_config.sh"], True)

                continue
            
            if(execute(["ssh", f"{USERNAME}@{target}", "mkdir", "AMR"], True) == 1):
                wait_for_res = True
                while(wait_for_res):
                    user_response = input("This host appears to be setup. Would you like to wipe it and continue? (y/N)")

                    if(user_response == "Y") or  (user_response == "y"):
                        wait_for_res = False

                    if(user_response == "N") or  (user_response == "n"):
                        continue

                    if(user_response == ""):
                        continue
                
                #delete and remake the AMR directory
                execute(["ssh", f"{USERNAME}@{target}", "rm", "-rf", "AMR"], True)
                execute(["ssh", f"{USERNAME}@{target}", "mkdir", "AMR"], True)

            #install git
            execute(['ssh', f"{USERNAME}@{target}", "sudo", "apt", "install", "-y", 'git'], True)

            #copy over the AMR bashrc
            execute(["scp", sample_bashrc_path, f"{USERNAME}@{target}:.bashrc"], True)

            #copy over the AMR rc local
            execute(["scp", sample_rc_local_path, f"{USERNAME}@{target}:tempfile"], True)
            execute(["ssh", f"{USERNAME}@{target}", "sudo", "mv", "tempfile", "/etc/rc.local"], True)
            execute(["ssh", f"{USERNAME}@{target}", "chmod", "a+x", "/etc/rc.local"], True)

            #copy over the can bringup command
            execute(["scp", can_bringup_script_path, f"{USERNAME}@{target}:tempfile"], True)
            execute(["ssh", f"{USERNAME}@{target}", "sudo", "mv", "tempfile", "/bin/can_up.sh"], True)
            execute(["ssh", f"{USERNAME}@{target}", "chmod", "a+x", "/bin/can_up.sh"], True)

            #clone amr setup repo
            execute(["ssh", f"{USERNAME}@{target}", "(cd", "AMR", "&&", "git", "clone", "https://github.com/OSU-AMR/amr_setup.git)"], True)

            #install the setup script from the github
            execute(["ssh", f"{USERNAME}@{target}", "sudo", "AMR/amr_setup/setup.bash"], True)

        for target in targets:

            #if the user wants to install the abttery
            if(INSTALL_BATTERY):

                #copy over the battery install script
                execute(["scp", battery_install_script, f"{USERNAME}@{target}:install_battery.sh"], True)
                execute(["ssh", f"{USERNAME}@{target}", "chmod", "a+x", "install_battery.sh"], True)
                execute(["ssh", f"{USERNAME}@{target}", "./install_battery.sh"], True)

def getNumberFromHostname(hostname):
    #parse target number from  the given hostname

    for prefix in HOSTNAME_PREFIXES:
        if prefix in HOSTNAME_SUFFIXES:
            print("A host name prefix is a host name suffix. This is not allowed!")
            return -1
        
    #find the prefix
    found_prefix = ""
    for prefix in HOSTNAME_PREFIXES:
        if prefix in hostname:
            found_prefix = prefix
            break

    if(found_prefix == ""):
        print(f"Please use a valid prefix at the begining at the AMR hostname. Choose from {HOSTNAME_PREFIXES}.")
        print(f"Valid hostname format PREFIX#SUFFIX. # is a valid positive integer!")
        return -1
    
    #find the suffix
    found_suffix = ""
    for suffix in HOSTNAME_SUFFIXES:
        if suffix in hostname:
            found_suffix = suffix
            break

    if(found_suffix == ""):
        print(f"Please use a valid suffix at the begining at the AMR hostname. Choose from {HOSTNAME_SUFFIXES}.")
        print(f"Valid hostname format PREFIX#SUFFIX. # is a valid positive integer!")
        return -1
    
    #split off the prefix
    number_str = ""
    try:
        suffix_str = hostname.split(prefix)[1]

        #split off the suffix
        number_str = suffix_str.split(suffix)[0]
    except:
        print(f"Failed to parse hostname: {hostname} to AMR number.")
        return -1
    
    
    try:
        number = int(number_str)

        return number
    
    except:

        print(f"Failed to parse hostname number {number_str}")

    return -1

def get_amr_number_env_string(amr_number):
    #get the string to add to the /etc/environment to set the amr chassis number based on the hostname
    return f"\nAMR_CHASSIS_NUMBER={amr_number}\n"

def execute(fullCmd, printOut=False):
    if printOut: print(fullCmd)
    proc = Popen(fullCmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    if printOut:
        for line in iter(proc.stdout.readline, ""):
            print(line)
        for errLine in iter(proc.stderr.readline, ""):
            print(f"ERROR: {errLine}")
    proc.stdout.close()
    retCode = proc.wait()
    return retCode

def xferDir(localdir, username, address, destination):
    execute(["rsync", "-vrzc", "--delete", "--exclude=**/.git/",
             "--exclude=**/.vscode/", localdir, 
             f"{username}@{address}:{destination}"], False)

def downloadDir(remotedir, username, address, destination):
    execute(["rsync", "-vrzc", "--delete", "--exclude=**/.git/",
             "--exclude=**/.vscode/", 
             f"{username}@{address}:{remotedir}", destination], False)

