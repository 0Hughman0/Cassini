import pytest # type: ignore[import]

from cassini import DEFAULT_TIERS
from cassini.testing_utils import get_Project, patch_project

@pytest.fixture
def mk_project(get_Project, tmp_path):
    Project = get_Project

    # this crazy line is required for testing because cachedclassprop values may be set by other tests!    
    project = Project([type(cls.__name__, (cls,), {}) for cls in DEFAULT_TIERS], tmp_path)
    project.setup_files()

    wp = project['WP1']
    wp.setup_files()

    exp = project['WP1.1']
    exp.setup_files()

    smpl = project['WP1.1a']
    smpl.setup_files()

    dset = project['WP1.1a-data']
    dset.setup_files()

    return project


def test_add_highlight(mk_project) -> None:
    project: Project = mk_project

    wp = project['WP1']

    assert wp.highlights_file is not None 
    assert not wp.highlights_file.exists()
    
    wp.add_highlight('test', [{'data': {}}])

    assert wp.highlights_file.exists()

    exp = project['WP1.1']

    assert exp.highlights_file is not None 
    assert not exp.highlights_file.exists()
    
    exp.add_highlight('test', [{'data': {}}])

    assert exp.highlights_file.exists()

    smpl = project['WP1.1a']

    assert smpl.highlights_file is not None 
    assert not smpl.highlights_file.exists()
    
    smpl.add_highlight('test', [{'data': {}}])

    assert smpl.highlights_file.exists()

    dset = project['WP1.1a-data']

    with pytest.raises(AttributeError):
        assert dset.highlights_file is None 

