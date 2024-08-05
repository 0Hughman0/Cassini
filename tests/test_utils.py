import shutil
import os
from unittest.mock import MagicMock
import itertools
import importlib
import sys

import pytest
from cassini import env, Project
from cassini.utils import find_project


CWD = os.getcwd()


@pytest.fixture
def refresh_project():
    def wrapped():
        Project._instance = None
        env.project = None

        if 'project' in sys.modules:
            del sys.modules['project']
        if 'my_project' in sys.modules:
            del sys.modules['my_project']
    
        importlib.invalidate_caches()

        if os.environ.get('CASSINI_PROJECT'):
            del os.environ['CASSINI_PROJECT']

    return wrapped


def test_find_not_set(tmp_path, refresh_project):
    project = shutil.copy('tests/project_cases/basic.py', tmp_path / 'project.py')

    refresh_project()

    assert 'CASSINI_PROJECT' not in os.environ
    
    assert not env.project

    with pytest.raises(KeyError):
        find_project()


@pytest.fixture(params=list(
        itertools.product(
        ['basic.py', 'not_project.py'],
        ['', 'subdir'],
        ['project.py', 'my_project.py'],
        ['{module}', '{module_file}', '{directory}'],
        ['', ':{project_obj}'],
        [False, True]
)))
def cas_project(request, tmp_path, refresh_project):
    project_in, subdir, project_out, module_format, obj_format, relative_path = \
        request.param
    
    os.chdir(CWD)
    
    if obj_format == ':{project_obj}' and module_format == '{directory}':
        return pytest.skip("Valid CASSINI_PATH cannot be constructed from directory and object specifier")

    if module_format == '{directory}' and project_out != 'project.py':
        return pytest.skip("Valid CASSINI_PATH cannot be constructed from directory if project not called project.py")
    
    if module_format == '{module}' and subdir:
        return pytest.skip("Valid CASSINI_PATH cannot be constructed from just module if it's inside a subdir")

    project_out = tmp_path / subdir / project_out if subdir else tmp_path / project_out
    project_out.parent.mkdir(exist_ok=True)
    project_file = shutil.copy(f'tests/project_cases/{project_in}', project_out)

    project_obj = 'project' if project_in == 'basic.py' else 'my_project'

    if project_obj == 'my_project' and obj_format == '':
        return pytest.skip("Finding project won't work if non `project` name used and obj not specified")

    module = project_out.name.replace('.py', '')

    if relative_path or module_format == '{module}':
        os.chdir(tmp_path)

    if relative_path:
        module_file = project_file.relative_to(os.getcwd())
    else:
        module_file = project_file
    
    directory = str(module_file.parent)

    path_part = module_format.format(module=module, module_file=module_file, directory=directory)
    obj_part = obj_format.format(project_obj=project_obj)
    
    yield path_part + obj_part, request.param, project_out.parent


def test_find_project(cas_project, refresh_project):
    refresh_project()

    assert 'CASSINI_PROJECT' not in os.environ
    assert not env.project

    os.environ['CASSINI_PROJECT'] = cas_project[0]

    print('\n', cas_project[0], '\n')
                    
    project = find_project()

    assert project.test_project
    assert project.project_folder == cas_project[2]

