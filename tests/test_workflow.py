import time
import datetime
import pytest # type: ignore[import]

from cassini import FolderTierBase, NotebookTierBase, Home
from cassini.testing_utils import get_Project, patch_project


@pytest.fixture
def mk_project(get_Project, tmp_path):
    Project = get_Project

    class MyHome(Home):
        pass

    class Second(NotebookTierBase):
        pass

    class Third(NotebookTierBase):
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

    before = datetime.datetime.now(datetime.timezone.utc)
    second.setup_files()
    after = datetime.datetime.now(datetime.timezone.utc)

    assert before <= second.started <= after
    assert second.exists()
    assert second in home
    assert f"scnd = project.env('{second.name}')" in second.file.read_text()

    assert list(home) == [second]


def test_created_times_unique(mk_project):
    project = mk_project

    home = project['MyHome']

    first = home['3']
    second = home['4']

    first.setup_files()
    time.sleep(0.001)
    second.setup_files()

    assert first.started < second.started


def test_make_child_with_meta(mk_project):
    project: Project = mk_project
    home = project['MyHome']

    child = home['1']

    meta = {'A': 1, 'B': ["🦀"]}

    child.setup_files(meta=meta)

    assert child.meta['A'] == meta['A']
    assert child.meta['B'] == meta['B']

    custom_template_path = project.template_folder / home.child_cls.__name__ / 'custom.tmplt'

    custom_template_path.write_text("{{ scnd.meta['A'] }} {{ scnd.meta['B'] }}")

    child2 = home['2']

    child2.setup_files(template=custom_template_path.relative_to(project.template_folder), meta=meta)

    assert child2.file.read_text(encoding='utf-8') == "1 ['🦀']"
