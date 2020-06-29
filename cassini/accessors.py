import functools
from typing import Callable, Union, Any


def _null_func(val):
    return val


JSONProcessor = Callable[[Union[dict, list, str, int, float, bool, None]], Any]


class MetaAttr:
    """
    Accessor for getting values from a Tier class's meta as an attribute.

    Supports basic serial and de-serialisation.

    Isn't fussy, in that it won't raise an exception if it can't find its key.

    Arguments
    =========
    post_get: func
        function to apply to data after being loaded from json file
    pre_set: func
        function to apply to data before stored in json file.
    name: str
        key to lookup in meta
    default:
        value to return if key not found in meta (note post_get isn't called on this).

    Examples
    ========

    >>> class MyTier(TierBase):
    >>>
    >>>     list_attr = MetaAttr(post_get=lambda val: val.split(','),
    ...                          pre_set=lambda val: ','.join(val))

    """

    def __init__(self,
                 post_get: JSONProcessor = _null_func, pre_set: JSONProcessor = _null_func,
                 name: str = None,
                 default: Any = None):
        self.name = name
        self.post_get = post_get
        self.pre_set = pre_set
        self.default = default

    def __set_name__(self, owner, name):
        if self.name is None:
            self.name = name

    def __get__(self, instance, owner):
        try:
            return self.post_get(instance.meta[self.name])
        except KeyError:
            return self.default

    def __set__(self, instance, value):
        setattr(instance.meta, self.name, self.pre_set(value))


class _SoftProp:
    """
    Like a property, except can be overwritten.
    """

    def __init__(self, func):
        self.func = func

    def __get__(self, instance, owner):
        if instance:
            return self.func(instance)
        return self


def soft_prop(wraps: Callable):
    """
    Create an over-writable property
    """
    return functools.wraps(wraps)(_SoftProp(wraps))


class _CachedProp:
    """
    Like a read only property, except it's only evaluated once.

    Cached value is stored in the _CachedProp instance, which is maybe a bad idea, idk.
    """

    def __init__(self, func: Callable):
        self.func = func
        self.cache = {}

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if instance in self.cache:
            return self.cache[instance]
        val = self.func(instance)
        self.cache[instance] = val
        return val

    def __set__(self, instance, value):
        raise AttributeError("Trying to set a cached property - naughty!")


def cached_prop(wraps: Callable):
    """
    Decorator for turning functions/ methods into `_CachedProp`s.
    """
    return functools.wraps(wraps)(_CachedProp(wraps))


class _CachedClassProp:
    """
    Like a combination between `classmethod` and `property`.

    The class instance is passed to the wrapped method upon calling.

    Also performs same caching as `_CachedProp`.
    """

    def __init__(self, func: Callable):
        self.func = func
        self.cache = {}

    def __get__(self, instance, owner):
        if owner in self.cache:
            return self.cache[owner]
        val = self.func(owner)
        self.cache[owner] = val
        return val

    def __set__(self, instance, value):
        raise AttributeError("Trying to set a cached class property - naughty!")


def cached_class_prop(wraps: Callable):
    """
    Decorator for turning functions/ methods into `_CachedClassProp`s.

    First argument of wraps will be `self.__class__` rather than `self`.
    """
    return functools.wraps(wraps)(_CachedClassProp(wraps))
