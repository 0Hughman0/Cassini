from unittest.mock import Mock


from cassini import DEFAULT_TIERS, FolderTierBase, NotebookTierBase
import cassini.jlgui
from cassini.jlgui import JLGui
from cassini.testing_utils import patch_project, get_Project


def test_defaults_have_jl_gui():
    for Tier in DEFAULT_TIERS:
        assert Tier.gui_cls is JLGui


def test_folder_inherited_have_jl_gui():
    class Tier(FolderTierBase):
        pass

    assert Tier.gui_cls is JLGui


def test_notebook_tier_inherited_have_jlgui():
    class Tier(NotebookTierBase):
        pass 

    assert Tier.gui_cls is JLGui


def test_gui_instance_made(patch_project):
    Tier, Project = patch_project
    tier1 = Project['Tier1']
    assert isinstance(tier1.gui, JLGui)


def test_gui_instance_passed_tier(patch_project):
    Tier, Project = patch_project
    tier1 = Project['Tier1']
    assert tier1.gui.tier is tier1
    

def test_gui_header(monkeypatch):
    mock = Mock()
    monkeypatch.setattr(cassini.jlgui, 'publish_display_data', mock)
    gui = JLGui(None)
    gui.header()
    assert mock.called_with({"application/cassini.header+json": {}})


def test_meta_editor_single_key(monkeypatch):
    mock = Mock()
    monkeypatch.setattr(cassini.jlgui, 'publish_display_data', mock)
    gui = JLGui(None)
    gui.meta_editor('key')
    assert mock.call_args.args == ({"application/cassini.metaeditor+json": {"values": ["key"]}},)


def test_meta_editor_multi_key(monkeypatch):
    mock = Mock()
    monkeypatch.setattr(cassini.jlgui, 'publish_display_data', mock)
    gui = JLGui(None)
    gui.meta_editor(['key1', 'key2'])
    assert mock.call_args.args == ({"application/cassini.metaeditor+json": {"values": ['key1', 'key2']}},)
