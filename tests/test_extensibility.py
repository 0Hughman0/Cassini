from unittest.mock import Mock
from typing import Any

from utils import patch_project


def test_setup_files_hook(patch_project):
    Tier, project = patch_project

    home = project.home
    home.exists = lambda: False

    call_order = []

    def stamp_call(label):
        def wrapped(*args, **kwargs):
            call_order.append(label)
        return wrapped

    home.setup_files = Mock(side_effect=stamp_call('home'))

    before_mock = Mock(side_effect=stamp_call('before'))
    after_mock = Mock(side_effect=stamp_call('after'))

    project.__before_setup_files__.append(before_mock)
    project.__after_setup_files__.append(after_mock)
    
    project.setup_files()

    assert before_mock.call_args.args == (project,)
    assert after_mock.call_args.args == (project,)
    assert call_order == ['before', 'home', 'after']


def test_launch_hook(patch_project):
    Tier, project = patch_project
    project.exists = lambda self: False

    call_order = []

    def stamp_call(label):
        def wrapped(*args, **kwargs):
            call_order.append(label)
        return wrapped

    project.setup_files = Mock(side_effect=stamp_call('project'))

    before_mock = Mock(side_effect=stamp_call('before'))
    after_mock = Mock(side_effect=stamp_call('after'))

    project.__before_launch__.append(before_mock)
    project.__after_launch__.append(after_mock)
    
    app = Mock()

    project.launch(app)

    assert before_mock.call_args.args == (project, app)
    assert after_mock.call_args.args == (project, app)
    assert call_order == ['before', 'project', 'after']
