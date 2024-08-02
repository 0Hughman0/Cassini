
from pathlib import Path
import datetime

from cassini.sharing import shared_project, NoseyPath, SharedTierData, SharingTier
from cassini.testing_utils import get_Project, patch_project
from cassini import DEFAULT_TIERS

import pytest
import pydantic


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


def test_making_share(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    project.setup_files()

    tier = project['WP1.1']
    tier.parent.setup_files()
    tier.setup_files()

    tier.description = 'description'
    (tier / 'data.txt').write_text('some data')

    stier = shared_project.env('WP1.1')

    stier / 'data.txt'

    shared_project.make_shared(tmp_path / Path('WP1.1share'), [stier])

    pass


def test_serialisation():
    
    m = SharedTierData(
        name='WP1.1',
        conclusion='a conclusion',
        description='a description',
        file=Path('a file'),
        folder=Path('a folder'),
        parent='WP1',
        href='http://wut',
        id='1',
        identifiers=['1', '1'],
        meta_file=Path('a meta_file'),
        started=datetime.datetime.now(),
        called={'get_child': {}, 'getitem': {}, 'truediv': {}}
    )

    assert m.name == 'WP1.1'
    
    assert m.file == Path('a file')
    assert m.folder == Path('a folder')
    assert m.meta_file == Path('a meta_file')

    m.file = Path('new file')

    assert m.file == Path('new file')

    with pytest.raises(pydantic.ValidationError):
        m.file = 1

    assert isinstance(m.parent, SharingTier)
    assert m.parent._name == 'WP1'

    with pytest.raises(pydantic.ValidationError):
        m.parent = 1

    assert m == SharedTierData.model_validate_json(m.model_dump_json())

    m.called.get_child = {('WP1.1',): 'WP1.1'}

    with pytest.raises(pydantic.ValidationError):
        # expecting a string!
        m.called.get_child = {('WP1.1',): SharingTier('WP1.1')}
