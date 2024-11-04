import pytest # type: ignore[import]

from cassini import FolderTierBase, NotebookTierBase, Home
from cassini.core import TierABC
from cassini.accessors import _CachedProp
from cassini.testing_utils import get_Project, patch_project, patched_default_project


def test_project(get_Project, tmp_path):
    Project = get_Project

    class First(Home):
        pretty_type = "First"

    class Second(NotebookTierBase):
        pretty_type = "Second"

    project = Project([First, Second], tmp_path)
    with pytest.raises(RuntimeError):
        Project([First, Second], tmp_path)

    assert project.rank_map[First] == 0

    assert project.rank_map[Second] == 1

    assert project.project_folder == tmp_path
    assert project.template_folder == tmp_path / 'templates'

    obj = project['First']

    assert isinstance(obj, First)

    obj = project['Second1']

    assert isinstance(obj, Second)


def test_home_attr(patch_project):
    Tier, project = patch_project
    home = Home(project=project)

    assert home.name == 'Home'
    assert home.pretty_type == 'Home'
    assert home.short_type == 'hm'

    assert home.folder == project.project_folder / 'Tiers'


def test_construct(patch_project):
    Tier, project = patch_project

    with pytest.raises(ValueError):
        home = Home('Not Needed', project=project)

    with pytest.raises(ValueError):
        tier = Tier(project=project)

    with pytest.raises(ValueError):
        tier = Tier('1', '2', project=project)

    with pytest.raises(ValueError):
        tier = Tier('l', project=project)


def test_tier_attrs(patch_project):
    Tier, project = patch_project

    assert Tier.pretty_type == 'Tier'
    assert Tier.short_type == 'tr'

    assert Tier.name_part_template == 'Tier{}'
    assert Tier.name_part_regex == r'Tier(\d+)'

    tier = Tier('1', project=project)

    assert tier.parent_cls is Home
    assert tier.parent.child_cls is Tier
    assert tier.child_cls is None
    assert tier.parse_name('Tier1') == ('1',)

    assert tier.id == '1'
    assert tier.identifiers == ('1',)
    assert tier.name == 'Tier1'

    assert tier.folder == project.project_folder / 'Tiers' / 'Tier1'
    assert tier.meta_file == project.project_folder / 'Tiers' / '.trs' / 'Tier1.json'
    assert tier.highlights_file == project.project_folder / 'Tiers' / '.trs' / 'Tier1.hlts'
    assert tier.file == project.project_folder / 'Tiers' / 'Tier1.ipynb'

    assert tier.parent == Home(project=project)

    assert tier.exists() is False

    assert str(tier) == '<Tier "Tier1">'


def test_folder_base_requires_pretty_name():
    class MyFolderTier(FolderTierBase):
        pass

    with pytest.raises(AttributeError):
        MyFolderTier.pretty_type
    

def test_notebook_base_requires_pretty_name():
    class MyNotebookTier(NotebookTierBase):
        pass

    with pytest.raises(AttributeError):
        MyNotebookTier.pretty_type
    

def test_tier_accessors(patch_project):
    Tier, project = patch_project

    assert isinstance(TierABC.name, _CachedProp)

    assert Tier.pretty_type is Tier.pretty_type

    obj = Tier('1', project=project)

    assert obj.name is obj.name

    with pytest.raises(AttributeError):
        obj.name = 'new'

    with pytest.raises(AttributeError):
        obj.doesnt_have


def test_meta_attr(patched_default_project):
    project, make_tiers = patched_default_project
    WP1, = make_tiers(['WP1'])

    assert WP1.__class__.started.cas_field == 'core'
    assert WP1.__class__.description.cas_field == 'core'
    assert WP1.__class__.conclusion.cas_field == 'core'
