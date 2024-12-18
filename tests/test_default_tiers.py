import os

import pytest # type: ignore[import]

from cassini import DEFAULT_TIERS, Home, FolderTierBase, NotebookTierBase
from cassini.core import Project
from cassini.defaults import WorkPackage, Experiment, Sample, DataSet
from cassini.testing_utils import get_Project, patch_project

@pytest.fixture
def mk_project(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    project.setup_files()
    return project


def test_parse_name(mk_project):
    project = mk_project
    assert WorkPackage.name_part_regex == r'WP(\d+)'
    assert project.parse_name('WP1') == ('1',)
    assert project.parse_name('WP572') == ('572',)

    assert project.parse_name('WP1.2') == ('1', '2')
    assert project.parse_name('WP572.573') == ('572', '573')

    assert project.parse_name('WP1.2c') == ('1', '2', 'c')
    assert project.parse_name('WP572.573foobar3') == ('572', '573', 'foobar3')

    assert project.parse_name('WP1.2c-meas') == ('1', '2', 'c', 'meas')
    assert project.parse_name('WP572.573foobar3-123new to me') == ('572', '573', 'foobar3', '123new to me')

    assert project.parse_name('P572.573foobar3-123new to me') == tuple()
    assert project.parse_name('INVALIDATE WP572.573foobar3-123new to me') == tuple()


def test_get_home(mk_project):
    project = mk_project
    home = project['Home']
    assert home.name == 'Home'
    assert home.exists()

    with pytest.raises(ValueError):
        home = project['foo']


def test_work_package(mk_project):
    project = mk_project

    wp = project['WP1']
    wp.setup_files()

    assert wp.name == 'WP1'
    assert wp.exists()

    with pytest.raises(ValueError):
        exp = wp['a']  # invalid

    exp = wp['1']
    exp.setup_files()

    exp2 = wp['2']
    exp2.setup_files()

    # order may be different depending on caching etc.
    assert set(wp) == set([exp, exp2])
    assert set(wp.exps) == set([exp, exp2])


def test_experiment(mk_project):
    project = mk_project

    wp = project['WP2']
    wp.setup_files()

    exp1 = wp['1']
    exp1.setup_files()

    assert exp1.short_type == 'exp'
    assert exp1.name == 'WP2.1'

    with pytest.raises(ValueError):
        smpl = exp1['1']

    with pytest.raises(ValueError):
        smpl = exp1['-a']

    smpl1 = exp1['a']
    smpl1.setup_files()

    smpl2 = exp1['b']
    smpl2.setup_files()

    assert set(exp1) == set([smpl1, smpl2])
    assert set(exp1.smpls) == set([smpl1, smpl2])

    assert exp1.techniques == []

    exp1.setup_technique('MyTechnique')

    assert exp1.techniques == ['MyTechnique']


def test_sample(mk_project):
    project = mk_project

    wp = project['WP3']
    wp.setup_files()
    exp2 = wp['2']
    exp2.setup_files()

    smpl1 = exp2['c']
    smpl1.setup_files()

    assert smpl1.exists()
    assert smpl1.name == 'WP3.2c'

    dataset1 = smpl1['Data']

    assert not dataset1.exists()

    dataset1.setup_files()

    assert dataset1.exists()

    assert set(smpl1.datasets) == set([dataset1])
    assert set(smpl1) == set([dataset1])


def test_datasets(mk_project):
    project = mk_project

    wp = project['WP4']
    wp.setup_files()
    exp2 = wp['3']
    exp2.setup_files()
    smpl1 = exp2['d']
    smpl1.setup_files()

    dataset = smpl1['Stuff']
    dataset.setup_files()

    with pytest.raises(AttributeError):
        assert dataset.file is None
    
    assert dataset.child_cls is None

    mock_file = dataset / 'nothing.txt'
    mock_file.write_text('test')

    assert list(dataset)[0].path == list(os.scandir(dataset))[0].path
