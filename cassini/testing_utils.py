from typing import Sequence, Tuple, Callable

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
    A pytest fixture that gets a clean version of the Project class, with caches and other class attributes appropriately reset.
    """
    env._reset()

    Project.__before_setup_files__ = []
    Project.__after_setup_files__ = []
    Project.__before_launch__ = []
    Project.__after_launch__ = []

    return Project


@pytest.fixture
def patch_project(get_Project, tmp_path):
    """
    A pytest fixture that returns a simple preconfigured `project`.
    """
    Project = get_Project

    class Tier(NotebookTierBase):
        pretty_type = "Tier"

    project = Project([Home, Tier], tmp_path)
    return Tier, project


@pytest.fixture
def patched_default_project(
    get_Project, tmp_path
) -> Tuple[Project, Callable[[Sequence[str]], Sequence[TierABC]]]:
    """
    A pytest fixture that provides a factory for setting up a project with the default configuration.

    Returns
    -------
    project: Project
        The fresh project instance.
    create_tiers: Callable[[Sequence[str]], Sequence[TierABC]]
        function for creating tiers by a list of names. Returns each pre-setup tier in order.

    Example
    -------
    ```python

    def test_something(patched_default_project):
        project, make_tiers = patched_default_project
        WP1, = make_tiers(['WP1'])
    ```
    """
    Project = get_Project

    project = Project(DEFAULT_TIERS, tmp_path)
    project.setup_files()

    def create_tiers(names: Sequence[str]) -> Sequence[TierABC]:
        """
        Provide a list of tiers.

        These tiers will be created in order and all their files will be setup.
        """
        tiers = []

        for name in names:
            tier = project[name]

            parent = tier

            parents = []

            while parent:
                parents.append(parent)
                parent = parent.parent

            for child in reversed(parents):  # work from top down
                try:
                    child.setup_files()
                except FileExistsError:
                    pass

            tiers.append(tier)

        return tiers

    return project, create_tiers
