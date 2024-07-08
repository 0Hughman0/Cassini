import pytest # type: ignore[import]

from cassini import FolderTierBase, NotebookTierBase, Home, Project
from cassini.core import TierABC
from cassini.accessors import _CachedProp


def test_project(tmp_path):
    class First(Home):
        name = "First"

    class Second(NotebookTierBase):
        pass

    project = Project([First, Second], tmp_path)

    with pytest.raises(RuntimeError):
        Project([First, Second], tmp_path)

    assert First.rank == 0
    assert project.rank_map['frst'] == 0

    assert Second.rank == 1
    assert project.rank_map['scnd'] == 1

    assert project.project_folder == tmp_path
    assert project.template_folder == tmp_path / 'templates'

    obj = project['First']

    assert isinstance(obj, First)

    obj = project['Second1']

    assert isinstance(obj, Second)


@pytest.fixture
def patch_project(monkeypatch, tmp_path):
    Project._instance = None

    class Tier(FolderTierBase):
        pass

    project = Project([Home, Tier], tmp_path)
    return Tier, project


def test_home_attr(patch_project):
    Tier, project = patch_project
    home = Home()

    assert home.name == 'Home'
    assert home.pretty_type == 'Home'
    assert home.short_type == 'hm'

    assert home.file == project.project_folder / 'Home.ipynb'


def test_construct(patch_project):
    Tier, project = patch_project

    with pytest.raises(ValueError):
        home = Home('Not Needed')

    with pytest.raises(ValueError):
        tier = Tier()

    with pytest.raises(ValueError):
        tier = Tier('1', '2')

    with pytest.raises(ValueError):
        tier = Tier('l')


def test_tier_attrs(patch_project):
    Tier, project = patch_project

    assert Tier.hierarchy == [Home, Tier]
    assert Tier.pretty_type == 'Tier'
    assert Tier.short_type == 'tr'

    assert Tier.name_part_template == 'Tier{}'
    assert Tier.name_part_regex == r'Tier(\d+)'

    assert Tier.parent_cls is Home
    assert Tier.child_cls is None
    assert Tier.parse_name('Tier1') == ('1',)

    tier = Tier('1')

    assert tier.hierarchy == [Home, Tier]
    assert tier.id == '1'
    assert tier.identifiers == ('1',)
    assert tier.name == 'Tier1'

    assert tier.folder == project.project_folder / 'Tiers' / 'Tier1'
    assert tier.meta_file == project.project_folder / 'Tiers' / '.trs' / 'Tier1.json'
    assert tier.highlights_file == project.project_folder / 'Tiers' / '.trs' / 'Tier1.hlts'
    assert tier.cache_file == project.project_folder / 'Tiers' / '.trs' / 'Tier1.cache'
    assert tier.file == project.project_folder / 'Tiers' / 'Tier1.ipynb'

    assert tier.parent == Home()
    assert tier.hm == Home()

    assert tier.exists() is False

    assert str(tier) == '<Tier "Tier1">'


def test_tier_accessors(patch_project):
    Tier, project = patch_project

    assert isinstance(TierABC.name, _CachedProp)

    assert Tier.pretty_type is Tier.pretty_type

    obj = Tier('1')

    assert obj.name is obj.name

    with pytest.raises(AttributeError):
        obj.name = 'new'

    with pytest.raises(AttributeError):
        obj.pretty_type = 'new'

    with pytest.raises(AttributeError):
        obj.doesnt_have