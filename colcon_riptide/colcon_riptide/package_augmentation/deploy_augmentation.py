# Copyright 2016-2019 Dirk Thomas
# Copyright 2023 Cole Tucker
# Licensed under the Apache License, Version 2.0

from colcon_core.package_augmentation \
    import PackageAugmentationExtensionPoint
from colcon_core.plugin_system import satisfies_version
import os.path

DEPLOY_IGNORE = "DEPLOY_IGNORE"
SQUEAKY_CLEAN = "SQUEAKY_CLEAN"
BUILD_IF_MISSING = "BUILD_ONLY_IF_MISSING"

class DeployIgnorePackageAugmentation(PackageAugmentationExtensionPoint):
    """
    Augment Python packages with information from `setup.cfg` files.

    Only packages which pass no arguments (or only a ``cmdclass``) to the
    ``setup()`` function in their ``setup.py`` file are being considered.
    """

    def __init__(self):  # noqa: D107
        super().__init__()
        satisfies_version(
            PackageAugmentationExtensionPoint.EXTENSION_POINT_VERSION,
            '^1.0')

    def augment_package(  # noqa: D102
        self, desc, *, additional_argument_names=None
    ):
        deploy_ignore = desc.path / DEPLOY_IGNORE
        squeaky_clean = desc.path / SQUEAKY_CLEAN
        build_if_missing = desc.path / BUILD_IF_MISSING
        
        desc.metadata['colcon_deploy_allow'] = not os.path.lexists(str(deploy_ignore))
        desc.metadata['squeaky_clean'] = os.path.lexists(str(squeaky_clean))
        desc.metadata['build_if_missing'] = os.path.lexists(str(build_if_missing))



