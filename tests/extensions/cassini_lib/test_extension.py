import shutil
from pathlib import Path

import pytest
from semantic_version import Version

from cassini import DEFAULT_TIERS, NotebookTierBase

from cassini.ext.cassini_lib import extend_project
from cassini.ext.cassini_lib.import_tools import PatchImporter

from cassini.testing_utils import get_Project


@pytest.fixture
def create_project(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)

    return project


@pytest.fixture
def setup_project(create_project):
    project = create_project
    project = extend_project(project)

    project.setup_files()

    shutil.copytree('tests/extensions/cassini_lib/mock_libraries', project.project_folder / 'cas_lib', dirs_exist_ok=True)

    return project


def test_extend_creates_dir(create_project):
    project = create_project
    project = extend_project(create_project)

    project.setup_files()

    assert (project.project_folder / 'cas_lib').exists()


def test_extend_existing_project(create_project):
    project = create_project
    
    project.setup_files()

    assert not (project.project_folder / 'cas_lib').exists()

    project = extend_project(project)
    project.setup_files()

    assert (project.project_folder / 'cas_lib').exists()


def test_extend_adds_attributes(create_project):
    project = create_project
    project = extend_project(project)

    for Tier in project.hierarchy:
        if issubclass(Tier, NotebookTierBase):
            assert hasattr(Tier, 'cas_lib_version')
            assert hasattr(Tier, 'cas_lib')


def test_cas_lib_version_private(create_project):
    project = create_project
    project = extend_project(project)

    assert project.hierarchy[1].cas_lib_version.cas_field == 'private'


def test_import_init(setup_project):
    project = setup_project
    wp = project['WP1']
    wp.setup_files()
    
    importer = wp.cas_lib()
    
    assert wp.cas_lib_version == Version('0.2.0')
    assert isinstance(importer, PatchImporter)
    
    with pytest.raises(ImportError):
        import module

    with importer:
        import module

        assert module.__version__ == "0.2.0"

        import my_package

        assert my_package.__version__ == "0.2.0"

    
def test_import_force_version(setup_project):
    project = setup_project

    wp = project['WP1']

    importer = wp.cas_lib('0.1.0')

    assert Path(importer.path).name == '0.1.1'

    with importer:
        import module

        assert module.__version__ == "0.1.1"
    
        import my_package

        assert my_package.__version__ == "0.1.1"
