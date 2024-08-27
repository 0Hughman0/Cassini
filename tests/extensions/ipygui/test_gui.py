from unittest.mock import Mock

from cassini.ext import ipygui
from cassini.ext.ipygui.gui import HomeGui, BaseTierGui, ExperimentGui, SampleGui
from cassini.ext.ipygui.components import SearchWidget
from cassini.testing_utils import patched_default_project, get_Project
from cassini import DEFAULT_TIERS, env

import pytest


@pytest.fixture
def patched_ipygui_project(patched_default_project):
    project, make_tiers = patched_default_project

    old_guis = {}

    for cls in project.hierarchy:
        old_guis[cls] = cls.gui_cls

    ipygui.extend_project(project)

    yield project, make_tiers

    for cls in project.hierarchy:
        cls.gui_cls = old_guis[cls]


def test_setting_gui_cls(patched_ipygui_project):
    project, make_tiers = patched_ipygui_project
    Home, WP1, WP1_1, WP1_1a, WP1_1a_A = make_tiers(['Home', 'WP1', 'WP1.1', 'WP1.1a', 'WP1.1a-A'])

    assert isinstance(Home.gui, HomeGui)
    assert isinstance(WP1.gui, BaseTierGui)
    assert isinstance(WP1_1.gui, ExperimentGui)
    assert isinstance(WP1_1a.gui, SampleGui)
    assert isinstance(WP1_1a_A.gui, BaseTierGui)


def test_new_children(patched_ipygui_project):
    project, make_tiers = patched_ipygui_project
    Home, WP1, WP1_1, WP1_1a, WP1_1a_A = make_tiers(['Home', 'WP1', 'WP1.1', 'WP1.1a', 'WP1.1a-A'])

    assert not project['WP1.1a-B'].exists()

    form = WP1_1a.gui.new_child()
    id_input = form.children[0]
    id_input.value = 'B'
    
    make_new_button = form.children[1].children[0]
    make_new_button.click()

    assert project['WP1.1a-B'].exists()

    assert not project['WP2'].exists()

    form = Home.gui.new_child()
    id_input = form.children[0]
    id_input.value = '2'
    make_new_button = form.children[3].children[0]
    make_new_button.click()

    assert project['WP2'].exists()


def test_new_dataset(patched_ipygui_project):
    project, make_tiers = patched_ipygui_project
    WP1_1, WP1_1a = make_tiers(['WP1.1', 'WP1.1a'])

    assert not project['WP1.1a-A'].exists()

    form = WP1_1.gui.new_dataset()
    id_input = form.children[0]
    id_input.value = 'A'

    sample_options = form.children[1]
    sample_options.value = ('WP1.1a',)
    
    make_new_button = form.children[2].children[0]
    make_new_button.click()

    assert project['WP1.1a-A'].exists()


def test_search_widget(patched_ipygui_project, monkeypatch):
    project, make_tiers = patched_ipygui_project
    Home, WP1 = make_tiers(['Home', 'WP1'])

    mock_project = Mock()
    mock_getitem = Mock()
    mock_project.__getitem__ = mock_getitem
    monkeypatch.setattr(env, 'project', mock_project)

    search = SearchWidget()
    search.search.value = 'WP1'
    search.go_btn.click()

    mock_getitem.assert_called_with('WP1')
