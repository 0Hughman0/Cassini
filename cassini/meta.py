"""
Module for allowing storage of object attributes in a json file.

Pydantic is used for validation during de/serialisation.

Examples
--------
Basic usage. 

A [Meta][cassini.meta.Meta] object is like a dictionary, except it's contents is stored in a file on disk:

```pycon
>>> from cassini.meta import Meta
>>> 
>>> meta = Meta('data.json')
>>> meta['key'] = 'value'
>>> meta['key']
value
>>> with open('data.json') as fs:
...     print(fs.read())
{"key":"value"}
```

Pydantic looks after validation

```pycon
>>> meta['invalid'] = object  # raises ValidationError because object cannot be stored in a json.
1 validation error for MetaCache
invalid
  input was not a valid JSON value [type=invalid-json-value, input_value=<class 'object'>, input_type=type]
```

You can pass a custom Pydantic model to `Meta` to change the validation behaviour. Cassini provides a helpful baseclass for these [MetaCache][cassini.meta.MetaCache].

```pycon
>>> from cassini.meta import MetaCache
>>> from typing import Optional
>>> from pathlib import Path
>>> 
>>> class MyModel(MetaCache):
...     a_path: Optional[Path] = None
```

!!!Important
    Because meta are initially created empty, any fields in the model should provide a default. Usually it's best to use `Optional` and a default of `None`.

Which you can then pass to `Meta`:

```pycon
>>> with_path = Meta('data-with-path.json', model=MyModel)
>>> with_path['a_path'] = Path('a path')
>>> with_path['a_path']
Path('a path')
>>> with_path['a_path'] = 1
cassini.meta.MetaValidationError: Invalid data in file: data-with-path.json, due to the following validation error:

1 validation error for MyModel
a_path
  Input should be an instance of Path [type=is_instance_of, input_value=1, input_type=int]
```

You may want to create a class, where certain attributes are stored in a `meta.json`. E.g. [NotebookTierBase][cassini.core.NotebookTierBase].

Attributes you want to store in `meta` are defined using [MetaAttr][cassini.meta.MetaAttr]. When accessing `MetaAttr` on an object, lookups are redirected to
that object's `meta` attribute.

This is easier to under by example:

```pycon
>>> from cassini.meta import MetaAttr, Meta
>>> 
>>> class MyClass:
... 
...     from_json = MetaAttr(json_type=str, attr_type=str)  # note here we provide strict types for from_json
... 
...     def __init__(self):
...         self.meta = Meta.create_meta('object-meta.json', owner=self)  # this does some magic, that we'll come back to.
... 
>>> my_instance = MyClass()
>>> my_instance.from_json = 'value'
>>> my_instance.from_json
value
>>> 
>>> my_instance.meta['from_json']
value # it's magically in the meta!
>>> with open('object-meta.json') as fs:
...     print(fs.read())
... 
{"from_json":"value"}
```

As you saw, we provided a strict `json_type` to `from_json` of `str`.

This type is enforced by Pydantic:

```pycon
>>> my_instance.from_json = 5  # raises ValidationError
1 validation error for MyClassMetaCache
from_json
  Input should be a valid string [type=string_type, input_value=5, input_type=int]
    For further information visit https://errors.pydantic.dev/2.9/v/string_type
```

This is because, the magic line:

```pycon 
Meta.create_meta('object-meta.json', owner=self)
```

Automatically generated a pydantic model for `MyClass`'s meta:

```pycon
>>> my_instance.meta.model
<class 'cassini.meta.MyClassMetaCache'>
```

Which includes a `from_json` field:

```pycon
>>> my_instance.meta.model.model_fields
{'from_json': FieldInfo(annotation=str, required=False, default=None)}
```

This is done using the [Meta.build_meta_model][cassini.meta.Meta.build_meta_model] function, which looks through an objects attributes 
(including those it inherited), finds all the `MetaAttr`, and then uses them to build fields of the model.
"""

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
    overload,
    TypeVar,
    Union,
    Literal,
)
from typing_extensions import Tuple, cast, Self, Type

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    create_model,
    JsonValue,
    ValidationError,
)
from pydantic.fields import FieldInfo


JSONType = TypeVar("JSONType")
AttrType = TypeVar("AttrType")


class MetaCache(BaseModel):
    """
    Base Model for Meta caches. Restricts fields to be json serialisable and performs validation on assignment.
    """

    __pydantic_extra__: Dict[str, JsonValue] = Field(init=False)
    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        revalidate_instances="subclass-instances",
        strict=True,
    )


class MetaValidationError(ValueError):
    """
    Custom exception thrown when an attempt is made to put a meta object into an invalid state.

    Attributes
    ----------
    file : Path
        The file the json data is stored in.
    validation_error : Exception
        Original pydantic `ValidationError` that caused this exception.
    """

    def __init__(self, *, validation_error: ValidationError, file: Path):
        message = f"Invalid data in file: {file}, due to the following validation error:\n\n{validation_error}"

        super().__init__(message)
        self.file = file
        self.validation_error = validation_error


class Meta:
    """
    Like a dictionary, except linked to a json file on disk. Caches the value of the json in itself.

    Pydantic is used to validate its contents and perform serialisation and deserialsation.

    This class can be used in conjunction with `MetaAttr`.

    Parameters
    ---------
    file : str, Path
           File Meta object stores information about.
    model : MetaCache
        Pydantic model representation of this meta object. Used to perform validation, and serial/deserialisation.

    Attributes
    ----------
    file : Path
        Path to the meta file.
    model : MetaCache
        Pydantic model representation of this meta object. Used to perform validation, and serial/deserialisation.
    """

    timeout: ClassVar[int] = 1
    my_attrs: ClassVar[List[str]] = ["model", "_cache", "_cache_born", "file"]

    def __init__(
        self, file: Union[str, Path], model: Union[Type[MetaCache], None] = None
    ):
        if isinstance(file, str):
            file = Path(file)

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
                    self.file.read_text(encoding="utf-8"), strict=False
                )
            except ValidationError as e:
                raise MetaValidationError(validation_error=e, file=self.file)

            self._cache_born = time.time()

        return self._cache

    def refresh(self) -> None:
        """
        Check age of cache, if stale then re-fetch.
        """
        if self.age >= self.timeout:
            self.fetch()

    def write(self) -> None:
        """
        Overwrite contents of cache into file.
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
        # it might not be possible for this to happen, because all fields have to have defaults.
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
        Like `dict.get`.
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

    @classmethod
    def build_meta_model(thisCls, wrappedCls):
        """
        Utility for building a `MetaModel` for a class.

        Takes a class and finds all `MetaAttr`, including those of parent classes.

        It then converts these to fields via [MetaAttr.as_field()][cassini.meta.MetaAttr.as_field] and uses these fields to create
        a model which bases [MetaCache][cassini.meta.MetaCache].

        This can then be passed to `Meta`'s model paramter.

        Parameters
        ----------
        wrappedCls : Type
            Class to inspect to build a model of `MetaAttr`.

        Returns
        -------
        model : MetaCache
            The newly built model.
        """
        meta_attrs = {}

        fields = set()

        for cls in wrappedCls.__mro__:
            for name in cls.__dict__:
                if name == "meta_model":
                    continue

                # attr = getattr(cls, name)
                # Avoid invoking accessors, which is not needed to find MetaAttr
                attr = cls.__dict__[name]

                if isinstance(attr, MetaAttr):
                    meta_attrs[name] = attr
                    fields.add(attr.as_field())

        cls_name = wrappedCls.__name__

        return create_model(
            f"{cls_name}MetaCache",
            __base__=MetaCache,
            **{name: field for name, field in fields},
        )

    @classmethod
    def create_meta(cls, path: Path, owner: object):
        """
        Create meta object, that stores its data at `path` which is owned by `owner`.

        If `owner` has a `meta_model` attribute, this will be passed to the `Meta` object as its created.

        If not, `build_meta_model` is used to find `MetaAttr` on `object` and build a model.

        Parameters
        ----------
        path : Path
            The path to store the created meta's data.
        owner : object
            The object this meta object will belong to. If the owner has `meta_model` attribute, this is passed to the `Meta`.

            If not, `build_meta_model` is used to build a model for that object.

        Returns
        -------
        meta : Meta
            `Meta` object with appropriate path and model.
        """
        if hasattr(owner, "meta_model") and owner.meta_model:
            model = owner.meta_model
        else:
            model = cls.build_meta_model(owner.__class__)

        return Meta(path, model)


def _null_func(val: Any) -> Any:
    return cast(JsonValue, val)


class MetaAttr(Generic[AttrType, JSONType]):
    """
    Accessor which allows storing object attributes in a `meta.json` file.

    For example, when an object tries to access a `MetaAttr` e.g. `object.my_meta_attr`, it will lookup the value of `MetaAttr.name` in `self.meta`.

    Note
    ----
    This requires the `Meta` object that attributes are stored in to be an attribute on the object called `meta`.

    Example
    -------

    ```pycon
    >>> from pathlib import Path
    >>> from cassini.meta import MetaAttr, Meta
    >>>
    >>> class MyClass:
    ...     def __init__(self):
    ...         self.meta = Meta.create_meta(path=Path('data.json'), owner=self)
    ...
    ...     name = MetaAttr(str, str)
    ...
    >>> obj = MyClass()
    >>> obj.name
    None
    >>> obj.name = 'Jeoff'
    >>> obj.name
    'Jeoff'
    >>> # the above is shorthand for
    >>> obj.meta['name'])
    >>>
    >>> with open('data.json') as fs:
    ...     print(fs.read())
    {"name":"Jeoff"}
    ```

    Parameters
    ----------
    json_type : JSONType
        These can just be simple native python types, such as `str` or `int`.
        Or a more complex [Pydantic compatible type](https://docs.pydantic.dev/latest/concepts/types/).

        In any case, pydantic will try and coerce the what's stored in `instance.meta.file` into this type.
    attr_type : AttrType
        The type you expect this MetaAttr to have internally. Usually this is the same as `json_type`.
    post_get : Callable[[JSONType], AttrType]
        function to apply to data after being loaded from json file
    pre_set : Callable[[AttrType], JSONType]
        function to apply to data before stored in json file.
    name : str
        key to lookup in meta. This can be set automatically.
    default : AttrType
        value to return if key not found in meta.
    cas_field : Union[None, Literal["core"], Literal["private"]]
        If provided, this field is included when this attribute is turned into a field for a `Meta.model`. If set to `'core'`
        or `'private'`, this field tells the jupyter cassini frontend that this attibute should not be displayed to the user
        to edit.

        Warning
        -------
        `'core'` is reserved for cassini internals, such as `started`.

    """

    def __init__(
        self,
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

        self.name: str = cast(str, name)
        self.default = default

        self.cas_field = cas_field

    def __set_name__(self, owner: object, name: str) -> None:
        if self.name is None:
            self.name = name

    @overload
    def __get__(self, instance: None, owner: object) -> Self:
        pass

    @overload
    def __get__(self, instance: object, owner: object) -> AttrType:
        pass

    def __get__(
        self, instance: Union[Any, None], owner: object
    ) -> Union[AttrType, Self]:
        if owner is None or instance is None:
            return self

        return self.post_get(instance.meta.get(self.name, self.default))

    def __set__(self, instance: Any, value: AttrType) -> None:
        setattr(instance.meta, self.name, self.pre_set(value))

    def as_field(self) -> Tuple[str, Tuple[Type[JSONType], FieldInfo]]:
        """
        Converts this `MetaAttr` into a `Field` to pass to pydantic, for building models.
        """
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
