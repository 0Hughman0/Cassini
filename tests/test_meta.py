import json

import pytest # type: ignore[import]
from cassini.core import Meta
from cassini.accessors import MetaAttr

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
    assert contents == DEFAULT_CONTENTS

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
