import json
import pathlib

import pytest # type: ignore[import]
from cassini import HomeTierBase, NotebookTierBase
from cassini.meta import MetaAttr, MetaManager, Meta, MetaCache
from cassini.testing_utils import get_Project, patch_project

import pydantic



DEFAULT_CONTENTS = {'a_str': 'val', 'an_int': 1, 'a_float': 1.5}


@pytest.fixture
def mk_meta(tmp_path):
    temp_file = tmp_path / 'test_constructor.json'
    temp_file.write_text(json.dumps(DEFAULT_CONTENTS))
    return Meta(temp_file)


def test_access(mk_meta):
    meta = mk_meta

    assert meta['a_str'] == 'val'
    assert meta['an_int'] == 1
    assert meta['a_float'] == 1.5

    meta['a_str'] = 'new'
    assert meta['a_str'] == 'new'

    meta['an_int'] = 2
    assert meta['an_int'] == 2

    meta['a_float'] = 2.5
    assert meta['a_float'] == 2.5

    assert meta.a_float == 2.5

    meta.a_float = 3.5
    assert meta.a_float == 3.5

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
    del meta['a_str']
    del default['a_str']
    assert meta.keys() == default.keys()

    with pytest.raises(KeyError):
        assert meta['a_str'] == 'val'


def test_meta_attr(mk_meta):
    manager = MetaManager()

    @manager.connect_class
    class MyClass:

        a_str = manager.meta_attr(str, str)
        an_int = manager.meta_attr(int, int)
        a_float = manager.meta_attr(float, float)
        
        processed_str = manager.meta_attr(str, str, post_get=lambda val: f't{val}', name='a_str')
        always_5 = manager.meta_attr(int, int, pre_set=lambda val: 5, name='an_int')

        doesnt_have = manager.meta_attr(str, str)
        with_default = manager.meta_attr(str, str, default='squid')

        def __init__(self):
            self.meta = manager.create_meta(mk_meta.file, owner=self)

    obj = MyClass()

    assert obj.a_str == 'val'
    assert obj.an_int == 1
    assert obj.a_float == 1.5

    assert obj.processed_str == 'tval'

    obj.a_str = 'new'

    assert obj.a_str == 'new'
    assert obj.processed_str == 'tnew'

    obj.always_5 = 7

    assert obj.always_5 == 5
    assert obj.an_int == 5

    assert obj.doesnt_have is None
    assert obj.with_default == 'squid'


def test_jsonable(mk_meta):
    meta = mk_meta

    # attributes have to be serialisable in some way!
    with pytest.raises(pydantic.ValidationError):
        meta['object'] = object

    # values must be json values. If you want type coersion, define a meta attr!
    with pytest.raises(pydantic.ValidationError):
        meta['pathlike'] = pathlib.Path().absolute()

    # type changes are allowed without meta definition.
    meta['type-change'] = 'text'

    assert meta['type-change'] == 'text'

    meta['type-change'] = False

    assert meta['type-change'] is False


def test_strict_attrs(tmp_path):
    class Model(MetaCache):
        strict_str: str = 'default'

    meta = Meta(tmp_path / 'test.json',
                Model)
    
    assert meta['strict_str'] == 'default'
    
    with pytest.raises(pydantic.ValidationError):
        meta['strict_str'] = 5
    
    meta['strict_str'] = 'new val'

    assert meta['strict_str'] == 'new val'


def test_meta_creation(get_Project, tmp_path):
    Project = get_Project
    class First(HomeTierBase):
        pass

    class Second(NotebookTierBase):
        pass

    project = Project([First, Second], tmp_path)
    project.setup_files()

    obj1 = project['Second1']
    obj2 = project['Second2']
    obj2.setup_files()
    obj1.setup_files()
    
    assert obj1.meta is not obj2.meta
    
    assert obj2.description != '1'
    obj1.description = '1'
    assert obj2.description != '1'

    assert obj1.meta is obj1.__meta_manager__.metas[obj1]
    assert obj2.meta is obj2.__meta_manager__.metas[obj2]


def test_meta_attr_discovery(get_Project, tmp_path):
    Project = get_Project
    class First(HomeTierBase):
        pass

    class Second(NotebookTierBase):
        pass

    class Third(NotebookTierBase):
        pass

    manager = MetaManager()

    @manager.connect_class
    class Fourth(NotebookTierBase):
        test_attr = manager.meta_attr(str, str)

    assert Second.__meta_manager__ is Third.__meta_manager__
    assert Fourth.__meta_manager__ is not Third.__meta_manager__

    assert 'description' not in (attr.name for attr in Fourth.__meta_manager__.meta_attrs)
    assert 'description' in Fourth.__meta_manager__.build_fields()
    assert 'conclusion' in Fourth.__meta_manager__.build_fields()
    assert 'started' in Fourth.__meta_manager__.build_fields()

    project = Project([First, Second, Third, Fourth], tmp_path)
    project.setup_files()

    obj = project['Second1']
    obj.setup_files()

    assert obj.started

    assert 'description' in obj.meta.model.model_fields
    assert 'conclusion' in obj.meta.model.model_fields
    assert 'started' in obj.meta.model.model_fields

    assert obj.description is None

    obj.description = 'new description'

    assert obj.description == 'new description'

    with pytest.raises(pydantic.ValidationError):
        obj.description = 124

    obj = project['Second1Third1']
    obj.setup_files()

    obj = project['Second1Third1Fourth1']
    obj.setup_files()

    assert obj.started

    assert 'test_attr' in obj.meta.model.model_fields
    assert 'description' in obj.meta.model.model_fields
    assert 'conclusion' in obj.meta.model.model_fields
    assert 'started' in obj.meta.model.model_fields
