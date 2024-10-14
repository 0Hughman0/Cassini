from __future__ import annotations

import datetime
import html
import json
import os
from pathlib import Path
from abc import ABC, abstractmethod
import re

from typing import (
    Any,
    List,
    Sequence,
    Type,
    Tuple,
    Iterator,
    Union,
    Dict,
    ClassVar,
    Optional,
    Callable,
    cast,
    Protocol,
)
from warnings import warn
from jupyterlab.labapp import LabApp  # type: ignore[import-untyped]
from typing_extensions import Self

import jinja2
from pydantic import JsonValue, AwareDatetime

from .meta import Meta, MetaManager, MetaAttr, use_meta
from .accessors import cached_prop, cached_class_prop, soft_prop
from .utils import (
    FileMaker,
    open_file,
    CassiniLabApp,
    PathLibEnv,
)
from .environment import env
from .config import config
from .jlgui import JLGui


class TierGuiProtocol(Protocol):
    """
    Protocol for providing a gui for tiers.

    Must provide a header method and take the tier to provide a gui for as the first argument.
    """

    def __init__(self, tier: TierABC):
        pass

    def header(self):
        """
        The header is the UI that is goes at the top of a notebook.
        """
        pass


MetaDict = Dict[str, JsonValue]


HighlightType = List[Dict[str, Dict[str, Any]]]
HighlightsType = Dict[str, HighlightType]


class TierABC(ABC):
    """
    Abstract Base class for creating Tiers objects. Tiers should correspond to a folder on your disk.

    Instances of this class or subclasses should not be created directly. Instead a Project instance
    should create them.

    Parameters
    ----------
    *identifiers : str
        sequence of strings that identify this tier. With the final identifier being unique.

    Attributes
    ----------
    id_regex: str
        Class attribute, regex that defines a group that matches the id of a `Tier` object from a name... except the
        name isn't the full name, but with parent names stripped, see examples basically!
    hierarchy : list
        Class attribute, hierarchy of `Tier`s.
    id_regex : str
        (class attribute) regex used to restrict form of `Tier` object ids. Should contain 1 group that captures the id.
    gui_cls : Any
        (class attribute) The class called upon initialisation to use as gui for this object. Constructor should take `self`
         as first argument.
    """

    _cache: ClassVar[Dict[Tuple[str, ...], TierABC]] = env.create_cache()

    def __init_subclass__(cls, *args: Any, **kwargs: Any) -> None:
        super().__init_subclass__(*args, **kwargs)
        cls._cache = env.create_cache()  # ensures each TierBase class has its own cache

    id_regex: ClassVar[str] = r"(\d+)"

    gui_cls: Type[TierGuiProtocol]

    @cached_class_prop
    def _pretty_type(cls) -> str:
        """
        Name used to display this Tier. Defaults to `cls.__name__`.
        """
        return cls.__name__  # type: ignore[attr-defined]

    pretty_type: str = _pretty_type  # to please type checker.

    @cached_class_prop
    def _short_type(cls) -> str:
        """
        Name used to programmatically refer to instances of this `Tier`.

        Default, take pretty type, make lowercase and remove vowels.
        """
        return cls.pretty_type.lower().translate(str.maketrans(dict.fromkeys("aeiou")))

    short_type: str = _short_type

    @cached_class_prop
    def _name_part_template(cls) -> str:
        """
        Python template that's filled in with `self.id` to create segment of the `Tier` object's name.
        """
        return cls.pretty_type + "{}"

    name_part_template = _name_part_template

    @cached_class_prop
    def _name_part_regex(cls) -> str:
        """
        Regex where first group matches `id` part of string. Default is fill in `cls.name_part_template` with
        `cls.id_regex`.
        """
        return cls.name_part_template.format(cls.id_regex)

    name_part_regex = _name_part_regex

    @classmethod
    @abstractmethod
    def iter_siblings(cls, parent: TierABC) -> Iterator[TierABC]:
        """
        Provide an iterator for the siblings of this tier for a given parent i.e.
        iterate over parent's children.
        """
        pass

    def __new__(cls, *args: str, **kwargs: Dict[str, Any]) -> TierABC:
        obj = cls._cache.get(args)
        if obj:
            return obj
        obj = object.__new__(cls)
        cls._cache[args] = obj
        return obj

    _identifiers: Tuple[str, ...]
    gui: TierGuiProtocol

    def __init__(self: Self, *args: str, project: Project):
        self.project = project

        self._identifiers = tuple(filter(None, args))
        self.gui = self.gui_cls(self)

        rank = self.project.rank_map[self.__class__]

        if len(self._identifiers) != rank:
            raise ValueError(
                f"Invalid number of identifiers in {self._identifiers}, expecting {rank}."
            )

        if self.parse_name(self.name) != self.identifiers:
            raise ValueError(
                f"Invalid identifiers - {self._identifiers}, resulting name ('{self.name}') not in a parsable form "
            )

    @cached_prop
    def _parent_cls(self) -> Union[Type[TierABC], None]:
        """
        `Tier` above this `Tier`, `None` if doesn't have one
        """
        return self.project.get_parent_cls(self.__class__)

    parent_cls = _parent_cls

    @cached_prop
    def _child_cls(self) -> Union[Type[TierABC], None]:
        """
        `Tier` below this `Tier`, `None` if doesn't have one
        """
        return self.project.get_child_cls(self.__class__)

    child_cls = _child_cls

    def parse_name(self, name: str) -> Tuple[str, ...]:
        """
        Ask `env.project` to parse name.
        """
        return self.project.parse_name(name)

    @abstractmethod
    def setup_files(
        self, template: Union[Path, None] = None, meta: Optional[MetaDict] = None
    ) -> None:
        """
        Create all the files needed for a valid `Tier` object to exist.

        This includes its `.ipynb` file, its parent folder, its own folder and its `Meta` file.

        Will render `.ipynb` file as Jinja template engine, passing to the template `self` with names given by
        `self.short_type` and `tier`.

        Parameters
        ----------
        template : Path
            path to template file to render to create `.ipynb` file.
        meta : MetaDict
            Initial meta values to create the tier with.
        """
        pass

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
        return "".join(
            cls.name_part_template.format(id)
            for cls, id in zip(self.project.hierarchy[1:], self.identifiers)
        )

    @property
    @abstractmethod
    def folder(self) -> Path:
        """
        The folder this tier corresponds to.
        """
        pass

    def open_folder(self) -> None:
        """
        Open `self.folder` in explorer

        Notes
        -----
        Only works on Windows machines.

        Window is opened via the Jupyter server, not the browser, so if you are not accessing jupyter on localhost then
        the window won't open for you!
        """
        open_file(self.folder)

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
    def parent(self) -> Union[TierABC, None]:
        """
        Parent of this `Tier` _instance, `None` if has no parent :'(
        """
        if self.parent_cls:
            return self.parent_cls(*self._identifiers[:-1], project=self.project)
        return None

    @cached_prop
    @abstractmethod
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
        pass

    @abstractmethod
    def exists(self) -> bool:
        """
        returns True if this `Tier` object has already been setup (e.g. by `self.setup_files`)
        """
        pass

    def get_child(self, id: str) -> TierABC:
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
        return self.child_cls(*self._identifiers, id, project=self.project)

    def __truediv__(self, other: Any) -> Path:
        return cast(Path, self.folder / other)

    def __getitem__(self, item: str) -> TierABC:
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
        if not self.child_cls:
            raise NotImplementedError()

        yield from self.child_cls.iter_siblings(self)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} "{self.name}">'

    def _repr_html_(self) -> str:
        block = f'h{len(self.identifiers) + 1} style="display: inline;"'
        return (
            f'<a href="{self.href}"'
            f' target="_blank"><{block}>{html.escape(self.name)}</{block}</a>'
        )

    @abstractmethod
    def remove_files(self) -> None:
        """
        Deletes files associated with a `Tier`
        """
        pass


class FolderTierBase(TierABC):
    """
    Base class for a tier which has a folder, but not notebook/ meta.
    """

    gui_cls = JLGui

    @classmethod
    def iter_siblings(cls, parent: TierABC) -> Iterator[TierABC]:
        # TODO: shouldn't project also handle this?
        if not parent.folder.exists():
            return

        for folder in os.scandir(parent.folder):
            if not folder.is_dir():
                continue
            yield cls(*parent.parse_name(folder.name), project=parent.project)

    @cached_prop
    def folder(self) -> Path:
        """
        Path to folder where the contents of this `Tier` lives.

        Defaults to `self.parent.folder / self.name`.
        """
        if self.parent:
            return self.parent.folder / self.name
        else:  # this is bad
            return Path(self.name)

    def setup_files(self, template: Union[Path, None] = None, meta=None) -> None:
        print(f"Creating Folder for {self} at {self.folder}")

        with FileMaker() as maker:
            maker.mkdir(self.folder.parent, exist_ok=True)
            maker.mkdir(self.folder)

        print("Success")

    def remove_files(self) -> None:
        pass

    def exists(self) -> bool:
        """
        returns True if this `Tier` object has already been setup (e.g. by `self.setup_files`)
        """
        return self.folder.exists()

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
        return html.escape(Path(os.path.relpath(self.folder, os.getcwd())).as_posix())


class NotebookTierBase(FolderTierBase):
    """
    Base class for tiers which have a notebook and meta associated with them.
    """

    meta: Meta

    @cached_class_prop
    def meta_model(cls):
        return Meta.build_meta_model(cls)

    @cached_class_prop
    def _default_template(cls) -> Path:
        """
        Template used to render a tier file by default.
        """
        return Path(cls.pretty_type) / f"{cls.pretty_type}.tmplt.ipynb"

    default_template = _default_template

    @cached_class_prop
    def _meta_folder_name(cls) -> str:
        """
        Form of meta folder name. (Just fills in `config.META_DIR_TEMPLATE` with `cls.short_type`).
        """
        return config.META_DIR_TEMPLATE.format(cls.short_type)

    meta_folder_name = _meta_folder_name

    @classmethod
    def iter_siblings(cls, parent):
        meta_folder = parent.folder / config.META_DIR_TEMPLATE.format(cls.short_type)

        if not meta_folder.exists():
            return

        for meta_file in os.scandir(meta_folder):
            if not meta_file.is_file() or not meta_file.name.endswith(".json"):
                continue
            yield cls(
                *parent.parse_name(meta_file.name[:-5]), project=parent.project
            )  # I don't like this.

    def __init__(self, *identifiers: str, project: Project):
        super().__init__(*identifiers, project=project)
        self.meta: Meta = Meta.create_meta(self.meta_file, owner=self)

    def setup_files(
        self, template: Union[Path, None] = None, meta: Optional[MetaDict] = None
    ) -> None:
        """
        Create all the files needed for a valid `Tier` object to exist.

        This includes its `.ipynb` file, its parent folder, its own folder and its `Meta` file.

        Will render `.ipynb` file as Jinja template engine, passing to the template `self` with names given by
        `self.short_type` and `tier`.

        Parameters
        ----------
        template : Path
            path to template file to render to create `.ipynb` file.
        meta : MetaDict
            Initial meta values to create the tier with.
        """
        if template is None:
            template = self.default_template

        if meta is None:
            meta = {}

        if self.exists():
            raise FileExistsError(f"Meta for {self.name} exists already")

        if self.file and self.file.exists():
            raise FileExistsError(f"Notebook for {self.name} exists already")

        print(f"Creating files for {self.name}")

        print(f"Meta ({self.meta_file})")

        with FileMaker() as maker:
            maker.mkdir(self.meta.file.parent, exist_ok=True)
            maker.write_file(self.meta.file, json.dumps(meta))

            print("Writing Meta Data")

            self.started = datetime.datetime.now(datetime.timezone.utc)

            print("Success")

            print(f"Creating Tier File ({self.file}) using template ({template})")
            maker.write_file(self.file, self.render_template(template))
            print("Success")

            print(f"Creating Tier Folder ({self.folder})")

            self.folder.mkdir(exist_ok=True)

            print("Success")

        print("All Done")

    def exists(self) -> bool:
        """
        returns True if this `Tier` object has already been setup (e.g. by `self.setup_files`)
        """
        return bool(self.file and self.folder.exists() and self.meta_file.exists())

    description = MetaAttr(str, str, cas_field="core")
    conclusion = MetaAttr(str, str, cas_field="core")
    started = MetaAttr(AwareDatetime, datetime.datetime, cas_field="core")

    @cached_prop
    def meta_file(self) -> Path:
        """
        Path to where meta file for this `Tier` object should be.

        Returns
        -------
        meta_file : Path
            Defaults to `self.parent.folder / self.meta_folder_name / (self.name + '.json')`
        """
        assert self.parent
        return self.parent.folder / self.meta_folder_name / (self.name + ".json")

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
        return self.parent.folder / self._meta_folder_name / (self.name + ".hlts")

    @cached_prop
    def file(self) -> Path:
        """
        Path to where `.ipynb` file for this `Tier` instance will be.

        Returns
        -------
        file : Path
            Defaults to self.parent.folder / (self.name + '.ipynb').
        """
        assert self.parent
        return self.parent.folder / (self.name + ".ipynb")

    @classmethod
    def get_templates(cls, project: Project) -> List[Path]:
        """
        Get all the templates for this `Tier`.
        """
        return [
            Path(cls.pretty_type) / entry.name
            for entry in os.scandir(project.template_folder / cls.pretty_type)
            if entry.is_file()
        ]

    def render_template(self, template_path: Path) -> str:
        """
        Render template file passing `self` as `self.short_type` and as `tier`.

        Parameters
        ----------
        template : Path
            path to template file. Must be relative to `project.template_folder`

        Returns
        -------
        rendered_text : str
            template rendered with `self`.
        """
        template = self.project.template_env.get_template(template_path)
        return template.render(**{self.short_type: self, "tier": self})

    def get_highlights(self) -> Union[HighlightsType, None]:
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
            highlights = cast(
                HighlightsType, json.loads(self.highlights_file.read_text())
            )
            return highlights
        else:
            return {}

    def add_highlight(
        self, name: str, data: HighlightType, overwrite: bool = True
    ) -> None:
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

        if self.highlights_file and highlights is not None:
            highlights = highlights.copy()
        else:
            return

        if not overwrite and name in highlights:
            raise KeyError("Attempting to overwrite existing meta value")

        highlights[name] = data
        self.highlights_file.write_text(json.dumps(highlights), encoding="utf-8")

    def remove_highlight(self, name: str) -> None:
        """
        Remove highlight from highlight file. Performed by calling `get_highlights()`, then deleting the key `name` from
        the dictionary, then re-writing the highlights... if you're interested!
        """
        highlights = self.get_highlights()

        if not highlights or not self.highlights_file:
            return

        del highlights[name]
        self.highlights_file.write_text(json.dumps(highlights), encoding="utf-8")

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
        return html.escape(Path(os.path.relpath(self.file, os.getcwd())).as_posix())

    def remove_files(self) -> None:
        """
        Deletes files associated with a `Tier`
        """
        if self.file:
            self.file.unlink()

        if self.meta_file:
            self.meta_file.unlink()


class HomeTierBase(FolderTierBase):
    """
    Home `Tier`.

    This, or a subclass of this should generally be the first entry in your hierarchy, essentially represents the top
    level folder in your hierarchy.

    Creates the `Home.ipynb` notebook that allows easy navigation of your project.
    """

    @cached_prop
    def name(self) -> str:
        return self.pretty_type

    @classmethod
    def iter_siblings(cls, parent: TierABC) -> Iterator[TierABC]:
        raise NotImplementedError("Home tier cannot be iterated over.")

    @cached_prop
    def folder(self) -> Path:
        assert self.child_cls
        return self.project.project_folder / (self.child_cls.pretty_type + "s")

    @cached_prop
    def file(self) -> Path:
        return self.project.project_folder / f"{self.name}.ipynb"

    def exists(self) -> bool:
        return bool(self.folder and self.file.exists())

    def setup_files(self, template: Union[Path, None] = None, meta=None) -> None:
        assert self.child_cls

        with FileMaker() as maker:
            print(f"Creating {self.child_cls.pretty_type} folder")
            maker.mkdir(self.folder, exist_ok=True)
            print("Success")

        with FileMaker() as maker:
            print(f"Creating Tier File ({self.file})")
            # TODO: look at this, is this ok?
            maker.write_file(
                self.file, (config.DEFAULT_TEMPLATE_DIR / "Home.ipynb").read_text()
            )
            print("Success")

    def remove_files(self) -> None:
        self.file.unlink()


class Project:
    """
    Represents your project. Understands your naming convention, and your project hierarchy.

    Parameters
    ----------
    hierarchy : Sequence[Type[BaseTier]]
        Sequence of `TierBase` subclasses representing the hierarchy for this project. i.e. earlier entries are stored
        in higher level directories.
    project_folder : Union[str, Path]
        path to home directory. Note this also accepts a path to a file, but will take `project_folder.parent` in that
        case. This enables `__file__` to be used if you want `project_folder` to be based in the same dir.


    Notes
    -----
    This class is a singleton i.e. only 1 instance per interpreter can be created.

    Project provides the following hooks, to allow customization of setting up and launching projects. These are
    lists of functions, which are called in order at the specified time:

        `__before_setup_files__` and `__after_setup_files__` - These are called when `project.setup_files()` is
        called. These can be used, for example, to create additional directories or files. These callables
        should take the project instance as an argument.

        `__before_launch__` and `__after_launch__` - These are called during and after `project.launch()` is
        called. These take the project and LabApp instance as an argument.
    """

    def __new__(cls, *args: Any, **kwargs: Any) -> Project:
        if env.project:
            raise RuntimeError(
                "Attempted to create new Project instance, only 1 instance permitted per interpreter"
            )
        instance = object.__new__(cls)
        env.project = instance
        return instance

    def __init__(
        self, hierarchy: Sequence[Type[TierABC]], project_folder: Union[str, Path]
    ):
        self._rank_map: Dict[Type[TierABC], int] = {}
        self._hierarchy: Sequence[Type[TierABC]] = []

        self.__before_setup_files__: List[Callable[[Project], None]] = []
        self.__after_setup_files__: List[Callable[[Project], None]] = []

        self.__before_launch__: List[
            Callable[[Project, Union[LabApp, None]], None]
        ] = []
        self.__after_launch__: List[Callable[[Project, Union[LabApp, None]], None]] = []

        self.hierarchy: Sequence[Type[TierABC]] = hierarchy

        project_folder_path = Path(project_folder).resolve()
        self.project_folder: Path = (
            project_folder_path
            if project_folder_path.is_dir()
            else project_folder_path.parent
        )

        self.template_env: PathLibEnv = PathLibEnv(
            autoescape=jinja2.select_autoescape(["html", "xml"]),
            loader=jinja2.FileSystemLoader(self.template_folder),
        )

    @property
    def hierarchy(self) -> Sequence[Type[TierABC]]:
        return self._hierarchy

    @hierarchy.setter
    def hierarchy(self, hierarchy: Sequence[Type[TierABC]]):
        self._hierarchy = hierarchy

        for rank, tier_cls in enumerate(hierarchy):
            self._rank_map[tier_cls] = rank

    @property
    def rank_map(self):
        return self._rank_map

    @property
    def home(self) -> TierABC:
        """
        Get the home `Tier`.
        """
        return self.hierarchy[0](project=self)

    def env(self, name: str) -> TierABC:
        """
        Initialise the global environment to a particular `Tier` that is retrieved by parsing `name`.

        This will set the value of `env.o`.

        Warnings
        --------
        This should only really be called once (or only with 1 name). Otherwise this could create some unexpected
        behaviour.
        """
        obj = self.__getitem__(name)

        if env.o and name != env.o.name:
            warn(
                (
                    f"Overwriting the global Tier {env.o} for this interpreter. This may cause unexpected behaviour. "
                    f"If you wish to create Tier objects that aren't the current Tier I recommend initialising them "
                    f"directly e.g. obj = MyTier('id1', 'id2')"
                )
            )

        env.update(obj)
        return obj

    def get_tier(self, identifiers: Tuple[str, ...]) -> TierABC:
        """
        Get a tier for a given set of identifiers.
        """
        cls = self.hierarchy[len(identifiers)]
        return cls(*identifiers, project=self)

    def get_child_cls(self, tier_cls: Type[TierABC]) -> Union[None, Type[TierABC]]:
        """
        Get the child class of a given tier class. Returns None if there is no child class
        """
        rank = self.rank_map[tier_cls]
        if rank + 1 > (len(self.hierarchy) - 1):
            return None
        else:
            cls = self.hierarchy[rank + 1]  # I don't understand why annotation needed?
            return cls

    def get_parent_cls(self, tier_cls: Type[TierABC]) -> Union[None, Type[TierABC]]:
        """
        Get the parent class of a given tier class. Returns None if there is no parent class
        """
        rank = self.rank_map[tier_cls]
        if rank - 1 < 0:
            return None
        else:
            cls = self.hierarchy[rank - 1]
            return cls

    def __getitem__(self, name: str) -> TierABC:
        """
        Retrieve a tier object from the project by name.

        Parameters
        ----------
        name : str
            Parsable name to get the tier object by. To get your `Home` just provide `Home.name`.

        Returns
        -------
        tier : TierBase
            Tier retrieved from project.
        """
        if name == self.home.name:
            obj = self.home
        else:
            identifiers = self.parse_name(name)
            if not identifiers:
                raise ValueError(f"Name {name} not recognised as identifying any Tier")
            obj = self.get_tier(identifiers)
        return obj

    @soft_prop
    def template_folder(self) -> Path:
        """
        Overwritable property providing where templates will be stored for this project.
        """
        return self.project_folder / "templates"

    def setup_files(self) -> TierABC:
        """
        Setup files needed for this project.

        Will put everything you need in `project_folder` to get going.
        """
        for func in self.__before_setup_files__:
            func(self)

        home = self.home

        if home.exists():
            return home

        print("Setting up project.")

        with FileMaker() as maker:
            print("Creating templates folder")
            maker.mkdir(self.template_folder)
            print("Success")

            for tier_cls in self.hierarchy:
                if not issubclass(tier_cls, NotebookTierBase):
                    continue

                maker.mkdir(self.template_folder / tier_cls.pretty_type)
                print("Copying over default template")
                maker.copy_file(
                    config.BASE_TEMPLATE,
                    self.template_folder / tier_cls.default_template,
                )
                print("Done")

        print("Setting up Home Tier")
        home.setup_files()
        print("Success")

        for func in self.__after_setup_files__:
            func(self)

        return home

    def launch(
        self, app: Union[LabApp, None] = None, patch_pythonpath: bool = True
    ) -> LabApp:
        """
        Jump off point for a cassini project.

        Sets up required files for your project, monkeypatches `PYTHONPATH` to make your project available throughout
        and launches a jupyterlab server.

        This explicitly associates an instance of the Jupyter server with a particular project.

        Parameters
        ----------
        app : LabApp
            A ready made Jupyter Lab app (By defuault will just create a new one).
        patch_pythonpath : bool
            Add `self.project_folder` to the `PYTHONPATH`? (defaults to `True`)
        """
        for func in self.__before_launch__:
            func(self, app)

        self.setup_files()

        if patch_pythonpath:
            py_path = os.environ.get("PYTHONPATH", "")
            project_path = str(self.project_folder.resolve())
            os.environ["PYTHONPATH"] = (
                py_path + os.pathsep + project_path if py_path else project_path
            )

        if app is None:
            app = CassiniLabApp()

        app.launch_instance()

        for func in self.__after_launch__:
            func(self, app)

        return app

    def parse_name(self, name: str) -> Tuple[str, ...]:
        """
        Parses a string that corresponds to a `Tier` and returns a list of its identifiers.

        returns an empty tuple if not a valid name.

        Parameters
        ----------
        name : str
            name to parse

        Returns
        -------
        identifiers : tuple
            identifiers extracted from name, empty tuple if `None` found

        Notes
        -----
        This works in a slightly strange - but robust way!

        e.g.

            >>> name = 'WP2.3c'

        it will loop through each entry in `cls.hierarchy` (skipping home!), and then perform a search on `name` with
        that regex:

            >>> WorkPackage.name_part_regex
            WP(\\d+)
            >>> match = re.search(WorkPackage.name_part_regex, name)

        If there's no match, it will return `()`, if there is, it stores the `id` part:

            >>> wp_id = match.group(1)  # in python group 0 is the whole match
            >>> wp_id
            2

        Then it removes the whole match from the name:

            >>> name = name[match.end(0):]
            >>> name
            .3c

        Then it moves on to the next tier

            >>> Experiment.name_part_regex
            '\\.(\\d+)'
            >>> match = re.search(WorkPackage.name_part_regex, name)

        If there's a match it extracts the id, and substracts the whole string from name and moves on, continuing this
        loop until it's gone through the whole hierarchy.

        The whole name has to be a valid id, or it will return `()` e.g.

            >>> TierBase.parse_name('WP2.3')
            ('2', '3')
            >>> TierBase.parse_name('WP2.u3')
            ()
        """
        parts = self.hierarchy[1:]
        ids: List[str] = []
        for tier_cls in parts:
            pattern = tier_cls.name_part_regex
            match = re.search(pattern, name)
            if match and match.start(0) == 0:
                ids.append(match.group(1))
                name = name[match.end(0) :]
            else:
                break
        if name:  # if there's any residual text then it's not a valid name!
            return tuple()
        else:
            return tuple(ids)

    def __repr__(self) -> str:
        return f"<Project at: '{self.project_folder}' hierarchy: '{self.hierarchy}' ({env})>"
