import pytest

from cassini import TierBase, Home, Project


@pytest.fixture
def mk_project(tmp_path):
    Project._instance = None

    class MyHome(Home):
        pass

    class Second(TierBase):
        pass

    class Third(TierBase):
        pass

    project = Project([MyHome, Second, Third], tmp_path)
    project.setup_files()
    return project


def test_project_setup(mk_project):
    project = mk_project

    home = project['MyHome']

    assert home.exists()
    assert home.file.exists()
    assert home.folder.exists()


def test_make_child(mk_project):
    project = mk_project

    home = project['MyHome']

    assert home['1'] == home.get_child('1')
    second = home['1']

    assert not second.exists()
    assert list(home) == []

    second.setup_files()

    assert second.exists()
    assert second in home
    assert f"scnd = project.env('{second.name}')" in second.file.read_text()

    assert list(home) == [second]
