import json

import pytest # type: ignore[import]
from cassini import Project, HomeTierBase, NotebookTierBase
from cassini.meta import Meta
from cassini.meta import MetaAttr

import pydantic

from utils import patch_project

DEFAULT_CONTENTS = {'str': 'val', 'int': 1, 'float': 1.5}


@pytest.fixture
def mk_meta(tmp_path):
    temp_file = tmp_path / 'test_constructor.json'
    temp_file.write_text(json.dumps(DEFAULT_CONTENTS))
    return Meta(temp_file)


def test_access(mk_meta):
    meta = mk_meta

    assert meta['str'] == 'val'
    assert meta['int'] == 1
    assert meta['float'] == 1.5

    meta['str'] = 'new'
    assert meta['str'] == 'new'

    meta['int'] = 2
    assert meta['int'] == 2

    meta['float'] = 2.5
    assert meta['float'] == 2.5

    assert meta.float == 2.5

    meta.float = 3.5
    assert meta.float == 3.5

    assert meta.get('foo') is None
    assert meta.get('foo', 'bar') == 'bar'


def test_caching(mk_meta, monkeypatch):
    meta = mk_meta

    contents = meta.fetch()
    assert contents.model_dump() == DEFAULT_CONTENTS

    assert meta.age < 0.1

    meta.file.write_text(json.dumps({'manual': 1}))

    with pytest.raises(KeyError):
        assert meta['manual'] == 1

    with pytest.raises(AttributeError):
        assert meta.manual == 1

    meta.fetch()

    assert meta['manual'] == 1

    monkeypatch.setattr(Meta, 'timeout', 0.0)

    meta.file.write_text(json.dumps({'manual': 2}))
    assert meta.age >= 0
    assert meta.timeout == 0.0
    assert meta['manual'] == 2


def test_del(mk_meta):
    meta = mk_meta

    default = DEFAULT_CONTENTS.copy()
    assert meta.keys() == default.keys()
    del meta['str']
    del default['str']
    assert meta.keys() == default.keys()

    with pytest.raises(KeyError):
        assert meta['str'] == 'val'


def test_meta_attr(mk_meta):
    class MyClass:

        str = MetaAttr()
        int = MetaAttr()
        float = MetaAttr()

        processed_str = MetaAttr(post_get=lambda val: f't{val}', name='str')
        always_5 = MetaAttr(pre_set=lambda val: 5, name='int')

        doesnt_have = MetaAttr()
        with_default = MetaAttr(default='squid')

        def __init__(self):
            self.meta = mk_meta

    obj = MyClass()

    assert obj.str == 'val'
    assert obj.int == 1
    assert obj.float == 1.5

    assert obj.processed_str == 'tval'

    obj.str = 'new'

    assert obj.str == 'new'
    assert obj.processed_str == 'tnew'

    obj.always_5 = 7

    assert obj.always_5 == 5
    assert obj.int == 5

    assert obj.doesnt_have is None
    assert obj.with_default == 'squid'


def test_jsonable(mk_meta):
    meta = mk_meta

    with pytest.raises(pydantic.ValidationError):
        meta['object'] = object


    # type changes are allowed without meta definition.
    meta['type-change'] = 'text'

    assert meta['type-change'] == 'text'

    meta['type-change'] = False

    assert meta['type-change'] is False


def test_strict_attrs(tmp_path):
    meta = Meta(tmp_path / 'test.json',
                {'strict_str': (str, 'default')})
    
    assert meta['strict_str'] == 'default'
    
    with pytest.raises(pydantic.ValidationError):
        meta['strict_str'] = 5
    
    meta['strict_str'] = 'new val'

    assert meta['strict_str'] == 'new val'


def test_meta_attr_discovery(tmp_path):
    class First(HomeTierBase):
        pass

    class Second(NotebookTierBase):
        pass
    
    Project._instance = None
    project = Project([First, Second], tmp_path)
    project.setup_files()

    obj = project['Second1']
    obj.setup_files()

    assert 'description' in obj.meta._model.model_fields
    assert 'conclusion' in obj.meta._model.model_fields
    assert 'started' in obj.meta._model.model_fields

    assert obj.description is None

    obj.description = 'new description'

    assert obj.description == 'new description'

    with pytest.raises(pydantic.ValidationError):
        obj.description = 124

    





    
