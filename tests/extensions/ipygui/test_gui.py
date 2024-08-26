from cassini.ext import ipygui
from cassini.ext.ipygui.gui import HomeGui, BaseTierGui, ExperimentGui, SampleGui
from cassini.testing_utils import patched_default_project, get_Project
from cassini import DEFAULT_TIERS

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
    form.children[0].value = 'B'
    form.children[1].children[0].click()

    assert project['WP1.1a-B'].exists()

    assert not project['WP2'].exists()

    form = Home.gui.new_child()
    form.children[0].value = '2'
    form.children[3].children[0].click()

    assert project['WP2'].exists()

