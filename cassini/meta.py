import time
import functools
from pathlib import Path
from typing import Any, Callable, ClassVar, Dict, Generic, KeysView, List, TYPE_CHECKING, Optional, TypeVar, Union
from typing_extensions import Annotated, Tuple, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, create_model, JsonValue

if TYPE_CHECKING:
    from cassini.core import TierABC


T = TypeVar("T")
JOut = TypeVar("JOut", bound=JsonValue)


class MetaJSON(BaseModel):
    __pydantic_extra__: Dict[str, JsonValue] = Field(init=False)
    model_config = ConfigDict(extra='allow', validate_assignment=True, revalidate_instances='subclass-instances', strict=True)


class Meta:
    """
    Like a dictionary, except linked to a json file on disk. Caches the value of the json in itself.

    Arguments
    ---------
    file: Path
           File Meta object stores information about.
    """

    timeout: ClassVar[int] = 1
    my_attrs: ClassVar[List[str]] = ["_model", "_cache_born", "file"]

    def __init__(self, file: Path, fields: Optional[Dict[str, Tuple[JsonValue, Field]]] = None):
        if fields is None:
            fields = {}

        model = create_model('CustomMetaJSON',
                             **fields,
                             __base__=MetaJSON)
        self._model: MetaJSON = model()
        self._cache_born: float = 0.0
        self.file: Path = file

    @property
    def age(self) -> float:
        """
        time in secs since last fetch
        """
        return time.time() - self._cache_born

    def fetch(self) -> MetaJSON:
        """
        Fetches values from the meta file and updates them into `self._cache`.

        Notes
        -----
        This doesn't *overwrite* `self._cache` with meta contents, but updates it. Meaning new stuff to file won't be
        overwritten, it'll just be loaded.
        """
        if self.file.exists():
            self._model = self._model.model_validate_json(self.file.read_text(), strict=False)
            self._cache_born = time.time()
        return self._model

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
        self._model.model_validate(self._model)  # maybe over-cautious!
        jsons = self._model.model_dump_json(exclude_defaults=True, exclude={'__pydantic_extra__'})
        # Danger moment - writing bad cache to file.
        with self.file.open("w", encoding="utf-8") as f:
            f.write(jsons)

    def __getitem__(self, item: str) -> JsonValue:
        self.refresh()
        try:
            return getattr(self._model, item)
        except AttributeError as e:
            raise KeyError(e)

    def __setitem__(self, key: str, value: JsonValue) -> None:
        self.__setattr__(key, value)

    def __getattr__(self, item: str) -> JsonValue:
        self.refresh()
        try:
            return getattr(self._model, item)
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, name: str, value: JsonValue) -> None:
        if name in self.my_attrs:
            super().__setattr__(name, value)
        else:
            self.fetch()
            setattr(self._model, name, value)
            self.write()

    def __delitem__(self, key: str) -> None:
        self.fetch()
        excluded = self._model.model_dump(exclude={key})
        self._model = self._model.model_validate(excluded)
        self.write()

    def __repr__(self) -> str:
        self.refresh()
        return f"<Meta {self._model} ({self.age * 1000:.1f}ms)>"

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
        return self._model.model_dump().keys()


def _null_func(val: Any) -> Any:
    return cast(JsonValue, val)


class MetaAttr(Generic[JOut, T]):
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
        post_get: Callable[[JOut], T] = _null_func,
        pre_set: Callable[[T], JOut] = _null_func,
        name: Union[str, None] = None,
        default: Union[T, None] = None,
    ):
        self.name: str = cast(str, name)
        self.post_get: Callable[[JOut], T] = post_get
        self.pre_set: Callable[[T], JOut] = pre_set
        self.default = default

    def __set_name__(self, owner: object, name: str) -> None:
        if self.name is None:
            self.name = name

    def __get__(self, instance: "TierABC", owner: object) -> Union[T, None]:
        if instance is None:
            return self

        return self.post_get(cast(JOut, instance.meta.get(self.name, self.default)))

    def __set__(self, instance: "TierABC", value: T) -> None:
        setattr(instance.meta, self.name, self.pre_set(value))

    def as_field(self) -> Tuple[str, Tuple[JOut, Field]]:
        # this is nasty, see https://github.com/python/cpython/issues/101688
        try:
            JOut, T = get_args(self.__orig_class__)  # typing[attr-defined]
        except AttributeError:
            JOut = JsonValue

        return self.name, Annotated[Optional[JOut], Field(default=self.default)]


class MetaAttrManager:

    def __init__(self, cls):
        self.cls = cls
        self.meta_attrs = []

    @functools.wraps(MetaAttr)
    def MetaAttr(self, *args, **kwargs):
        meta_attr = MetaAttr(*args, **kwargs)
        self.meta_attrs.append(meta_attr)
        return meta_attr