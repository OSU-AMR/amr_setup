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

class Command(VerbExtensionPoint):
    """deploys package workspaces."""

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(VerbExtensionPoint.EXTENSION_POINT_VERSION, '^1.0')

    def add_arguments(self, *, parser):  # noqa: D102

        # enforce hostname
        parser.add_argument('hostname')

        parser.add_argument('command',
            help="Command to be run on multiple devices"
        )

        # support a configurable username
        parser.add_argument(
            '--username',
            default='dev',
            help='The username to use on login '
                 '(default: ros)'
        )

        parser.add_argument(
            '--deploy-list',
            action='store_true',
            help='Wether to deploy to a single host or a list of hosts define in the deploy lists folder'
        )

        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Wether or not to print command out put to console'
        )

        parser.add_argument(
            '--very-verbose',
            action='store_true',
            help='Wether or not to print command'
        )

        add_packages_arguments(parser)

        decorated_parser = DestinationCollectorDecorator(parser)
        add_task_arguments(decorated_parser, 'colcon_core.task.command')
        self.task_argument_destinations = decorated_parser.get_destinations()

    def main(self, *, context):  # noqa: D102

        USERNAME = context.args.username
        HOSTNAME = context.args.hostname
        COMMAND = context.args.command
        DEPLOY_LISTS = context.args.deploy_list
        VERBOSE = context.args.verbose
        VERY_VERBOSE = context.args.very_verbose

        #make sure verbose if true if very verbose is true
        if(VERY_VERBOSE):
            VERBOSE = True

        targets = [HOSTNAME]
    
        #read the deploy list and set the target
        if(DEPLOY_LISTS == True):
            try:
                list_text = files('colcon_riptide.deploy_lists').joinpath(f'{HOSTNAME}.txt').read_text()
                targets = list_text.split("\n")
            except FileNotFoundError:
                print(f"No file found for deploy lists at {files('colcon_riptide.deploy_lists').joinpath(f'{HOSTNAME}.txt')}")
                return
            
        #try to find the command in the saved files
        try:
            command_text = files('colcon_riptide.commands').joinpath(f'{COMMAND}.txt').read_text()
            command_lines = command_text.split("\n")
        except:
            command_lines = COMMAND.split("\n")

        #error code state for deploy log
        results = dict()

        for target in targets:

            # test connection to target
            ret_code = testNetwork(target)
            if ret_code != 0:
                print(f"Failed to ping {HOSTNAME}. Hostname unknown, or device offline")

                #add failure state to result log
                results[target] = "Failure Could Not Find Host"

                continue


            for line in command_lines:

                #ignore if a comment
                line = line.split("#")[0]

                #ignore if exmpty
                if(line == ""):
                    continue

                #install the setup script from the github
                if(execute(["ssh", f"{USERNAME}@{target}", line], VERBOSE, VERY_VERBOSE)):
                    results[target] = "Failed with Ret Code 1 - Please see output above"

                else:
                    results[target] = "Command Successfully Sent"

        #print out the log of the results
        print(f"\n\n*******************************************************************")
        print(f"Deploy action finished on {len(results)} target: ")
        for target in results.keys():
            print(f"    {target} ->>> {results[target]}")
        print(f"*******************************************************************\n\n")

    
def execute(fullCmd, print_output, printOut):
    if printOut: print(fullCmd)
    proc = Popen(fullCmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)
    if printOut:
        for line in iter(proc.stdout.readline, ""):
            if(print_output):
                print(line)
        for errLine in iter(proc.stderr.readline, ""):
            print(f"ERROR: {errLine}")
    proc.stdout.close()
    retCode = proc.wait()
    return retCode

def testNetwork(pingAddress):
    return call(["ping", "-c", "1", pingAddress], stdout=open(os.devnull, 'wb'))

