import time
from pathlib import Path
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Generic,
    KeysView,
    List,
    Optional,
    TypeVar,
    Union,
)
from typing_extensions import Tuple, cast, Self, Type

from pydantic import BaseModel, ConfigDict, Field, create_model, JsonValue
from pydantic.fields import FieldInfo


JSONType = TypeVar("JSONType")
AttrType = TypeVar("AttrType")


class MetaCache(BaseModel):
    __pydantic_extra__: Dict[str, JsonValue] = Field(init=False)
    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        revalidate_instances="subclass-instances",
        strict=True,
    )


class Meta:
    """
    Like a dictionary, except linked to a json file on disk. Caches the value of the json in itself.

    Arguments
    ---------
    file: Path
           File Meta object stores information about.
    """

    timeout: ClassVar[int] = 1
    my_attrs: ClassVar[List[str]] = ["model", "_cache", "_cache_born", "file"]

    def __init__(
        self, file: Path, fields: Optional[Dict[str, Tuple[Type, FieldInfo]]] = None
    ):
        if fields is None:
            fields = {}

        self._cache_born: float = 0.0
        self.file: Path = file

        self.model: Type[MetaCache] = create_model(
            "CustomMetaCache", __base__=MetaCache, **fields
        )  # type: ignore[call-overload]
        self._cache: MetaCache = self.model()

    @property
    def age(self) -> float:
        """
        time in secs since last fetch
        """
        return time.time() - self._cache_born

    def fetch(self) -> MetaCache:
        """
        Fetches values from the meta file and updates them into `self._cache`.

        Notes
        -----
        This doesn't *overwrite* `self._cache` with meta contents, but updates it. Meaning new stuff to file won't be
        overwritten, it'll just be loaded.
        """
        if self.file.exists():
            self._cache = self._cache.model_validate_json(
                self.file.read_text(), strict=False
            )
            self._cache_born = time.time()
        return self._cache

    def refresh(self) -> None:
        """
        Check age of cache, if stale then re-fetch
        """
        if self.age >= self.timeout:
            self.fetch()

    def write(self) -> None:
        """
        Overwrite contents of cache into file
        """
        jsons = self._cache.model_dump_json(
            exclude_defaults=True, exclude={"__pydantic_extra__"}
        )
        # Danger moment - writing bad cache to file.
        with self.file.open("w", encoding="utf-8") as f:
            f.write(jsons)

    def __getitem__(self, item: str) -> Any:
        self.refresh()
        try:
            return getattr(self._cache, item)
        except AttributeError as e:
            raise KeyError(e)

    def __setitem__(self, key: str, value: Any) -> None:
        self.__setattr__(key, value)

    def __getattr__(self, item: str) -> Any:
        self.refresh()
        try:
            return getattr(self._cache, item)
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self.my_attrs:
            super().__setattr__(name, value)
        else:
            self.fetch()
            setattr(self._cache, name, value)
            self.write()

    def __delitem__(self, key: str) -> None:
        self.fetch()
        excluded = self._cache.model_dump(
            exclude={"__pydantic_extra__", key}, exclude_defaults=True
        )
        self._cache = self.model.model_validate(excluded)
        self.write()

    def __repr__(self) -> str:
        self.refresh()
        return f"<Meta {self._cache} ({self.age * 1000:.1f}ms)>"

    def get(self, key: str, default: Any = None) -> Any:
        """
        Like `dict.get`
        """
        try:
            return self.__getattr__(key)
        except AttributeError:
            return default

    def keys(self) -> KeysView[str]:
        """
        like `dict.keys`
        """
        self.refresh()
        return self._cache.model_dump(
            exclude={"__pydantic_extra__"}, exclude_defaults=True
        ).keys()


def _null_func(val: Any) -> Any:
    return cast(JsonValue, val)


class MetaAttr(Generic[AttrType, JSONType]):
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

    def __init__(
        self,
        owner_: "MetaManager",
        json_type: Type[JSONType],
        attr_type: Type[AttrType],
        post_get: Callable[[JSONType], AttrType] = _null_func,
        pre_set: Callable[[AttrType], JSONType] = _null_func,
        name: Union[str, None] = None,
        default: Union[AttrType, None] = None,
    ):
        self.json_type = json_type
        self.attr_type = attr_type

        self.post_get = post_get
        self.pre_set = pre_set

        self.owner = owner_
        self.name: str = cast(str, name)
        self.default = default

    def __set_name__(self, owner: object, name: str) -> None:
        if self.name is None:
            self.name = name

    def __get__(
        self, instance: Union[Any, None], owner: object
    ) -> Union[AttrType, Self]:
        if owner is None or instance is None:
            return self

        if not self.owner.metas[instance]:
            raise RuntimeError(
                "Trying to access Meta Attribute before Meta instance created!"
            )

        return self.post_get(self.owner.metas[instance].get(self.name, self.default))

    def __set__(self, instance: Any, value: AttrType) -> None:
        setattr(self.owner.metas[instance], self.name, self.pre_set(value))

    def as_field(self) -> Tuple[str, Tuple[Type[JSONType], FieldInfo]]:
        return self.name, (self.json_type, Field(default=self.default))


class MetaManager:
    metas: ClassVar[Dict[Any, Meta]] = {}

    def __init__(self) -> None:
        self.cls: Union[Type, None] = None
        self.meta_attrs: List[MetaAttr] = []

    def connect_class(self, cls: Type) -> Type:
        cls.__meta_manager__ = self  # type: ignore[attr-defined]
        self.cls = cls
        return cls

    def build_fields(self):
        fields = set()

        for cls in self.cls.__mro__:
            manager = getattr(cls, "__meta_manager__", None)
            if manager:
                fields.update(meta_attr.as_field() for meta_attr in manager.meta_attrs)

        return {name: field for name, field in fields}

    def meta_attr(
        self,
        json_type: Type[JSONType],
        attr_type: Type[AttrType],
        post_get: Callable[[JSONType], AttrType] = _null_func,
        pre_set: Callable[[AttrType], JSONType] = _null_func,
        name: Union[str, None] = None,
        default: Union[AttrType, None] = None,
    ):
        obj = MetaAttr(
            self,
            json_type=json_type,
            attr_type=attr_type,
            post_get=post_get,
            pre_set=pre_set,
            name=name,
            default=default,
        )

        self.meta_attrs.append(obj)

        return obj

    def create_meta(self, path: Path, owner: Any):
        self.__class__.metas[owner] = Meta(path, self.build_fields())
        return self.metas[owner]
