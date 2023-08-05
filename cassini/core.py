from __future__ import annotations

import datetime
import html
import json
import os
import time
from pathlib import Path
from collections import defaultdict

from typing import Any, KeysView, List, Type, Tuple, Iterator, Union, Dict, ClassVar, Sequence, Optional, cast

import pandas as pd  # type: ignore

from .ipygui import BaseTierGui
from .accessors import MetaAttr, cached_prop, cached_class_prop
from .utils import FileMaker, open_file
from .environment import env, _Env, Project
from .config import config


class Meta:
    """
    Like a dictionary, except linked to a json file on disk. Caches the value of the json in itself.

    Arguments
    ---------
    file: Path
           File Meta object stores information about.
    """

    timeout: ClassVar[int] = 1
    my_attrs: ClassVar[List] = ['_cache', '_cache_born', 'file']

    def __init__(self, file: Path):
        self._cache: dict = {}
        self._cache_born: float = 0.0
        self.file: Path = file

    @property
    def age(self) -> float:
        """
        time in secs since last fetch
        """
        return time.time() - self._cache_born

    def fetch(self) -> dict:
        """
        Fetches values from the meta file and updates them into `self._cache`.

        Notes
        -----
        This doesn't *overwrite* `self._cache` with meta contents, but updates it. Meaning new stuff to file won't be
        overwritten, it'll just be loaded.
        """
        if self.file.exists():
            self._cache.update(json.loads(self.file.read_text()))
            self._cache_born = time.time()
        return self._cache

    def refresh(self):
        """
        Check age of cache, if stale then re-fetch
        """
        if self.age >= self.timeout:
            self.fetch()

    def write(self):
        """
        Overwrite contents of cache into file
        """
        # Danger moment - writing bad cache to file.
        with self.file.open('w') as f:
            json.dump(self._cache, f)

    def __getitem__(self, item: str) -> Any:
        self.refresh()
        return self._cache[item]

    def __setitem__(self, key: str, value: Any):
        self.__setattr__(key, value)

    def __getattr__(self, item: str) -> Any:
        self.refresh()
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)

    def __setattr__(self, name: str, value: Any) -> Any:
        if name in self.my_attrs:
            super().__setattr__(name, value)
        else:
            self.fetch()
            self._cache[name] = value
            self.write()

    def __delitem__(self, key: str):
        self.fetch()
        del self._cache[key]
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

    def keys(self) -> KeysView:
        """
        like `dict.keys`
        """
        self.refresh()
        return self._cache.keys()


class TierMeta(type):
    """
    Metaclass mixin for the TierBase. Needed to ensure that each Tier Class has its own cache.
    """
    cache: Dict[Tuple[str, ...], TierBase]

    def __new__(cls, name, bases, dct):
        kls = super().__new__(cls, name, bases, dct)
        kls.cache = {}  # ensures each TierBase class has its own cache
        return kls


class TierBase(metaclass=TierMeta):
    """
    Base class for creating Tiers

    Parameters
    ----------
    *identifiers : str
        sequence of strings that identify this tier. With the final identifier being unique.

    Attributes
    ----------
    rank : int
        Class attribute, specifying the rank of this `Tier`
    id_regex: str
        Class attribute, regex that defines a group that matches the id of a `Tier` object from a name... except the name isn't the full
        name, but with parent names stripped, see examples basically!
    hierarchy : list
        Class attribute, hierarchy of `Tier`s.
    description : str
        returns the description found in a `Tier` _instance's meta file
    started : datetime
        return a datetime parsed using `config.DATE_FORMAT` found in meta file
    conclusion : str
        return the conclusion found in a `Tier` _instance's meta file.
    rank : int
        (class attribute) rank of this `Tier` class (not to be set directly)
    id_regex : str
        (class attribute) regex used to restrict form of `Tier` object ids. Should contain 1 group that captures the id.
    gui_cls : Any
        (class attribute) The class called upon initialisation to use as gui for this object. Constructor should take `self` as first
        argument.
    """

    rank: ClassVar[int] = -1
    id_regex: ClassVar[str] = r'(\d+)'

    gui_cls = BaseTierGui

    @cached_class_prop
    def hierarchy(cls) -> List[Type[TierBase]]:
        """
        Gets the hierarchy from `env.project`.
        """
        assert env.project
        return env.project.hierarchy


    @cached_class_prop
    def pretty_type(cls) -> str:
        """
        Name used to display this Tier. Defaults to `cls.__name__`.
        """
        return cls.__name__
    
    @cached_class_prop
    def short_type(cls) -> str:
        """
        Name used to programmatically refer to instances of this `Tier`.

        Default, take pretty type, make lowercase and remove vowels.
        """
        return cls.pretty_type.lower().translate(str.maketrans(dict.fromkeys('aeiou')))

    @cached_class_prop
    def name_part_template(cls) -> str:
        """
        Python template that's filled in with `self.id` to create segment of the `Tier` object's name.
        """
        return cls.pretty_type + '{}'

    @cached_class_prop
    def name_part_regex(cls) -> str:
        """
        Regex where first group matches `id` part of string. Default is fill in `cls.name_part_template` with
        `cls.id_regex`.
        """
        return cls.name_part_template.format(cls.id_regex)

    @cached_class_prop
    def parent_cls(cls) -> Union[Type[TierBase], None]:
        """
        `Tier` above this `Tier`, `None` if doesn't have one
        """
        assert env.project

        if cls.rank is None or cls.rank <= 0:
            return None
        return cls.hierarchy[cls.rank - 1]

    @cached_class_prop
    def child_cls(cls) -> Union[Type[TierBase], None]:
        """
        `Tier` below this `Tier`, `None` if doesn't have one
        """
        assert env.project

        if cls.rank is None or cls.rank >= (len(cls.hierarchy) - 1):
            return None
        return cls.hierarchy[cls.rank + 1]

    @cached_class_prop
    def default_template(cls) -> Union[Path, None]:
        """
        Template used to render a tier file by default.
        """
        return Path(cls.pretty_type) / f'{cls.pretty_type}.tmplt.ipynb'

    @cached_class_prop
    def _meta_folder_name(cls) -> str:
        """
        Form of meta folder name. (Just fills in `config.META_DIR_TEMPLATE` with `cls.short_type`).
        """
        return config.META_DIR_TEMPLATE.format(cls.short_type)

    def __new__(cls, *args: str, **kwargs):
        obj = cls.cache.get(args)
        if obj:
            return obj
        obj = object.__new__(cls)
        cls.cache[args] = obj
        return obj

    @classmethod
    def parse_name(cls, name: str) -> Tuple[str, ...]:
        """
        Ask `env.project` to parse name.
        """
        if not env.project:
            raise RuntimeError("Attempting to parse a name before a project is initialised")
        return env.project.parse_name(name)

    @classmethod
    def _iter_meta_dir(cls, path: Path) -> Iterator[Tuple[str, ...]]:
        for meta_file in os.scandir(path):
            if not meta_file.is_file() or not meta_file.name.endswith('.json'):
                continue
            yield cls.parse_name(meta_file.name[:-5])

    def __init__(self, *args: str):
        self._identifiers = tuple(filter(None, args))
        self.gui = self.gui_cls(self)

        if len(self._identifiers) != self.rank:
            raise ValueError(f"Invalid number of identifiers in {self._identifiers}, expecting {self.rank}.")

        if self.parse_name(self.name) != self.identifiers:
            raise ValueError(f"Invalid identifiers - {self._identifiers}, resulting name ('{self.name}') not in a parsable form ")

        if self.meta_file:
            self.meta: Meta = Meta(self.meta_file)

    def setup_files(self, template: Union[Path, None] = None):
        """
        Create all the files needed for a valid `Tier` object to exist.

        This includes its `.ipynb` file, its parent folder, its own folder and its `Meta` file.

        Will render `.ipynb` file as Jinja template engine, passing to the template `self` with names given by
        `self.short_type` and `tier`.

        Parameters
        ----------
        template : Path
            path to template file to render to create `.ipynb` file.
        """
        if template is None:
            template = self.default_template

        if self.exists():
            raise FileExistsError(f"Meta for {self.name} exists already")

        if self.file and self.file.exists():
            raise FileExistsError(f"Notebook for {self.name} exists already")

        print(f"Creating files for {self.name}")

        print(f"Meta ({self.meta_file})")

        with FileMaker() as maker:
            maker.mkdir(self.meta.file.parent, exist_ok=True)
            maker.write_file(self.meta.file, '{}')

            print("Writing Meta Data")

            self.started = datetime.datetime.now()

            print("Success")

            print(f"Creating Tier File ({self.file}) using template ({template})")
            maker.write_file(self.file, self.render_template(template))
            print("Success")

            print(f"Creating Tier Folder ({self.folder})")

            self.folder.mkdir(exist_ok=True)

            print("Success")

        print("All Done")

    description = MetaAttr()
    conclusion = MetaAttr()
    started = MetaAttr(lambda val: datetime.datetime.strptime(val, config.DATE_FORMAT), # type: ignore
                       lambda val: val.strftime(config.DATE_FORMAT))  # type: ignore

    @cached_prop
    def identifiers(self) -> Tuple[str, ...]:
        """
        Read only copy of identifiers that make up this `Tier` object.
        """
        return self._identifiers

    @cached_prop
    def name(self) -> str:
        """
        Full name of `Tier` object. Made by concatenating each parent's `self.name_part_template` filled with each parent's
        `self.id`.

        Examples
        --------

            >>> wp = WorkPackage('2')
            >>> exp = Experiment('2', '3')
            >>> smpl = Sample('2', '3', 'c')
            >>> wp.name_part_template.format(wp.id)
            WP2
            >>> exp.name_part_template.format(exp.id)
            .3
            >>> smpl.name_part_template.format(smpl.id)
            c
            >>> smpl.name  # all 3 joined together
            WP2.3c
        """

        return ''.join(cls.name_part_template.format(id) for cls, id in zip(self.hierarchy[1:], self.identifiers))

    @cached_prop
    def id(self) -> str:
        """
        Shortcut for getting final identifier.

        Examples
        --------

            >>> from my_project import project
            >>> smpl = project.env('WP2.3c')
            >>> smpl.identifiers
            ['2', '3', 'c']
            >>> smpl.id
            'c'
        """
        return self._identifiers[-1]

    @cached_prop
    def folder(self) -> Path:
        """
        Path to folder where the contents of this `Tier` lives.

        Defaults to `self.parent.folder / self.name`.
        """
        if self.parent:
            return self.parent.folder / self.name
        else: # this is bad
            return Path(self.name)

    @cached_prop
    def meta_file(self) -> Path:
        """
        Path to where meta file for this `Tier` object should be.

        Returns
        -------
        meta_file : Path
            Defaults to `self.parent.folder / self._meta_folder_name / (self.name + '.json')`
        """
        assert self.parent
        return self.parent.folder / self._meta_folder_name / (self.name + '.json')

    @cached_prop
    def highlights_file(self) -> Union[Path, None]:
        """
        Path to where highlights file for this `Tier` object should be.

        Returns
        -------
        highlights_file : Path
            Defaults to `self.parent.folder / self._meta_folder_name / (self.name + '.hlts')`
        """
        assert self.parent
        return self.parent.folder / self._meta_folder_name / (self.name + '.hlts')

    @cached_prop
    def cache_file(self) -> Union[Path, None]:
        """
        Path to where cache file for this `Tier` object will be.

        Returns
        -------
        cache_file : Path
            Defaults to `self.parent.folder / self._meta_folder_name / (self.name + '.cache')`
        """
        assert self.parent
        return self.parent.folder / self._meta_folder_name / (self.name + '.cache')

    @cached_prop
    def file(self) -> Union[Path, None]:
        """
        Path to where `.ipynb` file for this `Tier` instance will be.

        Returns
        -------
        file : Path
            Defaults to self.parent.folder / (self.name + '.ipynb').
        """
        assert self.parent
        return self.parent.folder / (self.name + '.ipynb')


    @cached_prop
    def parent(self) -> Union[TierBase, None]:
        """
        Parent of this `Tier` _instance, `None` if has no parent :'(
        """
        if self.parent_cls:
            return self.parent_cls(*self._identifiers[:-1])
        return None

    @cached_prop
    def href(self) -> Union[str, None]:
        """
        href usable in notebook HTML giving link to `self.file`.

        Assumes that `os.getcwd()` reflects the directory of the currently opened `.ipynb` (usually true, unless you're
        changing working dir).

        Does do escaping on the HTML, but is maybe pointless!

        Returns
        -------
        href : str
            href usable in notebook HTML.
        """
        if self.file:
            return html.escape(Path(os.path.relpath(self.file, os.getcwd())).as_posix())
        else:
            return None

    def exists(self) -> bool:
        """
        returns True if this `Tier` object has already been setup (e.g. by `self.setup_files`)
        """
        return self.meta_file.exists()

    def get_child(self, id: str) -> TierBase:
        """
        Get a child according to the given `id`.

        Parameters
        ----------
        id : str
            id to add `self.identifiers` to form new `Tier` object of tier below.

        Returns
        -------
        child : Type[TierBase]
            child `Tier` object.
        """
        assert self.child_cls
        return self.child_cls(*self._identifiers, id)

    def serialize(self):
        data = dict(self.meta)
        data['identifiers'] = self.identifiers
        data['name'] = self.name
        data['file'] = str(self.file)
        
        parents = []
        parent = self.parent
        
        while parent:
            parents.append(parent)
            parent = parent.parent
        
        data['parents'] = [parent.name for parent in parents][::-1]
        data['children'] = [child.name for child in self]
        
        return data

    def children_df(self, * , include: Optional[List[str]] = None, exclude: Optional[List[str]]) -> Union[pd.DataFrame, None]:
        """
        Build an `UnescapedDataFrame` containing rows from each child of this `Tier`. Columns are inferred from contents
        of meta files.

        Parameters
        ----------
        include : Sequence[str]
            names of columns to include in children DataFrame
        exclude : Sequence[str]
            names of columns to drop from children DataFrame

        Notes
        -----
        Parameters include and exclude are mutually exclusive.

        Returns
        -------
        df : UnescapedDataFrame, None
            DataFrame containing `Tier`'s children. If no children then returns `None`.
        """
        if self.child_cls is None:
            return None

        if include and exclude:
            raise ValueError("Only one of include or exclude can be provided")

        children = list(self)

        if not children:
            return None

        data: Dict[str, List[Any]] = defaultdict(list)
        attributes_set: set[str] = set()

        for child in children:
            attributes_set.update(child.meta.keys())
            data['Name'].append(child.name)

        attributes = list(attributes_set)

        for child in children:
            for attr in attributes:
                try:
                    val = getattr(child, attr)
                except AttributeError:
                    val = child.meta.get(attr)
                data[attr].append(val)

        for tier in children:
            data['Obj'].append(tier)

        df = pd.DataFrame(data=data)
        df = df.set_index('Name')
        df = df.sort_values('started', axis=0)

        priority_columns = ['started', 'description']
        if 'conclusion' in df.columns:
            priority_columns.append('conclusion')

        df = df[priority_columns + [col for col in df.columns if col not in priority_columns]]

        if include:
            df = df.loc[:, include]

        if exclude:
            df = df.drop(exclude, axis='columns')

        return cast(pd.DataFrame, df)

    @classmethod
    def get_templates(cls) -> List[Path]:
        """
        Get all the templates for this `Tier`.
        """
        assert env.project

        return [Path(cls.pretty_type) / entry.name for entry in
                os.scandir(env.project.template_folder / cls.pretty_type)
                if entry.is_file()]

    def render_template(self, template) -> str:
        """
        Render template file passing `self` as `self.short_type`.

        Parameters
        ----------
        template : Path
            path to template file.

        Returns
        -------
        rendered_text : str
            template rendered with `self`.
        """
        assert env.project

        template = env.project.template_env.get_template(template)
        return template.render(**{self.short_type: self, 'tier': self})

    def open_folder(self):
        """
        Open `self.folder` in explorer

        Notes
        -----
        Only works on Windows machines.

        Window is opened via the Jupyter server, not the browser, so if you are not accessing jupyter on localhost then
        the window won't open for you!
        """
        open_file(self.folder)

    def get_highlights(self) -> Union[Dict[str, List[Dict[str, Dict[str, Any]]]], None]:
        """
        Get dictionary of highlights for this `Tier` _instance.

        This dictionary is in a form that can be rendered in the notebook using `IPython.display.publish_display_data`
        see Examples.

        This is implemented for you with `self.display_highlights()`.

        Returns
        -------
        highlights : dict
            Get dictionary of highlights for this `Tier` _instance. If the highlights file doesn't exist, just returns an
            empty dict.

        Examples
        --------

            >>> wp = project['WP1']
            >>> for title, outputs in wp.get_highlights():
            ...     print("Displaying Highlight:", title)
            ...     for output in outputs:
            ...         IPython.display.publish_display_data(**output)
        """
        if self.highlights_file and self.highlights_file.exists():
            highlights = json.loads(self.highlights_file.read_text())
            return highlights
        else:
            return {}

    def add_highlight(self, name: str, data: List[Dict[str, Dict[str, Any]]], overwrite: bool = True):
        """
        Add a highlight to `self.highlights_file`.

        This is usually done behind the scenes using the `%%hlt My Title` magic.

        Parameters
        ----------
        name : str
            Name of highlight (also taken as the title).
        data : list
            list of data and metadata that can be passed to `IPython.display.publish_display_data` to render.
        overwrite : bool
            If `False` will raise an exception if a highlight of the same `name` exists. Default is `True`
        """
        highlights = self.get_highlights()
        
        if self.highlights_file and highlights:
            highlights = highlights.copy()
        else:
            return 
        
        if not overwrite and name in highlights:
            raise KeyError("Attempting to overwrite existing meta value")
        highlights[name] = data
        self.highlights_file.write_text(json.dumps(highlights))

    def remove_highlight(self, name: str):
        """
        Remove highlight from highlight file. Performed by calling `get_highlights()`, then deleting the key `name` from
        the dictionary, then re-writing the highlights... if you're interested!
        """
        highlights = self.get_highlights()

        if not highlights or not self.highlights_file:
            return
        
        del highlights[name]
        self.highlights_file.write_text(json.dumps(highlights))

    def get_cached(self) -> Union[Dict[str, List[Dict[str, Dict[str, Any]]]], None]:
        """
        Retrieve cached output from `self.cache_file`.

        Keys are a hash of text from cell that created this output.

        Returns
        -------
        cached : dict
            dictionary with all the cached outputs. In the same form as `self.get_highlights()`. Returns an empty dict
            if no `cache_file` exists.
        """
        if self.cache_file and self.cache_file.exists():
            cache = json.loads(self.cache_file.read_text())
            return cache
        else:
            return {}

    def cache_result(self, name: str, data: List[Dict[str, Dict[str, Any]]], overwrite: bool = True):
        """
        Cache a result in `self.cache_file`.

        This is usually done behind the scenes using the `%%cache` magic.

        Parameters
        ----------
        name : str
            name used as key in JSON for this cached result. When using `%%cache` this is a hash of the cell text
        data : dict
            list of data and metadata that can be passed to `IPython.display.publish_display_data` to render.
        overwrite : bool
            If `False` will raise an exception if a cached result of the same `name` exists. Default is `True`
        """
        if not self.cache_file:
            return
        
        cache = self.get_cached()
        
        if cache:
            cache = cache.copy()
        else:
            return
        
        if not overwrite and name in cache:
            raise KeyError("Attempting to overwrite existing meta value")
        
        cache[name] = data
        self.cache_file.write_text(json.dumps(cache))

    def remove_cached(self, name):
        """
        Remove cached output according to the `name` provided.
        """
        cached = self.get_cached()
        del cached[name]
        self.cache_file.write_text(json.dumps(cached))

    def __truediv__(self, other) -> Path:
        return self.folder / other

    def __getitem__(self, item) -> TierBase:
        """
        Equivalent to `self.get_child(item)`.
        """
        return self.get_child(item)

    def __iter__(self) -> Iterator[Any]:
        """
        Iterates over all children (in no particular order). Children are found by looking through the child meta
        folder.

        Empty iterator if no children.
        """
        assert self.child_cls

        child_cls = self.child_cls
        child_meta_dir = self / child_cls._meta_folder_name
        if child_meta_dir.exists():
            return (child_cls(*identifiers) for identifiers in self._iter_meta_dir(child_meta_dir))
        return iter(())

    def __repr__(self):
        return f'<{self.__class__.__name__} "{self.name}">'

    def _repr_html_(self) -> str:
        block = f'h{len(self.identifiers) + 1} style="display: inline;"'
        return f'<a href="{self.href}"' \
               f' target="_blank"><{block}>{html.escape(self.name)}</{block}</a>'

    def __getattr__(self, item):
        if env.project and item in env.project.rank_map:
            rank = env.project.rank_map[item]
            return env.project.hierarchy[rank](*self.identifiers[:rank])
        raise AttributeError(item)

    def remove_files(self):
        """
        Deletes files associated with a `Tier`
        """
        if self.file:
            self.file.unlink()

        if self.meta_file:
            self.meta_file.unlink()
