from cassini import (
    Home,
    HomeTierBase,
    NotebookTierBase,
    FolderTierBase,
    DEFAULT_TIERS,
    env,
)
from cassini.core import Project, TierABC
from cassini.accessors import _CachedProp, _CachedClassProp


import pytest


ALL_TIERS = [*DEFAULT_TIERS, TierABC, HomeTierBase, FolderTierBase, NotebookTierBase]


@pytest.fixture
def get_Project():
    env.shareable_project = None
    env.project = None

    Project._instance = None
    Project.__before_setup_files__ = []
    Project.__after_setup_files__ = []
    Project.__before_launch__ = []
    Project.__after_launch__ = []

    for cache in env.caches:
        cache.clear()

    return Project


@pytest.fixture
def patch_project(get_Project, tmp_path):
    Project = get_Project

    class Tier(NotebookTierBase):
        pass

    project = Project([Home, Tier], tmp_path)
    return Tier, project
