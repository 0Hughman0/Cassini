from cassini import Home, NotebookTierBase
from cassini.core import Project


import pytest


@pytest.fixture
def get_Project():
    Project._instance = None
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
