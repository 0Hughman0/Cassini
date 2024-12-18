from unittest.mock import Mock

from cassini.migrate.__main__ import main
from cassini.migrate.V0_2toV0_3 import V0_2toV0_3
from cassini import env

import pytest


@pytest.fixture
def mock_migrator(monkeypatch):
    mock_project = Mock()
    mock_project.home = []

    mock_find_project = Mock()

    env.project = mock_project

    return mock_project, mock_find_project


def test_migrate_selection(mock_migrator):
    migrator = main(['0.2', '0.3'])

    assert isinstance(migrator, V0_2toV0_3)

    # A bit tricky to test...
    """
    with pytest.raises(Exception):
        migrator = main(['0.1', '0.3'])
    """
