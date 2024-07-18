from cassini import Home, NotebookTierBase
from cassini.core import Project


import pytest


@pytest.fixture
def patch_project(monkeypatch, tmp_path):
    Project._instance = None

    class Tier(NotebookTierBase):
        pass

    project = Project([Home, Tier], tmp_path)
    return Tier, project
