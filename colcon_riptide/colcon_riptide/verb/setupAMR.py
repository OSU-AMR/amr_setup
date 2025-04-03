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

        add_packages_arguments(parser)

        decorated_parser = DestinationCollectorDecorator(parser)
        add_task_arguments(decorated_parser, 'colcon_core.task.deploy')
        self.task_argument_destinations = decorated_parser.get_destinations()
  

    def main(self, *, context):  # noqa: D102

        USERNAME = context.args.username
        HOSTNAME = context.args.hostname

        #copy ssh key
        execute(["ssh-copy-id", f"{USERNAME}@{HOSTNAME}"], True)

        if(execute(["ssh", f"{USERNAME}@{HOSTNAME}", "mkdir", "AMR"], True) == 1):
            wait_for_res = True
            while(wait_for_res):
                user_response = input("This host appears to be setup. Would you like to wipe it and continue? (Y/n)")

                if(user_response == "Y") or  (user_response == "y"):
                    wait_for_res = False

                if(user_response == "N") or  (user_response == "n"):
                    return
            
            #delete and remake the AMR directory
            execute(["ssh", f"{USERNAME}@{HOSTNAME}", "rm", "-rf", "AMR"], True)
            execute(["ssh", f"{USERNAME}@{HOSTNAME}", "mkdir", "AMR"], True)

        execute(['ssh', f"{USERNAME}@{HOSTNAME}", "sudo", "apt", "install", "-y", 'git'], True)

        execute(["ssh", f"{USERNAME}@{HOSTNAME}", "(cd", "AMR", "&&", "git", "clone", "https://github.com/OSU-AMR/amr_setup.git)"], True)

                    


    
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
