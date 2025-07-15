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

ACTION_PACKAGE = "amr_roboware"
ACTION_DEPLOY_DIR = f"install/{ACTION_PACKAGE}/lib/{ACTION_PACKAGE}"

class DeployVerb(VerbExtensionPoint):
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

        # support a configurable remote dir
        parser.add_argument(
            '--remote_dir',
            default='~/colcon_deploy',
            help='The remote directory to transfer files to '
                 '(default: ~/colcon_deploy)'
        )

        # support a clean build on the other end
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Removes the workspace dirs on the target'
        )

        # support skipping the remote build
        parser.add_argument(
            '--no_build',
            action='store_true',
            help='Skips the remote build step'
        )

        # support archiving the remote build
        parser.add_argument(
            '--archive',
            action='store_true',
            help='Creates a tar archive of the build on the target and saves it to the host'
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

        parser.add_argument(
            '--actions',
            action='store_true',
            help='Only deploy action files'
        )

        parser.add_argument(
            '--action_directoy',
            default='src/actions',
            help='specify the '
        )


        add_packages_arguments(parser)

        decorated_parser = DestinationCollectorDecorator(parser)
        add_task_arguments(decorated_parser, 'colcon_core.task.deploy')
        self.task_argument_destinations = decorated_parser.get_destinations()
  

    def main(self, *, context):  # noqa: D102

        USERNAME = context.args.username
        REMOTE_DIR = context.args.remote_dir
        HOSTNAME = context.args.hostname
        WANT_CLEAN = context.args.clean
        NO_BUILD = context.args.no_build
        WANT_ARCHIVE = context.args.archive
        DEPLOY_LISTS = context.args.deploy_list
        VERBOSE = context.args.verbose
        VERY_VERBOSE = context.args.very_verbose
        ACTIONS_ONLY = context.args.actions
        ACTION_SUBDIR = context.args.action_directoy

        REM_SRC_DIR = os.path.join(REMOTE_DIR, "src")

        # the remote directories to clean when cleaning
        REM_DIRS_FOR_CLEAN = [
            os.path.join(REMOTE_DIR, "install"),
            os.path.join(REMOTE_DIR, "build"),
            os.path.join(REMOTE_DIR, "log")
        ]

        targets = [HOSTNAME]
    
        #read the deploy list and set the target
        if(DEPLOY_LISTS == True):
            try:
                list_text = files('colcon_riptide.deploy_lists').joinpath(f'{HOSTNAME}.txt').read_text()
                targets = list_text.split("\n")
            except FileNotFoundError:
                print(f"No file found for deploy lists at {files('colcon_riptide.deploy_lists').joinpath(f'{HOSTNAME}.txt')}")
                return


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

            # make sure the remote directory exists
            makeRemoteDir(REMOTE_DIR, USERNAME, target)

            if(ACTIONS_ONLY):
                try:
                    print("Syncing action files")

                    decorators = get_packages(
                        context.args,
                        additional_argument_names=self.task_argument_destinations,
                        # recursive_categories=('run', )
                    )

                    action_package = None
                    for package in decorators:
                        if(package.descriptor.name == ACTION_PACKAGE):
                            action_package = package
                            break

                    if(action_package is None):
                        print(f"Couldn't find package: {ACTION_PACKAGE}")
                        results[target] = "Action deploy failure"
                        continue

                    action_dir = os.path.join(action_package.descriptor.path, ACTION_SUBDIR)
                    deploy_dir = os.path.join(REM_SRC_DIR, "..", ACTION_DEPLOY_DIR)

                    xferDir(action_dir, USERNAME, target, deploy_dir)

                    results[target] = "Action deploy success!"
                    continue

                except KeyError as e:
                    print(f"Couldn't find package: {e}")

                results[target] = "Action deploy failure"
                continue


            # make sure we're not cleaning the entire directory
            if WANT_CLEAN:
                print("Cleaning remote directories")
                for dir in REM_DIRS_FOR_CLEAN:
                    delRemoteDir(dir, USERNAME, target)

            # attempt an rsync for the current directory to the target dir
            print("Synchronizing local packages to target")
            decorators = get_packages(
                context.args,
                additional_argument_names=self.task_argument_destinations,
                # recursive_categories=('run', )
            )

            # grab out the descriptors from each package as we are only building 
            # on the target and not the host

            packages_for_xfer = [package.descriptor for package in decorators if 
                package.selected and package.descriptor.metadata["colcon_deploy_allow"]]

            for package in packages_for_xfer:

                #handle packages that should only be rebuilt if it is missing - looking at you micro-ros agent
                if(package.metadata["build_if_missing"]):
                    #check if the target build and install directories exist on the remote device
                    pkg_install = os.path.join(REMOTE_DIR, "install", package.name)
                    pkg_build = os.path.join(REMOTE_DIR, "build", package.name)

                    if(check_path(pkg_build, USERNAME, target) and check_path(pkg_install, USERNAME, target)):
                        #no need to rebuild at all
                        packages_for_xfer.remove(package)

                #handle packages that need clean build everytime -> looking at you roboware
                if(package.metadata["squeaky_clean"]):
                    pkg_install = os.path.join(REMOTE_DIR, "install", package.name)
                    pkg_build = os.path.join(REMOTE_DIR, "build", package.name)
                    pkg_log = os.path.join(REMOTE_DIR, "log", package.name)

                    #delete the remote directory
                    delRemoteDir(pkg_install, USERNAME, target)
                    delRemoteDir(pkg_build, USERNAME, target)
                    delRemoteDir(pkg_log, USERNAME, target)

            # make sure the remote source directory exists
            makeRemoteDir(REM_SRC_DIR, USERNAME, target)

            # show packages for xfer to the user
            packages_to_build = []
            print("Selected packages:")
            if len(packages_for_xfer) == 0:
                print("\tNo packages selected")

                #add failure state to result log
                results[target] = "Failure with no Selected Packages"
                continue
            else:
                for descriptor in packages_for_xfer:
                    print(f"\t{descriptor.name}")
                    packages_to_build.append(descriptor.name)
                print("\n\n")

            # get exlpicitly the package paths
            xfered = 0
            try:
                for descriptor in packages_for_xfer:
                    print(f"Synchronizing >>> {descriptor.name}")
                    xferDir(descriptor.path, USERNAME, target, REM_SRC_DIR)

                    xfered += 1
            except Exception as e:
                print(f"Error synchronizing {descriptor.name}")
            
            # check that all were transferred
            if xfered != len(packages_for_xfer):
                print(f"Synchronized {xfered} of {len(packages_for_xfer)} packages")
                print(f"Failed to synchronize {len(packages_for_xfer) - xfered} of {len(packages_for_xfer)} packages")

                #add failure state to result log
                results[target] = "Faiulure Synchronizing Packages"
                continue

            print(f"Synchronized {xfered} of {len(packages_for_xfer)} packages")

            # if no build, we are done
            if NO_BUILD:
                #add failure state to result log
                results[target] = "Success without Build"
                continue

            # Now lets do a remote build
            print("\n\nExecuting remote build")

            arch_name = ""
            
            # detect if it is a clean build as everything needs to re-build
            if WANT_CLEAN:
                arch_name = createAndSendBuildScript(USERNAME, target, REMOTE_DIR, 
                    ["/opt/ros/humble/setup.bash"], [], WANT_ARCHIVE)

            else:
                arch_name = createAndSendBuildScript(USERNAME, target, REMOTE_DIR, 
                    ["/opt/ros/humble/setup.bash"], packages_to_build, WANT_ARCHIVE)

            # run the actual build
            build_status = remoteExec("/bin/bash /tmp/deploy_build.bash", USERNAME, target, True)

            # make sure build is good
            if build_status != 0:
                # dont need a error message as colcon prints from the remote
                #add failure state to result log
                results[target] = "Failed with Build Failure"
                continue

            if WANT_ARCHIVE:
                print(f"Downloading archive {arch_name}")

                # copy the file to the CWD
                work_dir = os.getcwd()

                downloadDir(arch_name, USERNAME, target, work_dir)

                local_path = os.path.join(work_dir, arch_name[arch_name.index('/') + 1 : ])

                print(f"Archive downloaded to {local_path}")

            #add failure state to result log
            results[target] = "Success with Build"

            #attempt to run the blueprint translator command
            translate_status = glorious_remote_execute(USERNAME, target, "ros2 run amr_central translate_blueprint.py --ros-args -p blueprint_filename:=map_a.yaml -p command_list_filename:=command_list.yaml -p ignore_gui:=True -p configure_cfm:=False", VERBOSE, VERY_VERBOSE)

            if(translate_status != 0):
                results[target] += " & and translate failure"
                continue
            
            results[target] += " & and translate success"

            #attempt to run the launch configurator file
            configure_status = glorious_remote_execute(USERNAME, target, 'ros2 run amr_launcher configure_for_launch.py',  VERBOSE, VERY_VERBOSE)

            if(configure_status != 0):
                results[target] += " & and launch configuration failure"
                continue
            
            results[target] += " & and launch configuration success"

        #print out the log of the results
        print(f"\n\n*******************************************************************")
        print(f"Deploy action finished on {len(results)} target: ")
        for target in results.keys():
            print(f"    {target} ->>> {results[target]}")
        print(f"*******************************************************************\n\n")


        print("You should reboot the AMRs now :)")

def execute(fullCmd, print_output=False, printOut=False):
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

def execute_with_output(fullCmd, printOut=False):
    output = ""

    if printOut: print(fullCmd)
    proc = Popen(fullCmd, stdout=PIPE, stderr=PIPE, universal_newlines=True)

    for line in iter(proc.stdout.readline, ""):
        output += line
    for errLine in iter(proc.stderr.readline, ""):
        print(f"ERROR: {errLine}")
    
    proc.stdout.close()
    retCode = proc.wait()
    return retCode, output

def xferDir(localdir, username, address, destination):
    execute(["rsync", "-vrzc", "--delete", "--exclude=**/.git/",
             "--exclude=**/.vscode/", localdir, 
             f"{username}@{address}:{destination}"], False)

def downloadDir(remotedir, username, address, destination):
    execute(["rsync", "-vrzc", "--delete", "--exclude=**/.git/",
             "--exclude=**/.vscode/", 
             f"{username}@{address}:{remotedir}", destination], False)

def testNetwork(pingAddress):
    return call(["ping", "-c", "1", pingAddress], stdout=open(os.devnull, 'wb'))

def remoteExec(cmd, username, address, printOut=False, passwd=""):
    connect = Connection(f"{username}@{address}")
    result = 0
    try:
        result = connect.run(cmd, hide=(not printOut)).exited
    except Exception as e:
        return -1
    return result

def makeRemoteDir(remoteDir, username, address):
    remoteExec(f"mkdir -p {remoteDir}", username, address, False)

def delRemoteDir(remoteDir, username, address):
    remoteExec(f"rm -rf {remoteDir}", username, address, False)

def check_path(remoteDir, username, address):
    #check to see if a directory exists on a remote device
    _, output = execute_with_output(["ssh", f"{username}@{address}", f'[ -d {remoteDir} ] && echo exists || echo does_not_exist'], False)

    if(output == "exists\n"):
        return True
    
    return False

def createAndSendBuildScript(username, hostname, remote_dir, source_files, packages, want_archive):
    DEPLOY_TEMPLATE = """
    #!/bin/bash

    # Make sure build dir exists
    if [ ! -d {0} ]; then 
        echo "Build called on a non-existant directory"
        exit -2
    fi

    # files to source
    {1}

    # switch directory
    cd {0}

    # run the build
    colcon build {2} {3}

    # guard archive against build failure
    if [ $? -ne 0 ]; then
        exit -3
    fi

    # if we want to, also build the archive
    {4}
    """

    sources = ""
    for file in source_files:
        sources += f"source {file}\n"

    # make sure there are entries in the list otherwise do it all
    packages_to_build = ""
    if len(packages) > 0:
        packages_to_build = "--packages-select "
        for package in packages:
            packages_to_build += f"{package} "
            
    cmake_args = "--cmake-args -DBUILD_DEPLOY=ON" #set the BUILD_DEPLOY flag to indicate to packages that this is a deploy build

    # make the archive command
    archive_cmd = ""
    arch_name = ""
    if want_archive:
        # figure out file names
        dir_name = remote_dir[remote_dir.index('/') + 1 : ]
        stamp = datetime.now().strftime("%b_%d_%Y_%H_%M_%S")
        arch_name = f"/tmp/{hostname}_{dir_name}_{stamp}.tar.gz"

        # build the archiive commands for bash
        archive_cmd += "printf '\n\nArchiving build\n'\n"
        archive_cmd += f"tar cf - . | gzip > {arch_name}\n"
        archive_cmd += "echo 'Done'"

    # write the template
    local_script_path = "/tmp/deploy_build.bash"
    with open(local_script_path, "w") as file1:
        # Writing data to a file
        formatted_template = DEPLOY_TEMPLATE.format(remote_dir, sources, packages_to_build, cmake_args, archive_cmd)
        file1.write(formatted_template)

    # make the template executable
    st = os.stat(local_script_path)
    os.chmod(local_script_path, st.st_mode | stat.S_IEXEC)

    # transfer the script
    xferDir(local_script_path, username, hostname, local_script_path)
    return arch_name

def glorious_remote_execute(user_name, target, command, is_verbose, is_very_verbose):
    return execute(["ssh", f"{user_name}@{target}", "source /opt/ros/humble/setup.bash; source ~/colcon_deploy/install/setup.bash; " + command], is_verbose, is_very_verbose)