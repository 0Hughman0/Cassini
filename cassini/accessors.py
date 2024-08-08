import functools

from typing import (
    Callable,
    Union,
    Any,
    cast,
    Dict,
    List,
    Tuple,
    TypeVar,
    Generic,
    Optional,
    Type,
    overload,
)
from typing_extensions import Self

from .environment import env

T = TypeVar("T")
V = TypeVar("V")

JSONPrimative = Union[str, int, float, bool, None]
JSONType = Union[
    Dict[JSONPrimative, "JSONType"],
    List["JSONType"],
    Tuple[JSONPrimative],
    JSONPrimative,
]
JSONProcessor = Callable[[JSONType], T]

JOut = TypeVar(
    "JOut",
    Dict[JSONPrimative, JSONType],
    List[JSONType],
    Tuple[JSONType, ...],
    str,
    int,
    float,
    bool,
    None,
)


class _SoftProp(Generic[T, V]):
    """
    Like a property, except can be overwritten.
    """

    def __init__(self, func: Callable[[T], V]):
        self.func = func
        self.__wrapped__ = func

    @overload
    def __get__(self, instance: None, owner: Type[T]) -> Self:
        pass

    @overload
    def __get__(self, instance: T, owner: Type[T]) -> V:
        pass

    def __get__(self, instance: Optional[T], owner: Type[T]) -> Union[V, Self]:
        if instance:
            return self.func(instance)
        return self


def soft_prop(wraps: Callable[[Any], V]) -> V:
    """
    Create an over-writable property
    """
    return cast(V, functools.wraps(wraps)(_SoftProp(wraps)))  # type: ignore[arg-type]


class _CachedProp(Generic[T, V]):
    """
    Like a read only property, except it's only evaluated once.

    Cached value is stored in the _CachedProp instance, which is maybe a bad idea, idk.
    """

    def __init__(self, func: Callable[[T], V]):
        self.func = func
        self.cache: Dict[T, V] = env.create_cache()

        self.__wrapped__ = func

    @overload
    def __get__(self, instance: None, owner: Type[T]) -> Self:
        pass

    @overload
    def __get__(self, instance: T, owner: Type[T]) -> V:
        pass

    def __get__(self, instance: Optional[T], owner: Type[T]) -> Union[V, Self]:
        if instance is None:
            return self

        if instance in self.cache:
            return self.cache[instance]

        val = self.func(instance)
        self.cache[instance] = val

        return val

    def __set__(self, instance: Optional[T], value: Any) -> None:
        raise AttributeError("Trying to set a cached property - naughty!")

    @property
    def __isabstractmethod__(self):
        return getattr(self.func, "__isabstractmethod__", False)


def cached_prop(wrapped: Callable[[Any], V]) -> V:
    """
    Decorator for turning functions/ methods into `_CachedProp`s.
    """
    return cast(V, functools.wraps(wrapped)(_CachedProp(wrapped)))  # type: ignore[arg-type]


class _CachedClassProp(Generic[T, V]):
    """
    Like a combination between `classmethod` and `property`.

    The class instance is passed to the wrapped method upon calling.

    Also performs same caching as `_CachedProp`.
    """

    def __init__(self, func: Callable[[Type[T]], V]):
        self.func = func
        self.cache: Dict[Type[T], V] = env.create_cache()

        self.__wrapped__ = func

    def __get__(self, instance: T, owner: Type[T]) -> V:
        if owner in self.cache:
            return self.cache[owner]

        val = self.func(owner)
        self.cache[owner] = val

        return val

    def __set__(self, instance: T, value: Any) -> Any:
        raise AttributeError("Trying to set a cached class property - naughty!")

    @property
    def __isabstractmethod__(self):
        return getattr(self.func, "__isabstractmethod__", False)


def cached_class_prop(wrapped: Callable[[Any], V]) -> V:
    """
    Decorator for turning functions/ methods into `_CachedClassProp`s.

    First argument of wrapped will be `self.__class__` rather than `self`.
    """
    return cast(V, functools.wraps(wrapped)(_CachedClassProp(wrapped)))  # type: ignore[arg-type]
