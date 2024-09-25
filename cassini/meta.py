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
    Literal,
)
from typing_extensions import Tuple, cast, Self, Type

from pydantic import BaseModel, ConfigDict, Field, create_model, JsonValue, ValidationError
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


class MetaValidationError(ValueError):

    def __init__(self, *, validation_error: ValidationError, file: Path):
        message = f"Invalid data in file: {file}, due to the following validation error:\n\n{validation_error}"
        
        super().__init__(message)
        self.file = file
        self.validation_error = validation_error


class Meta:
    """
    Like a dictionary, except linked to a json file on disk. Caches the value of the json in itself.

    Arguments
    ---------
    file: Path
           File Meta object stores information about.

    Attributes
    ----------
    file: Path
        Path to the meta file.
    model: MetaCache
        Pydantic model representation of this meta object. Used to perform validation, and serial/deserialisation.
    """

    timeout: ClassVar[int] = 1
    my_attrs: ClassVar[List[str]] = ["model", "_cache", "_cache_born", "file"]

    def __init__(self, file: Path, model: Union[Type[MetaCache], None] = None):
        if model is None:
            model = MetaCache

        self._cache_born: float = 0.0
        self.file: Path = file
        self.model: Type[MetaCache] = model

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
            try:
                self._cache = self.model.model_validate_json(
                    self.file.read_text(), strict=False
                )
            except ValidationError as e:
                raise MetaValidationError(validation_error=e, file=self.file)
            
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
            
            try:
                setattr(self._cache, name, value)
            except ValidationError as e:
                raise MetaValidationError(validation_error=e, file=self.file)
            
            self.write()

    def __delitem__(self, key: str) -> None:
        self.fetch()
        excluded = self._cache.model_dump(
            exclude={"__pydantic_extra__", key}, exclude_defaults=True
        )

        try:
            self._cache = self.model.model_validate(excluded)
        except ValidationError as e:
            raise MetaValidationError(validation_error=e, file=self.file)
        
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
    ---------
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
        cas_field: Union[None, Literal["core"], Literal["private"]] = None,
    ):
        self.json_type = json_type
        self.attr_type = attr_type

        self.post_get = post_get
        self.pre_set = pre_set

        self.owner = owner_
        self.name: str = cast(str, name)
        self.default = default

        self.cas_field = cas_field

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
        if self.cas_field:
            return self.name, (
                self.json_type,
                Field(
                    default=self.default,
                    json_schema_extra={"x-cas-field": self.cas_field},
                ),
            )
        else:
            return self.name, (self.json_type, Field(default=self.default))


T = TypeVar("T")


class MetaManager:
    """
    Class for the creation of meta objects.

    This needs to exist in order for the model of meta objects to work and allows
    meta objects to serialise attributes into types beyond `JsonValue`s.
    """

    metas: ClassVar[Dict[Any, Meta]] = {}

    def __init__(self) -> None:
        self.cls: Union[Type, None] = None
        self.meta_attrs: List[MetaAttr] = []

    def connect_class(self, cls: Type[T]) -> Type[T]:
        cls.__meta_manager__ = self  # type: ignore[attr-defined]
        self.cls = cls
        return cls

    def build_fields(self):
        """
        Look through the meta attributes of this class and its base classes and find all the
        meta attributes it should have. Then generate pydantic compatible Field definitions
        for those fields.
        """
        fields = set()

        for cls in self.cls.__mro__:
            manager = getattr(cls, "__meta_manager__", None)
            if manager:
                fields.update(meta_attr.as_field() for meta_attr in manager.meta_attrs)

        return {name: field for name, field in fields}

    def build_model(self) -> Type[MetaCache]:
        """
        Build a pydantic model for the metadata of `self.cls`, incorporating additional fields
        defined using `MetaAttr`.
        """
        fields = self.build_fields()

        cls_name = self.cls.__name__ if self.cls else "Custom"

        return create_model(f"{cls_name}MetaCache", __base__=MetaCache, **fields)

    def meta_attr(
        self,
        json_type: Type[JSONType],
        attr_type: Type[AttrType],
        post_get: Callable[[JSONType], AttrType] = _null_func,
        pre_set: Callable[[AttrType], JSONType] = _null_func,
        name: Union[str, None] = None,
        default: Union[AttrType, None] = None,
        cas_field: Union[None, Literal["core"], Literal["private"]] = None,
    ):
        """
        Add a meta attribute to this class.

        json_type: Any
            Type to pass to pydantic when creating the `Meta.model`. This can be any type supported by pydantic,
            `see here <https://docs.pydantic.dev/latest/concepts/conversion_table/>`_, i.e. not just `JsonValue`s.
        attr_type: Any
            Type actually returned by meta attribute i.e. accounting for `post_get`.
        post_get: func
        function to apply to data after being loaded from json file
        pre_set: func
            function to apply to data before stored in json file.
        name: str
            key to lookup in meta
        default:
            value to return if key not found in meta (note post_get isn't called on this).
        """
        obj = MetaAttr(
            self,
            json_type=json_type,
            attr_type=attr_type,
            post_get=post_get,
            pre_set=pre_set,
            name=name,
            default=default,
            cas_field=cas_field,
        )

        self.meta_attrs.append(obj)

        return obj

    def create_meta(self, path: Path, owner: Any):
        """
        Create meta object at `path`.

        The appropraite additional fields for each meta attribute are passed on.
        """
        self.__class__.metas[owner] = Meta(path, self.build_model())
        return self.metas[owner]
