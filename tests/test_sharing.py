from cassini.sharing import shared_project, NoseyPath
from cassini.testing_utils import get_Project, patch_project
from cassini import DEFAULT_TIERS

from pathlib import Path


def test_nosey_path():
    path = Path('a')
    npath = NoseyPath(path)

    assert npath.__truediv__('b')
    assert npath.absolute()

    assert npath == path

    assert path / 'a' == npath / 'a'

    assert isinstance(path / 'a', Path)
    assert isinstance(npath / 'a', NoseyPath)

    nsub = npath / 'a'
    nsubsub = nsub / 'b'

    assert (path / 'a') in npath._children
    assert (path / 'a' / 'b') in nsub._children


def test_nosey_path_compressing():
    base = Path('base').absolute()
    nbase = NoseyPath(base)

    nbase / 'a'

    assert nbase._unchain() == {'a': {}}
    
    nbase / 'b'

    assert nbase._unchain() == {'a': {}, 'b': {}}

    nbase / 'a' / 'aa'

    assert nbase._unchain() == {'a': {'aa': {}}, 'b': {}}

    nbase / 'b' / 'ba'

    assert nbase._unchain() == {'a': {'aa': {}}, 'b': {'ba': {}}}

    nbase / 'a' / 'aa' / 'aaa'

    assert nbase._unchain() == {'a': {'aa': {'aaa': {}}}, 'b': {'ba': {}}}

    paths = nbase.compress()

    assert paths == [base.joinpath(*['a', 'aa', 'aaa']), base.joinpath(*['b', 'ba'])]

    nbase / 'a'

    paths = nbase.compress()

    assert base / 'a' not in paths

    new_base = NoseyPath.replace_instance(nbase)

    new_base / 'a'

    paths = new_base.compress()

    assert base / 'a' in paths


def test_sharing(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    project.setup_files()

    tier = project['WP1']
    tier.setup_files()
    tier.description = 'a description'

    stier = shared_project.env('WP1')

    assert stier.name == 'WP1'
    assert stier.id == '1'

    base_path = stier / 'a path'
    assert base_path._path == tmp_path / 'WorkPackages' / 'WP1' / 'a path'

    double_path = stier / 'a path' / 'more'

    assert double_path._path == base_path / 'more'
    
    assert stier.description == 'a description'

    assert stier._accessed['name'] == 'WP1'
    assert stier._accessed['id'] == '1'
    assert stier._accessed['description'] == 'a description'
    
    assert stier._called['__truediv__'][('a path',)] == tmp_path / 'WorkPackages' / 'WP1' / 'a path'
    
    child = stier['5']

    assert child.name == 'WP1.5'
    assert child._accessed['name'] == 'WP1.5'
    assert stier._called['__getitem__'][('5',)] is child


def test_stier_path_finding(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    project.setup_files()

    tier = project['WP1.1']
    tier.parent.setup_files()
    tier.setup_files()

    stier = shared_project.env('WP1.1')
    base = tier.folder

    stier / 'a'

    assert base / 'a' in stier.find_paths()

    stier / 'a' / 'aa'

    assert base / 'a' in stier.find_paths()
    assert base / 'a' / 'aa' in stier.find_paths()

    stier.folder / 'b'

    assert base / 'b' in stier.find_paths()

    stier.folder / 'c' / 'cc'

    assert base / 'c' / 'cc' in stier.find_paths()
