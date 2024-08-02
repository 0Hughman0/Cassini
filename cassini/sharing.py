from collections import defaultdict
from typing import Any, Dict, List, Union, Optional, Tuple
from types import MethodType
from typing_extensions import Self, Annotated
import datetime
from pathlib import Path
import shutil
import copy


from pydantic import JsonValue, BaseModel, Field, ConfigDict, PlainSerializer, AfterValidator, WithJsonSchema

from . import env
from .core import TierABC
from .utils import find_project


SharableTierType = Annotated[
                    str,
                    AfterValidator(lambda n: SharingTier(n)),
                    PlainSerializer(lambda t: t._name, return_type=str)
                ]


class ShareTierCalls(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        strict=True
    )

    truediv: Dict[Tuple[Union[str, Path]], Path] = Field(default={})
    getitem: Dict[Tuple[str], SharableTierType] = Field(default={})
    get_child: Dict[Tuple[str], SharableTierType] = Field(default={})


class SharedTierData(BaseModel):
    """
    Ah crap, I have to create this dynamically I think, because round-trip validation can only work with strict types.
    """
    model_config = ConfigDict(
        extra="allow",
        validate_assignment=True,
        strict=True
    )
    name: str
    description: str = Field(default='')  # these should probably just derive from the meta.
    conclusion: str = Field(default='')
    file: Optional[Path] = Field(default=None)
    folder: Optional[Path] = Field(default=None)
    parent: Optional[SharableTierType] = Field(default=None)
    href: Optional[str] = Field(default=None)
    id: str = Field(default=None)
    identifiers: List[str] = Field(default=None)
    meta_file: Optional[Path] = Field(default=None)
    started: Optional[datetime.datetime] = Field(default=None)

    called: ShareTierCalls
    # 'meta' # requires special treatment!


class NoseyPath:

    @classmethod
    def replace_instance(cls, instance):
        obj = cls(instance._path)
        obj._previous_instances.append(instance)
        return obj

    @classmethod
    def from_parent(cls, path, parent):
        obj = cls(path)
        obj._children = parent._children
        parent._children.append(obj)

        return obj
    
    @classmethod
    def from_path_list(cls, path_list):
        obj = cls(path_list[0])
        obj._children = path_list[1:]

        return obj

    def __init__(self, path):
        self._path = path
        self._children = []
        self._previous_instances = []

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

        for previous in self._previous_instances:
            subs = previous.compress()
            paths.extend(subs)

        return paths


class _SharedProject:

    def __init__(self):
        self.import_string = None
        self.project = None
    
    def __call__(self, import_string) -> Self:
        self.import_string = import_string
        return self
    
    def find_project(self):
        try:
            self.project = find_project(import_string=self.import_string)
        except RuntimeError:
            self.project = None
    
    def env(self, name):
        if not self.project:
            self.find_project()
        return SharingTier(name=name, project=self.project)
    
    def __getitem__(self, name):
        if not self.project:
            self.find_project()
        return SharingTier(name=name, project=self.project)
    
    def make_shared(self, path: Path, stiers):
        path.mkdir(exist_ok=True)
        requires = path / 'requires'
        requires.mkdir(exist_ok=True)

        for stier in stiers:
            tier_dir = path / stier.name
            tier_dir.mkdir(exist_ok=True)

            shutil.copy(stier.meta.file, tier_dir / 'meta.json')

            with open(tier_dir / 'frozen.json', 'w') as fs:
                stier.dump(fs)
            
            for required in stier.find_paths():
                if required.exists():
                    destination = requires / required.relative_to(self.project.project_folder)
                    directory = destination if required.is_dir() else destination.parent
                    directory.mkdir(exist_ok=True, parents=True)
                    
                    shutil.copy(required, destination)


shared_project = _SharedProject()


class SharingTier:

    def __init__(self, name, project=None):
        self._accessed = {}
        self._called = defaultdict(dict)
        self._project = project
        self._name = name
        self._paths_used = []
        
        if project:
            self._tier = project[name]
        else:
            self._tier = None
            # self._load_cache()

    def handle_attr(self, name, val):
        if isinstance(val, (str, int, list, datetime.date, Path)):
            self._accessed[name] = val

        if isinstance(val, Path):
            val = NoseyPath(val)
            self._paths_used.append(val)

        if isinstance(val, TierABC):
            val = self._accessed[name] = SharingTier(val, self._project)

        return val
    
    def handle_call(self, method, args_kwargs, val):    
        if isinstance(val, TierABC):
            val = SharingTier(val.name, self._project)

        self._called[method][args_kwargs] = val

        if isinstance(val, Path):
            val = NoseyPath(val)
            self._paths_used.append(val)

        return val

    def __getattr__(self, name):
        if self._project:
            val = getattr(self._tier, name)

            if isinstance(val, MethodType):
                handle_call = self.handle_call
                meth = val

                def wrapper(*args, **kwargs):
                    args_kwargs = (*args, *tuple(kwargs.items()))
                    
                    result = meth(*args, **kwargs)

                    return handle_call(name, args_kwargs, result)
        
                val = wrapper
            else:
                val = self.handle_attr(name, val)
            
            return val
        else:
            return self._accessed[name]
        
    def __getitem__(self, other):
        return self.__getattr__('__getitem__')(other)
    
    def __truediv__(self, other):
        return self.__getattr__('__truediv__')(other)
        
    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self._name == other._name
        else:
            raise NotImplementedError()

    def dump(self, fs):
        model = SharedTierData(
            **self._accessed,
            called=self._called
        )

        json_str = model.model_dump_json()
        fs.write(json_str)

    def load(self, fs):
        model = SharedTierData.model_validate_json(fs.read())

        accessed = model.model_dump(exclude={'called'})
        self._accessed = accessed

        called = model.called.model_dump()

        called['__truediv__'] = called.get('truediv', {})
        called['__getitem__'] = called.get('getitem', {})
        self._called = called

    def find_paths(self):
        """
        Go through self._accessed, self._called and find the paths and get their full extent.
        """
        paths = []

        for nosey_path in self._paths_used:
            paths.extend(nosey_path.compress())

        return paths


class SharedTier:
    pass

