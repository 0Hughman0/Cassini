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

    Example
    -------

    ```python

    class MyClass

        @soft_prop
        def a_soft_prop(self):
            return 'red'

        @property
        def a_hard_prop(self):
            return 'red'
    
    my_instance = MyClass()
    my_instance.a_hard_prop = 'blue'  # raises error
    print(my_instance.a_hard_prop)  # still prints red
    my_instance.a_soft_prop = 'blue'  # allowed!
    print(my_instance.softy)  # prints blue
    ```
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

    Example
    -------

    ```python
    class MyClass:
    
        def __init__(self):
            self.count = 0
    
        @cached_prop
        def count_once(self):
            self.count += 1
            return count

    my_instance = MyClass
    print(my_instance.count_once)  # prints 1
    print(my_instance.count_once)  # ... still prints 1!
    ```
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

    Example
    -------

    ```python
    class MyClass:
    
        count = 0
    
        @cached_class_prop
        def count_once(cls):
            cls.count += 1
            return count

    print(MyClass.count_once)  # prints 1
    print(MyClass.count_once)  # ... still prints 1!
    ```
    """
    return cast(V, functools.wraps(wrapped)(_CachedClassProp(wrapped)))  # type: ignore[arg-type]
