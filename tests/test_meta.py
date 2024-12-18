import json
import pathlib
import datetime

from typing_extensions import assert_type

import pytest # type: ignore[import]
from cassini import HomeTierBase, NotebookTierBase
from cassini.meta import MetaAttr, Meta, MetaCache, MetaValidationError
from cassini.testing_utils import get_Project, patch_project, patched_default_project

import pydantic



DEFAULT_CONTENTS = {'a_str': 'val', 'an_int': 1, 'a_float': 1.5}


@pytest.fixture
def mk_meta(tmp_path):
    temp_file = tmp_path / 'test_constructor.json'
    temp_file.write_text(json.dumps(DEFAULT_CONTENTS))
    return Meta(temp_file)


def test_str_file_init(tmp_path):
    with_path = Meta(tmp_path)
    with_str = Meta(tmp_path.as_posix())

    assert with_path.file == with_str.file


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


def test_unicode_attr(mk_meta):
    meta = mk_meta

    meta['a_str'] = '🐟'

    meta.fetch()
    assert meta['a_str'] == '🐟'


def test_meta_attr(mk_meta):
    class MyClass:

        a_str = MetaAttr(str, str)
        an_int = MetaAttr(int, int)
        a_float = MetaAttr(float, float)
        
        processed_str = MetaAttr(str, str, post_get=lambda val: f't{val}', name='a_str')
        always_5 = MetaAttr(int, int, pre_set=lambda val: 5, name='an_int')

        doesnt_have = MetaAttr(str, str)
        with_default = MetaAttr(str, str, default='squid')

        def __init__(self):
            self.meta = Meta.create_meta(mk_meta.file, owner=self)

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


# this test has to be run with mypy... which is confusing.
def test_meta_attr_inferred_types(tmp_path) -> None:
    class MyClass:
        a_str = MetaAttr(str, str)

        def __init__(self):
            self.meta = Meta.create_meta(tmp_path / 'meta.json', owner=self)
    
    m = MyClass()
    
    assert_type(m.a_str, str)
    assert_type(MyClass.a_str, MetaAttr[str, str])


def test_jsonable(mk_meta):
    meta = mk_meta

    # attributes have to be serialisable in some way!
    with pytest.raises(MetaValidationError):
        meta['object'] = object

    # values must be json values. If you want type coersion, define a meta attr!
    with pytest.raises(MetaValidationError):
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
    
    with pytest.raises(MetaValidationError):
        meta['strict_str'] = 5
    
    meta['strict_str'] = 'new val'

    assert meta['strict_str'] == 'new val'



def test_meta_creation(get_Project, tmp_path):
    Project = get_Project
    class First(HomeTierBase):
        pretty_type = "First"

    class Second(NotebookTierBase):
        pretty_type = "Second"

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


def test_started_is_utc(patched_default_project):
    project, create_tiers = patched_default_project

    WP1, = create_tiers(['WP1'])
    
    assert WP1.started.tzinfo == datetime.timezone.utc


def test_started_requires_timezone(patched_default_project):
    project, create_tiers = patched_default_project

    WP1, = create_tiers(['WP1'])
    
    with pytest.raises(MetaValidationError):
        WP1.started = datetime.datetime.now()


def test_dumped_started_includes_timezone(patched_default_project):
    project, create_tiers = patched_default_project
    WP1, = create_tiers(['WP1'])

    assert 'Z' in json.loads(WP1.meta._cache.model_dump_json())['started']


def test_non_utc_timezones(patched_default_project):
    project, create_tiers = patched_default_project
    WP1, = create_tiers(['WP1'])

    WP1.started = datetime.datetime.fromisoformat('2011-11-04T00:05:23+04:00')
    WP1.started.utcoffset() == datetime.timedelta(hours=4)

    assert '+04:00' in json.loads(WP1.meta._cache.model_dump_json())['started']


def test_meta_attr_discovery(get_Project, tmp_path):
    Project = get_Project

    class First(HomeTierBase):
        pretty_type = "First"

    class Second(NotebookTierBase):
        pretty_type = "Second"

    class Third(NotebookTierBase):
        pretty_type = "Third"

    class Fourth(NotebookTierBase):
        pretty_type = "Fourth"
        test_attr = MetaAttr(str, str)

    for cls in [Second, Third, Fourth]:
        assert 'description' in cls.meta_model.model_fields
        assert 'conclusion' in cls.meta_model.model_fields
        assert 'started' in cls.meta_model.model_fields

    assert 'test_attr' not in Second.meta_model.model_fields
    assert 'test_attr' in Fourth.meta_model.model_fields    

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

    with pytest.raises(MetaValidationError):
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


def test_meta_validation_error_has_path(tmp_path):
    class Model(MetaCache):
        strict_str: str = 'default'

    meta = Meta(tmp_path / 'test.json', Model)

    with pytest.raises(MetaValidationError, match=str('test.json')):
        meta.strict_str = 10


def test_bad_setattr_raises_meta_error(tmp_path):
    class Model(MetaCache):
        strict_str: str = 'default'

    meta = Meta(tmp_path / 'test.json', Model)

    with pytest.raises(MetaValidationError, match=str('test.json')):
        meta.strict_str = 10


def test_bad_setitem_raises_meta_error(tmp_path):
    class Model(MetaCache):
        strict_str: str = 'default'

    meta = Meta(tmp_path / 'test.json', Model)

    with pytest.raises(MetaValidationError, match=str('test.json')):
        meta['strict_str'] = 10


def test_bad_fetch_raises_meta_error(tmp_path):
    class Model(MetaCache):
        strict_str: str = 'default'

    file = tmp_path / 'test.json'

    file.write_text('{"strict_str": 10}')

    meta = Meta(tmp_path / 'test.json', Model)

    with pytest.raises(MetaValidationError, match=str('test.json')):
        meta.fetch()


def test_bad_del_raises_meta_error(tmp_path):
    class Model(MetaCache):
        strict_str: str

    file = tmp_path / 'test.json'

    file.write_text('{"strict_str": "value"}')

    meta = Meta(tmp_path / 'test.json')
    meta.model = Model  # currently, we cannot set model=Model, because all fields must have defaults. 

    with pytest.raises(MetaValidationError, match=str('test.json')):
        del meta["strict_str"]


def test_cas_field_meta():
    m = MetaAttr(None, str, str, cas_field='core')
    assert m.cas_field == 'core'

    _, (_, field) = m.as_field()
    assert field.json_schema_extra == {'x-cas-field': 'core'}


def test_meta_manager_cas_field():
    attr = MetaAttr(str, str, cas_field='private')
    
    _, (_, field) = attr.as_field()
    assert field.json_schema_extra == {'x-cas-field': 'private'}
