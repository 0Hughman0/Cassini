
from pathlib import Path
import datetime
from typing import List, Any

from cassini.sharing import SharedProject, NoseyPath, SharedTierData, SharedTier, SharedTierCalls, GetChildCall, GetItemCall, TrueDivCall, SharedTierCall
from cassini.testing_utils import get_Project, patch_project
from cassini import DEFAULT_TIERS, env

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


def test_attribute_caching(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    shared_project = SharedProject()
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

    assert stier._accessed['id'] == '1'
    
    assert stier._called['__truediv__'][(('a path',), tuple())] == tmp_path / 'WorkPackages' / 'WP1' / 'a path'
    
    child = stier['5']

    assert child.name == 'WP1.5'
    assert stier._called['__getitem__'][(('5',), tuple())] is child

    child = stier.get_child(id='5')

    assert child.name == 'WP1.5'

    assert stier._called['get_child'][(tuple(), (('id', '5'),))] is child


def test_stier_path_finding(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    shared_project = SharedProject()
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


def test_serialisation(get_Project, tmp_path):
    getitem_call = GetItemCall(args=('3',), kwargs=tuple(), returns='WP1.3')
    get_child_call = GetChildCall(args=tuple(), kwargs=(('id', 'hello'),), returns='WP1.2')
    truediv_call = TrueDivCall(args=('args',), kwargs=tuple(), returns=Path('returned'))
    
    m = SharedTierData(
        file=Path('a file'),
        folder=Path('a folder'),
        parent='WP1',
        href='http://wut',
        id='1',
        identifiers=['1', '1'],
        meta_file=Path('a meta_file'),
        base_path=Path('base path'),
        called=SharedTierCalls(
            get_child=[get_child_call],
            getitem=[getitem_call],
            truediv=[truediv_call]
        )
    )
    
    assert m.file == Path('a file')
    assert m.folder == Path('a folder')
    assert m.meta_file == Path('a meta_file')

    m.file = Path('new file')

    assert m.file == Path('new file')

    with pytest.raises(pydantic.ValidationError):
        m.file = 1

    assert isinstance(m.parent, SharedTier)
    assert m.parent.name == 'WP1'

    with pytest.raises(pydantic.ValidationError):
        m.parent = 1

    # workaround for bug: https://github.com/pydantic/pydantic/issues/10054 !
    m.called = SharedTierCalls(**m.called.model_dump(), my_method=[
        SharedTierCall(args=('a1', 'a2'), kwargs=(('kk1', 'kv1'), ('kk2', 'kv2')), returns=[100])
    ])

    with pytest.raises(pydantic.ValidationError):
        # additional method call return types have to be json values, because they can't be sniffed!
        m.called.my_method2 = [
            SharedTierCall(args=('a1', 'a2'), kwargs=(('kk1', 'kv1'), ('kk2', 'kv2')), returns=Path('path'))
        ]

    assert m == SharedTierData.model_validate_json(m.model_dump_json())

    m2 = SharedTierData.model_validate_json(m.model_dump_json())

    assert isinstance(m2.file, Path)
    assert isinstance(m2.called.truediv[0].returns, Path)
    assert m2.called.my_method[0].returns == [100]


def test_meta_wrapping(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    project.setup_files()

    tier = project['WP1.1']
    tier.parent.setup_files()
    tier.setup_files()

    shared_project = SharedProject()
    stier = shared_project.env('WP1.1')

    assert stier.meta is tier.meta

    tier.description = "new description"

    assert stier.description == "new description"
    assert 'description' in stier.meta.keys()

    tier.conclusion = 'c'

    assert stier.conclusion == 'c'

    now = datetime.datetime.now()

    stier.started = now

    assert tier.meta['started'] == now


def test_making_share(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    shared_project = SharedProject(location=tmp_path / 'shared')
    project.setup_files()

    tier = project['WP1.1']
    tier.parent.setup_files()
    tier.setup_files()

    tier.description = 'description'
    (tier / 'data.txt').write_text('some data')

    stier = shared_project.env('WP1.1')

    stier / 'data.txt'

    shared_project.make_shared()

    shared_project = SharedProject(location=tmp_path / 'shared')
    env.project = None

    shared_tier = shared_project.env('WP1.1')

    assert shared_tier.name == 'WP1.1'
    assert shared_tier.description == 'description' == tier.description
    
    shared_tier.description = 'new description'

    assert shared_tier.description == 'new description'
    assert shared_tier.description != tier.description

    assert shared_tier / 'data.txt' != tier / 'data.txt'
    assert (shared_tier / 'data.txt').read_text() == (tier / 'data.txt').read_text()


def test_no_meta(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    shared_project = SharedProject(location=tmp_path / 'shared')
    project.setup_files()

    project['WP1'].setup_files()
    project['WP1.1'].setup_files()
    project['WP1.1a'].setup_files()
    tier = project['WP1.1a-Data']
    tier.setup_files()

    stier = shared_project['WP1.1a-Data']
    
    with pytest.raises((AttributeError, KeyError)):
        stier.description

    data = stier / 'data.csv'
    data.write_text('some data')

    assert stier.meta is None

    shared_project.make_shared()

    env.project = None

    shared_tier = shared_project['WP1.1a-Data']

    assert shared_tier.meta is None
    assert shared_tier / 'data.csv' != tier / 'data.csv'
    assert (shared_tier / 'data.csv').read_text() == (tier / 'data.csv').read_text()    
