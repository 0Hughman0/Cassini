from cassini import (
    Home,
    HomeTierBase,
    NotebookTierBase,
    FolderTierBase,
    DEFAULT_TIERS,
    env,
)
from cassini.core import Project, TierABC

import pytest


ALL_TIERS = [*DEFAULT_TIERS, TierABC, HomeTierBase, FolderTierBase, NotebookTierBase]


@pytest.fixture
def get_Project():
    """
    Get a clean version of the Project class, with caches and other class attributes appropriately reset.
    """
    env._reset()

    Project.__before_setup_files__ = []
    Project.__after_setup_files__ = []
    Project.__before_launch__ = []
    Project.__after_launch__ = []

    return Project


@pytest.fixture
def patch_project(get_Project, tmp_path):
    Project = get_Project

    class Tier(NotebookTierBase):
        pass

    project = Project([Home, Tier], tmp_path)
    return Tier, project
