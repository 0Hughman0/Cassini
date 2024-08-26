import shutil
import json
import datetime
import sys

import pytest

from cassini.migrate.V0_2toV0_3 import V0_2toV0_3
from cassini.utils import find_project
from cassini import env
from cassini.core import NotebookTierBase


@pytest.fixture
def get_migrator(tmp_path, monkeypatch):
    shutil.copytree('tests/compat/0.2.0', tmp_path, dirs_exist_ok=True)
    monkeypatch.setenv('CASSINI_PROJECT', str(tmp_path / 'project.py'))

    yield V0_2toV0_3(find_project())
    
    env._reset()
    sys.modules.pop('project')
    

def test_get_project(get_migrator):
    migrator = get_migrator
    assert migrator.project


def test_iterate(get_migrator):
    migrator = get_migrator
    
    all_names = set([
        'Home',
        'WP1',
        'WP1.1',
        'WP1.2',
        'WP1.1a',
        'WP1.1b',
        'WP2',
        'WP2.2',
        'WP2.2a'
    ])

    for tier in migrator.walk_tiers():
        all_names.remove(tier.name)

    assert len(all_names) == 0


def test_update_meta(get_migrator):
    migrator = get_migrator
    WP1 = migrator.project['WP1.1']
    assert '/' in json.loads(WP1.meta_file.read_text())['started']
    migrator.migrate_meta(WP1)
    assert '/' not in json.loads(WP1.meta_file.read_text())['started']
    assert isinstance(WP1.started, datetime.datetime)


def test_full_migrate(get_migrator):
    migrator = get_migrator
    migrator.migrate()

    for tier in migrator.walk_tiers():
        if isinstance(tier, NotebookTierBase):
            assert isinstance(tier.started, datetime.datetime)


def test_safe_on_exception(get_migrator):
    migrator = get_migrator
    WP1 = migrator.project['WP1']
    meta_contents = WP1.meta_file.read_text()
    broken_content = meta_contents.replace('/', '~')
    WP1.meta_file.write_text(broken_content)

    with pytest.raises(RuntimeError):
        migrator.migrate()
    
    backup_file = WP1.meta_file.with_suffix('.backup')
    assert backup_file.exists()
    assert broken_content == backup_file.read_text()
