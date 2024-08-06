from collections import defaultdict
from typing import Any, Dict, List, Union, Optional, Tuple, Generic, TypeVar
from types import MethodType
from typing_extensions import Self, Annotated
import datetime
from pathlib import Path
import shutil

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
    @classmethod
    def from_parent(cls, path: Path, parent: Self):
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
        for name, branch in level.items():
            path.append(name)

            if not branch:
                sub_paths.append(path.copy())
                path.clear()
            else:
                self._recurse_segments(branch, path, sub_paths)

    def compress(self) -> List[Path]:
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

    def __init__(self, name: str):
        if not env.is_sharing(env):
            raise RuntimeError("SharingTier objects should only be created in a sharing context i.e. via SharedProject instances")
    
        env.shareable_project.shared_tiers.append(self)

        self._accessed: Dict[str, Any] = {}
        self._called: Dict[str, Dict[ArgsKwargsType, Any]] = defaultdict(dict)
        self.name = name
        self._paths_used: List[NoseyPath] = []

        self._tier: TierABC = env.project[name]
        self.meta: Union[Meta, None] = getattr(self._tier, "meta", None)

        if self.meta:
            # Link this instance's meta attributes to _tier's meta object
            meta_manager: MetaManager = self._tier.__meta_manager__  # type: ignore[assignment]
            meta_manager.metas[self] = meta_manager.metas[self._tier]

    description = NotebookTierBase.description
    conclusion = NotebookTierBase.conclusion
    started = NotebookTierBase.started

    def handle_attr(self, name: str, val: Any) -> Any:
        if isinstance(val, (str, int, list, datetime.date, Path)):
            self._accessed[name] = val

        if isinstance(val, Path):
            val = NoseyPath(val)
            self._paths_used.append(val)

        if isinstance(val, TierABC):
            val = self._accessed[name] = SharingTier(val.name)

        return val

    def handle_call(self, method: str, args_kwargs: ArgsKwargsType, val: Any) -> Any:
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

    def dump(self, fs) -> SharedTierData:
        assert env.project

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
            **self._accessed, base_path=env.project.project_folder, called=called_obj
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
    def __init__(self, name: str) -> None:
        if not env.is_shared(env):
            raise RuntimeError("SharedTier instances should only be created in a Shared context i.e. one where SharedProject is used with no Project instances")
        
        self.name = name
        self.base_path: Union[Path, None] = None
        self.meta: Union[Meta, None] = None
        self._accessed: Dict[str, Any] = {}
        self._called: Dict[str, Dict[ArgsKwargsType, Any]] = {}

        folder, meta_file, frozen_file = env.shareable_project.make_paths(self)

        if meta_file.exists():
            self.meta = NotebookTierBase.__meta_manager__.create_meta(
                meta_file, self
            )

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
        assert env.shareable_project
        assert self.base_path

        return env.shareable_project.requires_path / path.relative_to(self.base_path)

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
    """

    def __init__(
        self, import_string: Union[str, None] = None, location: Union[Path, None] = None
    ) -> None:
        try:
            env.project = find_project(import_string)
        except (RuntimeError, KeyError):
            env.project = None

        env.shareable_project = self

        self.shared_tiers: List[SharingTier] = []
        self.location = location if location else Path("Shared")

    def env(self, name: str) -> Union[SharedTier, SharingTier]:
        if env.project:
            return SharingTier(name=name)
        else:
            return SharedTier(name=name)

    def __getitem__(self, name: str) -> Union[SharedTier, SharingTier]:
        if env.project:
            return SharingTier(name=name)
        else:
            return SharedTier(name=name)

    def make_paths(
        self, tier: Union[SharedTier, SharingTier]
    ) -> Tuple[Path, Path, Path]:
        outer = self.location / tier.name

        meta_file = outer / f"{tier.name}.json"
        frozen_file = outer / "frozen.json"

        return outer, meta_file, frozen_file

    @property
    def requires_path(self) -> Path:
        return self.location / "requires"

    def make_shared(self) -> None:
        if not env.is_sharing(env):
            raise RuntimeError("Trying to share tiers when not in a sharing context.")

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
                        env.project.project_folder
                    )
                    directory = destination if required.is_dir() else destination.parent
                    directory.mkdir(exist_ok=True, parents=True)

                    shutil.copy(required, destination)
