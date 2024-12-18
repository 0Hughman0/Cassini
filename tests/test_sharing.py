
from pathlib import Path
import datetime
from typing import List, Any

from cassini.sharing import (
    ShareableProject, 
    NoseyPath, 
    SharedTierData, 
    SharedTier, 
    SharedTierGui,
    SharingTier,
    SharedTierCalls, 
    GetChildCall, 
    GetItemCall, 
    TrueDivCall, 
    SharedTierCall,
    ShareableTierType
)
from cassini.testing_utils import get_Project, patch_project
from cassini.magics import hlt
from cassini import DEFAULT_TIERS, env

import pytest
import pydantic


@pytest.fixture
def mk_shared_project(tmp_path):
    shared = tmp_path / 'Shared'

    requires = shared / 'requires'
    requires.mkdir(parents=True)

    for name in ['WP1', 'WP1.1', 'WP1.1a', 'WP1.1a-Data']:
        tier = shared / name
        tier.mkdir()

        frozen = tier / 'frozen.json'
        frozen.write_text('{"base_path": "C:/None", "called": {}}')

        if name == 'WP1.1a-Data':
            continue

        meta = tier / f'{name}.json'
        meta.write_text('{"a": 1}')

    env.project = None
    env.shareable_project = None

    shared_project = ShareableProject(location=shared)
    stier = shared_project['WP1.1']
    return stier, shared_project


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
    shared_project = ShareableProject()
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
    shared_project = ShareableProject()
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


def test_shareble_tier_serialisation():
    class M(pydantic.BaseModel):
        a: ShareableTierType

    m = M(a=SharedTier('name'))
    assert isinstance(m.a, SharedTier)
    assert isinstance(m.model_dump()['a'], SharedTier)
    
    m = M(a=SharingTier('name'))
    assert isinstance(m.a, SharingTier)
    assert isinstance(m.model_dump()['a'], SharingTier)

    assert m.model_validate_json(m.model_dump_json()) == m

    with pytest.raises(pydantic.ValidationError):
        M(a='name')


def test_serialisation(mk_shared_project):
    getitem_call = GetItemCall(args=('3',), kwargs=tuple(), returns=SharedTier('WP1.1a'))
    get_child_call = GetChildCall(args=tuple(), kwargs=(('id', 'hello'),), returns=SharedTier('WP1.1a'))
    truediv_call = TrueDivCall(args=('args',), kwargs=tuple(), returns=Path('returned'))
    
    m = SharedTierData(
        file=Path('a file'),
        folder=Path('a folder'),
        parent=SharedTier('WP1'),
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

    shared_project = ShareableProject()
    stier = shared_project.env('WP1.1')

    assert stier.meta is tier.meta

    tier.description = "new description"

    assert stier.description == "new description"
    assert 'description' in stier.meta.keys()

    tier.conclusion = 'c'

    assert stier.conclusion == 'c'

    now = datetime.datetime.now(datetime.timezone.utc)

    stier.started = now

    assert tier.meta['started'] == now


def test_making_share(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    shared_project = ShareableProject(location=tmp_path / 'shared')
    project.setup_files()

    tier = project['WP1']
    tier.setup_files()
    tier['1'].setup_files()

    tier.description = 'description'
    (tier / 'data.txt').write_text('some data')

    stier = shared_project.env('WP1')

    assert isinstance(stier, SharingTier)

    stier / 'data.txt'
    child = stier['1']
    child_href = child.href

    shared_project.make_shared()

    env.shareable_project = None
    shared_project = ShareableProject(location=tmp_path / 'shared')
    shared_project.project = None

    shared_tier = shared_project.env('WP1')

    assert isinstance(shared_tier, SharedTier)

    assert shared_tier.name == 'WP1'
    assert shared_tier.description == 'description' == tier.description
    
    assert shared_tier['1'].name == child.name
    assert shared_tier['1'].href == child_href
    
    shared_tier.description = 'new description'

    assert shared_tier.description == 'new description'
    assert shared_tier.description != tier.description

    assert shared_tier / 'data.txt' != tier / 'data.txt'
    assert (shared_tier / 'data.txt').read_text() == (tier / 'data.txt').read_text()


def test_no_meta(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    shared_project = ShareableProject(location=tmp_path / 'shared')
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
    shared_project.project = None

    shared_tier = shared_project['WP1.1a-Data']

    assert shared_tier.meta is None
    assert shared_tier / 'data.csv' != tier / 'data.csv'
    assert (shared_tier / 'data.csv').read_text() == (tier / 'data.csv').read_text()    


def test_no_magics(mk_shared_project):
    *_, shared_project = mk_shared_project
    stier = shared_project['WP1.1']

    with pytest.warns(match="shared context"):
        out = hlt('hlt', 'print("cell")')
    
    assert out == 'print("cell")'


def test_getting_tier_children(get_Project, tmp_path):
    Project = get_Project
    project = Project(DEFAULT_TIERS, tmp_path)
    shared_project = ShareableProject(location=tmp_path / 'shared')
    project.setup_files()
    project['WP1'].setup_files()
    project['WP1.1'].setup_files()

    (project['WP1.1'] / 'file').write_text('data')

    stier = shared_project['WP1']
    stier_child = stier['1']

    assert stier_child.exists()
    assert (stier_child / 'file').read_text() == 'data'


def test_shared_gui_header():
    stier = SharedTier('name')
    assert isinstance(stier.gui, SharedTierGui)
    assert stier.gui.header() is None


def test_shared_gui_meta_editor():
    stier = SharedTier('name')
    assert isinstance(stier.gui, SharedTierGui)
    assert stier.gui.meta_editor() is None
    assert stier.gui.meta_editor(['name']) is None