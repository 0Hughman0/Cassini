from collections import defaultdict
from typing import Any, Dict, List, Union, Optional, Tuple, Generic, TypeVar
from types import MethodType
from typing_extensions import Self, Annotated
import datetime
from pathlib import Path
import shutil
import copy


from pydantic import JsonValue, BaseModel, Field, ConfigDict, PlainSerializer, AfterValidator, WithJsonSchema

from . import env
from .core import TierABC, NotebookTierBase
from .meta import MetaManager
from .utils import find_project


SharableTierType = Annotated[
                    str,
                    AfterValidator(lambda n: SharedTier(n)),
                    PlainSerializer(lambda t: t.name, return_type=str)
                ]

ReturnType = TypeVar('ReturnType')
ArgsType = TypeVar('ArgsType')
KwargsType = TypeVar('KwargsType')


class SharedTierCall(BaseModel, Generic[ArgsType, KwargsType, ReturnType]):
    args: ArgsType
    kwargs: KwargsType
    returns: ReturnType


class ShareTierCalls(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        strict=True
    )

    truediv: List[SharedTierCall[Tuple[Union[str, Path]], Tuple, Path]] = Field(default=[])
    getitem: List[SharedTierCall[Tuple[str], Tuple, SharableTierType]] = Field(default=[])
    get_child: List[SharedTierCall[Tuple[str], Tuple, SharableTierType]] = Field(default=[])


class SharedTierData(BaseModel):
    """
    Ah crap, I have to create this dynamically I think, because round-trip validation can only work with strict types.
    """
    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        strict=True
    )    
    file: Optional[Path] = Field(default=None)
    folder: Optional[Path] = Field(default=None)
    parent: Optional[SharableTierType] = Field(default=None)
    href: Optional[str] = Field(default=None)
    id: Optional[str] = Field(default=None)
    identifiers: Optional[List[str]] = Field(default=None)
    meta_file: Optional[Path] = Field(default=None)
    called: ShareTierCalls


class NoseyPath:

    @classmethod
    def from_parent(cls, path, parent):
        obj = cls(path)
        obj._children = parent._children
        parent._children.append(obj)

        return obj
    
    def __init__(self, path):
        self._path = path
        self._children = []

    def __getattr__(self, name):
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
    
    def __truediv__(self, other):
        return self.__getattr__('__truediv__')(other)
    
    def __eq__(self, other):
        if isinstance(other, NoseyPath):
            other = other._path
        return self._path.__eq__(other)

    def __req__(self, other):
        if isinstance(other, NoseyPath):
            other = other._path
        return self._path.__req__(other)

    def __repr__(self):
        return f'<NoseyPath ({self._path})>'
    
    def _unchain(self):
        segments = {}

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
    
    def _recurse_segments(self, level, path, sub_paths):
        for name, branch in level.items():
            path.append(name)
            
            if not branch:
                sub_paths.append(path.copy())
                path.clear()
            else:
                self._recurse_segments(branch, path, sub_paths)

    def compress(self):
        if not self._children:
            return [self._path]
        
        tree = self._unchain()
        sub_paths = []
        path = []

        self._recurse_segments(tree, path, sub_paths)

        paths = [self._path.joinpath(*sub) for sub in sub_paths]

        return paths


class SharedProject:

    def __init__(self, import_string=None, location=None):
        try:
            env.project = find_project(import_string)
        except (RuntimeError, KeyError):
            env.project = None

        env.shareable_project = self

        self.shared_tiers = []
        self.location = location if location else Path('Shared')

    def env(self, name):
        if env.project:
            return SharingTier(name=name)
        else:
            return SharedTier(name=name)
        
    def __getitem__(self, name):
        if env.project:
            return SharingTier(name=name)
        else:
            return SharedTier(name=name)
        
    def make_paths(self, tier):
        outer = self.location / tier.name

        meta_file = outer / 'meta.json'
        frozen_file = outer / 'frozen.json'

        return outer, meta_file, frozen_file
    
    def make_shared(self):
        path = self.location
        
        path.mkdir(exist_ok=True)
        requires = path / 'requires'
        requires.mkdir(exist_ok=True)

        for stier in self.shared_tiers:
            tier_dir = path / stier.name
            tier_dir.mkdir(exist_ok=True)

            shutil.copy(stier.meta.file, tier_dir / 'meta.json')

            with open(tier_dir / 'frozen.json', 'w') as fs:
                stier.dump(fs)
            
            for required in stier.find_paths():
                if required.exists():
                    destination = requires / required.relative_to(env.project.project_folder)
                    directory = destination if required.is_dir() else destination.parent
                    directory.mkdir(exist_ok=True, parents=True)
                    
                    shutil.copy(required, destination)


class SharingTier:

    def __init__(self, name):
        env.shareable_project.shared_tiers.append(self)

        self._accessed = {}
        self._called = defaultdict(dict)
        self.name = name
        self._paths_used = []
        
        self._tier = env.project[name]
        self.meta = self._tier.meta
        
        # Link this instance's meta attributes to _tier's meta object
        meta_manager = self._tier.__meta_manager__
        meta_manager.metas[self] = meta_manager.metas[self._tier]
    
    description = NotebookTierBase.description
    conclusion = NotebookTierBase.conclusion
    started = NotebookTierBase.started

    def handle_attr(self, name, val):
        if isinstance(val, (str, int, list, datetime.date, Path)):
            self._accessed[name] = val

        if isinstance(val, Path):
            val = NoseyPath(val)
            self._paths_used.append(val)

        if isinstance(val, TierABC):
            val = self._accessed[name] = SharingTier(val)

        return val
    
    def handle_call(self, method, args_kwargs, val):    
        if isinstance(val, TierABC):
            val = SharingTier(val.name)

        self._called[method][args_kwargs] = val

        if isinstance(val, Path):
            val = NoseyPath(val)
            self._paths_used.append(val)

        return val

    def __getattr__(self, name):
        val = getattr(self._tier, name)

        if isinstance(val, MethodType):
            handle_call = self.handle_call
            meth = val

            def wrapper(*args, **kwargs):
                args_kwargs = (args, tuple(kwargs.items()))
                
                result = meth(*args, **kwargs)

                return handle_call(name, args_kwargs, result)
    
            val = wrapper
        else:
            val = self.handle_attr(name, val)
        
        return val
    
    def __getitem__(self, other):
        return self.__getattr__('__getitem__')(other)
    
    def __truediv__(self, other):
        return self.__getattr__('__truediv__')(other)
        
    def __eq__(self, other):
        if isinstance(other, (SharedTier, SharingTier)):
            return self.name == other.name
        else:
            raise NotImplementedError()
        
    def __hash__(self):
        return hash(self.name)

    def dump(self, fs):
        called = defaultdict(list)
        
        for meth, calls in self._called.items():
            for args_kwargs, returns in calls.items():
                called[meth.strip('_')].append({
                        'args': args_kwargs[0],
                        'kwargs': args_kwargs[1],
                        'returns': returns
                        })

        model = SharedTierData(
            **self._accessed,
            called=called
        )

        json_str = model.model_dump_json()
        fs.write(json_str)

    def find_paths(self):
        """
        Go through self._accessed, self._called and find the paths and get their full extent.
        """
        paths = []

        for nosey_path in self._paths_used:
            paths.extend(nosey_path.compress())

        return paths


class SharedTier:
    
    def __init__(self, name):
        self.name = name

        if env.shareable_project:
            folder, meta_file, frozen_file = env.shareable_project.make_paths(self)
            self.meta = NotebookTierBase.__meta_manager__.create_meta(meta_file, self)
            
            with open(frozen_file) as fs:
                model = SharedTierData.model_validate_json(fs.read())

                accessed = model.model_dump(exclude={'called'})
                self._accessed = accessed

                raw_called = model.called.model_dump()

                called = defaultdict(dict)

                for method, calls in raw_called.items():
                    if method in ['truediv', 'getitem']:
                        method = f'__{method}__'
                    
                    for call in calls:
                        called[method][(call['args'], call['kwargs'])] = call['returns']

                self._called = called
        else:
            self.meta = None
            self._accessed = {}
            self._called = {}

    description = NotebookTierBase.description
    conclusion = NotebookTierBase.conclusion
    started = NotebookTierBase.started

    def __getattr__(self, name):
        if name in self._accessed:
            return self._accessed[name]
        else:
            def meth(*args, **kwargs):
                args_kwargs = (args, tuple(kwargs))

                return self._called[name][args_kwargs]
            
            return meth
    
    def __getitem__(self, other):
        return self.__getattr__('__getitem__')(other)
    
    def __truediv__(self, other):
        return self.__getattr__('__truediv__')(other)
    
    def __eq__(self, other):
        if isinstance(other, (SharedTier, SharingTier)):
            return self.name == other.name
        else:
            raise NotImplementedError()
        
    def __hash__(self) -> int:
        return hash(self.name)
