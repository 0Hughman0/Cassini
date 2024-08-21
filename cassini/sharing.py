from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Union, Optional, Tuple, Generic, TypeVar
from types import MethodType
from typing_extensions import Self, Annotated
import datetime
from pathlib import Path
import shutil
from io import TextIOWrapper

from pydantic import (
    JsonValue,
    BaseModel,
    Field,
    ConfigDict,
    PlainSerializer,
    AfterValidator,
)

from . import env
from .core import TierABC, NotebookTierBase
from .meta import Meta, MetaManager
from .utils import find_project


ShareableTierType = Annotated[
    str,
    AfterValidator(lambda n: SharedTier(n)),
    PlainSerializer(lambda t: t.name, return_type=str),
]

ReturnType = TypeVar("ReturnType")


class _SharedTierCall(BaseModel, Generic[ReturnType]):
    args: Tuple[JsonValue, ...]
    kwargs: Tuple[Tuple[str, JsonValue], ...]
    returns: ReturnType


TrueDivCall = _SharedTierCall[Path]
GetItemCall = _SharedTierCall[ShareableTierType]
GetChildCall = _SharedTierCall[ShareableTierType]
SharedTierCall = _SharedTierCall[JsonValue]


class SharedTierCalls(BaseModel):
    __pydantic_extra__: Dict[str, List[SharedTierCall]] = Field(init=False)
    model_config = ConfigDict(extra="allow", validate_assignment=True, strict=True)

    truediv: List[TrueDivCall] = Field(default=[])
    getitem: List[GetItemCall] = Field(default=[])
    get_child: List[GetChildCall] = Field(default=[])


class SharedTierData(BaseModel):
    """
    Serialised form of a shared tier.

    Attributes
    ----------
    file: Optional[Path]
        Absolute path to the file for the notebook.
    folder: Optional[Path]
        Absolute path for folder for the tier.
    parent: Optional[str]
        name of the tier's parent
    href: Optional[str]
        tier's href url
    id: Optional[str]
        the tier's id
    identifiers: List[str]
        the tier's identifiers
    meta_file: Optional[Path]
        Absolute path to the meta file.
    base_path: Path
        Base path used when generating URLs.
    called: SharedTierCalls
        Serialised version of calls made to this tier prior to sharing.
    """
    model_config = ConfigDict(extra="allow", validate_assignment=True, strict=True)

    file: Optional[Path] = Field(default=None)
    folder: Optional[Path] = Field(default=None)
    parent: Optional[ShareableTierType] = Field(default=None)
    href: Optional[str] = Field(default=None)
    id: Optional[str] = Field(default=None)
    identifiers: Optional[List[str]] = Field(default=None)
    meta_file: Optional[Path] = Field(default=None)
    base_path: Path

    called: SharedTierCalls


class NoseyPath:
    """
    Wrapper for `Path` objects that allows tracking of what paths have been generated from that object.

    This 'nosey' behaviour is used to keep track of which files are accessed through `Path` objects.

    Parameters
    ----------
    path: Path
        path to wrap around.
    """
    @classmethod
    def from_parent(cls, path: Path, parent: Self):
        """
        Create a new `NoseyPath` as a 'child' of `parent`.

        Allows parent to keep track of its child paths.
        """
        obj = cls(path)
        obj._children = parent._children
        parent._children.append(obj)

        return obj

    def __init__(self, path: Path) -> None:
        self._path: Path = path
        self._children: List[Self] = []

    def __getattr__(self, name: str) -> Any:
        val = getattr(self._path, name)

        if isinstance(val, MethodType):

            def wrapper(*args, **kwargs):
                result = val(*args, **kwargs)

                if isinstance(result, Path):
                    result = NoseyPath.from_parent(result, self)

                return result

            return wrapper

        if isinstance(val, Path):
            val = NoseyPath.from_parent(val, self)

        return val

    def __truediv__(self, other: Union[str, Path]) -> Path:
        return self.__getattr__("__truediv__")(other)

    def __eq__(self, other):
        if isinstance(other, NoseyPath):
            other = other._path
        return self._path.__eq__(other)

    def __repr__(self):
        return f"<NoseyPath ({self._path})>"

    def _unchain(self) -> Dict[str, Any]:
        """
        Creates a tree structure that contains all segments of the children of this object.
        """
        segments: Dict[str, Any] = {}

        for child in self._children:
            path = segments
            if child.is_absolute():
                child = child.relative_to(self._path)

            for part in child.parts:
                next_path = path.get(part)

                if next_path is None:
                    next_path = path[part] = {}

                path = next_path

        return segments

    def _recurse_segments(
        self, level: Dict[str, Any], path: List[str], sub_paths: List[List[str]]
    ):
        """
        Recurse through the `level`, keeping track of the `path` and add complete paths to sub_paths.
        """
        for name, branch in level.items():
            path.append(name)

            if not branch:
                sub_paths.append(path.copy())
                path.clear()
            else:
                self._recurse_segments(branch, path, sub_paths)

    def compress(self) -> List[Path]:
        """
        Create a list of complete paths that result from this path object e.g. through `__truediv__` calls.
        """
        if not self._children:
            return [self._path]

        tree = self._unchain()
        path: List[str] = []
        sub_paths: List[List[str]] = []

        self._recurse_segments(tree, path, sub_paths)

        paths = [self._path.joinpath(*sub) for sub in sub_paths]

        return paths


ArgsKwargsType = Tuple[Tuple[Any, ...], Tuple[Tuple[str, Any], ...]]


class SharingTier:
    """
    Wrapper around a `TierABC` object that keeps track of what attributes are accessed 
    and what methods are called.

    This class can then create a serialised version of `tier` using `SharedTierData`, which can 
    allow a `SharedTier` object to be created that emulates this `SharingTier`.

    This class should not be created directly. Instead, `SharedProject` objects should be used.

    Parameters
    ----------
    name: str
        The name of the tier to wrap around.

    Notes
    -----
    This class is not in a valid state until `SharingTier.load` has been called.
    """
    def __init__(self, name: str):
        self.shared_project: Union[None, SharedProject] = None

        self._accessed: Dict[str, Any] = {}
        self._called: Dict[str, Dict[ArgsKwargsType, Any]] = defaultdict(dict)
        self.name = name
        self._paths_used: List[NoseyPath] = []

        self._tier: Union[TierABC, None] = None
        self.meta: Union[Meta, None] = None

    @classmethod
    def with_project(cls, name: str, shared_project: SharedProject):
        """
        Create a `SharingTier` object, and load it from `shared_project`.

        Recommended way to create `SharingTier` objects in contexts where the `shared_project` is available.
        """
        tier = cls(name)
        tier.load(shared_project=shared_project)

        shared_project.shared_tiers.append(tier)

        return tier

    def load(self, shared_project: SharedProject):
        """
        Sync this `SharingTier` to wrap around the tier with name `self.name` from the `shared_project`.
        """
        self.shared_project = shared_project

        self._tier = shared_project.project[self.name]

        self.meta = getattr(self._tier, "meta", None)

        if isinstance(self._tier, NotebookTierBase) and self.meta:
            # Link this instance's meta attributes to _tier's meta object
            meta_manager: MetaManager = self._tier.__meta_manager__  # type: ignore[attr-defined]
            meta_manager.metas[self] = meta_manager.metas[self._tier]

    description = NotebookTierBase.description
    conclusion = NotebookTierBase.conclusion
    started = NotebookTierBase.started

    def handle_attr(self, name: str, val: Any) -> Any:
        """
        Handle attribute access to cache the result appropriately.
        """
        if isinstance(val, (str, int, list, datetime.date, Path)):
            self._accessed[name] = val

        if isinstance(val, Path):
            val = NoseyPath(val)
            self._paths_used.append(val)

        if isinstance(val, TierABC):
            val = self._accessed[name] = SharingTier(val.name)

        return val

    def handle_call(self, method: str, args_kwargs: ArgsKwargsType, val: Any) -> Any:
        """
        Handle call to a method to allow caching of the result.
        """
        if isinstance(val, TierABC):
            val = SharingTier(val.name)

        self._called[method][args_kwargs] = val

        if isinstance(val, Path):
            val = NoseyPath(val)
            self._paths_used.append(val)

        return val

    def __getattr__(self, name: str) -> Any:
        val = getattr(self._tier, name)

        if isinstance(val, MethodType):
            handle_call = self.handle_call
            meth = val

            def wrapper(*args, **kwargs) -> Any:
                args_kwargs = (args, tuple(kwargs.items()))

                result = meth(*args, **kwargs)

                return handle_call(name, args_kwargs, result)

            val = wrapper
        else:
            val = self.handle_attr(name, val)

        return val

    def __getitem__(self, other) -> Self:
        return self.__getattr__("__getitem__")(other)

    def __truediv__(self, other) -> Path:
        return self.__getattr__("__truediv__")(other)

    def __eq__(self, other):
        if isinstance(other, (SharedTier, SharingTier)):
            return self.name == other.name
        else:
            raise NotImplementedError()

    def __hash__(self):
        return hash(self.name)

    def dump(self, fs: TextIOWrapper) -> SharedTierData:
        """
        Serialise the cached version of the attribute and function calls to wrapped tier.

        Parameters
        ----------
        fs: TextIOWrapper
            Stream to write serialised data to. 

        Returns
        -------
        model: SharedTierData
            Model of this instance.
        """

        called = defaultdict(list)

        for meth, calls in self._called.items():
            for args_kwargs, returns in calls.items():
                called[meth.strip("_")].append(
                    {
                        "args": args_kwargs[0],
                        "kwargs": args_kwargs[1],
                        "returns": returns,
                    }
                )

        called_obj = SharedTierCalls(**called)  # type: ignore[arg-type]

        model = SharedTierData(
            **self._accessed, base_path=self.project.project_folder, called=called_obj
        )

        json_str = model.model_dump_json()
        fs.write(json_str)

        return model

    def find_paths(self) -> List[Path]:
        """
        Go through self._accessed, self._called and find the paths and get their full extent.
        """
        paths: List[Path] = []

        for nosey_path in self._paths_used:
            paths.extend(nosey_path.compress())

        return paths


class SharedTier:
    """
    A class that emulates a `TierABC` object without needing a full cassini `Project` configured.

    This class is the mirror of `SharingTier` objects, which create the serialised files required
    to load these objects. 

    Parameters
    ----------
    name: str
        The name of the tier to emulate.

    Notes
    -----
    This class is not in a valid state until `SharingTier.load` has been called.
    """
    def __init__(self, name: str) -> None:
        self.name = name
        self.shared_project: Union[None, SharedProject] = None
        self.base_path: Union[Path, None] = None
        self.meta: Union[Meta, None] = None
        self._accessed: Dict[str, Any] = {}
        self._called: Dict[str, Dict[ArgsKwargsType, Any]] = {}

    @classmethod
    def with_project(cls, name: str, shared_project: SharedProject):
        """
        Create a `SharedTier` instance, and load it from `shared_project`.
        """
        tier = cls(name)
        tier.load(shared_project)
        return tier

    def load(self, shared_project: SharedProject):
        """
        Load the contents of the shared tier into this object from the `shared_project`.
        """
        self.shared_project = shared_project

        folder, meta_file, frozen_file = shared_project.make_paths(self)

        if meta_file.exists():
            self.meta = NotebookTierBase.__meta_manager__.create_meta(meta_file, self)

        with open(frozen_file) as fs:
            model = SharedTierData.model_validate_json(fs.read())
            self.base_path = model.base_path

            accessed = model.model_dump(exclude={"called", "base_path"})
            self._accessed = accessed

            raw_called = model.called.model_dump()

            called: Dict[str, Any] = defaultdict(dict)

            for method, calls in raw_called.items():
                if method in ["truediv", "getitem"]:
                    method = f"__{method}__"

                for call in calls:
                    called[method][(call["args"], call["kwargs"])] = call["returns"]

            self._called = called

    description = NotebookTierBase.description
    conclusion = NotebookTierBase.conclusion
    started = NotebookTierBase.started

    def adjust_path(self, path: Path) -> Path:
        """
        Correct path to account for new base path.
        """
        assert self.shared_project
        assert self.base_path

        return self.shared_project.requires_path / path.relative_to(self.base_path)

    def __getattr__(self, name: str) -> Any:
        if name in self._accessed:
            val = self._accessed[name]

            if isinstance(val, Path):
                val = self.adjust_path(val)

            return val
        else:

            def meth(*args, **kwargs):
                args_kwargs = (args, tuple(kwargs))

                val = self._called[name][args_kwargs]

                if isinstance(val, Path):
                    val = self.adjust_path(val)

                return val

            return meth

    def __getitem__(self, other: Any) -> Self:
        return self.__getattr__("__getitem__")(other)

    def __truediv__(self, other: Any) -> Path:
        return self.__getattr__("__truediv__")(other)

    def __eq__(self, other):
        if isinstance(other, (SharedTier, SharingTier)):
            return self.name == other.name
        else:
            raise NotImplementedError()

    def __hash__(self) -> int:
        return hash(self.name)


class SharedProject:
    """
    Shareable version of `Project`. Allows sharing of notebooks that use Cassini with users who don't have
    Cassini set up.

    This class automatically detects if it's being used in a _sharing_ or _shared_ context and returns the appropriate values.
    It does this by trying to use `cassini.utils.find_project` to get ahold of your project instance. If it can't find 
    one, it assumes the code context is _shared_. If it does find one, it assumes you are still sharing this project.

    This object can be used as a substitute for a `Project` instance.

    Parameters
    ----------
    import_string: Optional[str]
        If created in a sharing context, this is used to find the `project` object, using the syntax specified 
        in `cassini.utils.find_project`.
    location: Optional[Path]
        location to store/ load the shared project data. Defaults to `Path("Shared")`.
    """

    def __new__(cls, *args, **kwargs) -> Self:
        if env.shareable_project:
            raise RuntimeError(
                "Only one shareable project instance should be created per interpretter"
            )

        obj = super().__new__(cls)
        env.shareable_project = obj
        return obj

    def __init__(
        self, import_string: Union[str, None] = None, location: Union[Path, None] = None
    ) -> None:
        try:
            self.project = find_project(import_string)
        except (RuntimeError, KeyError):
            self.project = None

        self.shared_tiers: List[SharingTier] = []
        self.location = location if location else Path("Shared")

    def env(self, name: str) -> Union[SharedTier, SharingTier]:
        """
        Equivalent to `Project.env`, except will return the appropriate `SharingTier` or `SharedTier`, depending
        on which is appropriate.

        Parameters
        ----------
        name: str
            Name of the tier to get.
        """
        if self.project:
            tier = SharingTier.with_project(name=name, shared_project=self)
            env.update(tier)
            return tier
        else:
            return SharedTier.with_project(name=name, shared_project=self)

    def __getitem__(self, name: str) -> Union[SharedTier, SharingTier]:
        """
        Equivalent to `Project.env`, except will return the appropriate `SharingTier` or `SharedTier`, depending
        on which is appropriate.

        Parameters
        ----------
        name: str
            Name of the tier to get.
        """
        if self.project:
            return SharingTier.with_project(name=name, shared_project=self)
        else:
            return SharedTier.with_project(name=name, shared_project=self)

    def make_paths(
        self, tier: Union[SharedTier, SharingTier]
    ) -> Tuple[Path, Path, Path]:
        """
        Build paths required for sharing a given tier object.

        Returns
        -------
        outer: Path
            The folder the tier data is stored in.
        meta_file: Path
            A path to the meta_file of that tier
        frozen_file: Path
            The path to the `frozen.json` file, where the tier's attributes and calls are stored.
        """
        outer = self.location / tier.name

        meta_file = outer / f"{tier.name}.json"
        frozen_file = outer / "frozen.json"

        return outer, meta_file, frozen_file

    @property
    def requires_path(self) -> Path:
        """
        Path for requires folder.
        """
        return self.location / "requires"

    def make_shared(self) -> None:
        """
        Create a shared version of this project.

        Will create a folder a `self.location`. Will then iterate all `tier` objects accessed in this context 
        and serialise them. 

        Additionally, and files that tiers used access will be copied into the `self.requires_path`. 
        """
        if not self.project:
            raise RuntimeError("Trying to share tiers when not in a sharing context.")

        project = self.project

        path = self.location

        path.mkdir(exist_ok=True)
        self.requires_path.mkdir(exist_ok=True)

        for stier in self.shared_tiers:
            tier_dir, meta_file, frozen_file = self.make_paths(stier)
            tier_dir.mkdir(exist_ok=True)

            if stier.meta:
                shutil.copy(stier.meta.file, meta_file)

            with open(frozen_file, "w") as fs:
                stier.dump(fs)

            for required in stier.find_paths():
                if required.exists():
                    destination = self.requires_path / required.relative_to(
                        project.project_folder
                    )
                    directory = destination if required.is_dir() else destination.parent
                    directory.mkdir(exist_ok=True, parents=True)

                    shutil.copy(required, destination)
