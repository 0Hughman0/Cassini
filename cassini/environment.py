from __future__ import annotations

from pathlib import Path
from warnings import warn
import re

from typing import Union, Tuple, List

import jinja2

from .accessors import soft_prop
from .utils import FileMaker
from .config import config


class PathLibEnv(jinja2.Environment):
    """
    Subclass of `jinja2.Environment` to enable using `pathlib.Path` for template names.
    """

    def get_template(self, name: Union[Path, str], parent=None, globals=None):
        return super().get_template(name.as_posix() if isinstance(name, Path) else name, parent=None, globals=None)


class Project:
    """
    Represents your project. Understands your naming convention, and your project hierarchy.

    Parameters
    ----------
    hierarchy : List[Type[BaseTier]]
        Sequence of `TierBase` subclasses representing the hierarchy for this project. i.e. earlier entries are stored
        in higher level directories.
    project_folder : Union[str, Path]
        path to home directory. Note this also accepts a path to a file, but will take `project_folder.parent` in that
        case. This enables `__file__` to be used if you want `project_folder` to be based in the same dir.

    Notes
    -----
    This class is a singleton i.e. only 1 instance per interpreter can be created.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance:
            raise RuntimeError("Attempted to create new Project instance, only 1 instance permitted per interpreter")
        instance = object.__new__(cls)
        cls._instance = instance
        env.project = instance
        return instance

    def __init__(self, hierarchy: List['BaseTier'], project_folder: Union[str, Path]):
        self.rank_map = {}
        self.hierarchy = hierarchy

        project_folder = Path(project_folder)
        self.project_folder = project_folder if project_folder.is_dir() else project_folder.parent

        self.template_env = PathLibEnv(autoescape=jinja2.select_autoescape(['html', 'xml']),
                                       loader=jinja2.FileSystemLoader(self.template_folder))

        for rank, tier_cls in enumerate(hierarchy):
            tier_cls.rank = rank
            self.rank_map[tier_cls.short_type] = rank

    @property
    def home(self):
        """
        Get the home `Tier`.
        """
        return self.hierarchy[0]()

    def env(self, name: str) -> 'BaseTier':
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
            warn((f"Overwriting the global Tier {env.o} for this interpreter. This may cause unexpected behaviour. "
                  f"If you wish to create Tier objects that aren't the current Tier I recommend initialising them "
                  f"directly e.g. obj = MyTier('id1', 'id2')"))

        env.update(obj)
        return obj

    def __getitem__(self, name: str) -> 'TierBase':
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
            cls = self.hierarchy[len(identifiers)]
            obj = cls(*identifiers)
        return obj

    @soft_prop
    def template_folder(self):
        """
        Overwritable property providing where templates will be stored for this project.
        """
        return self.project_folder / 'templates'

    def setup_files(self):
        """
        Setup files needed for this project.

        Will put everything you need in `project_folder` to get going.
        """
        home = self.home
        if home.exists():
            return home

        print("Setting up project.")

        with FileMaker() as maker:
            print(f"Creating templates folder")
            maker.mkdir(self.template_folder)
            print("Success")

            for tier_cls in self.hierarchy:
                if tier_cls.default_template is None:
                    continue
                maker.mkdir(self.template_folder / tier_cls.pretty_type)
                print("Copying over default template")
                maker.copy_file(config.BASE_TEMPLATE, self.template_folder / tier_cls.default_template)
                print("Done")

        print(f"Setting up Home Tier")
        home.setup_files()
        print("Success")

    def parse_name(self, name: str) -> Union[Tuple[str], Tuple]:
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
            WP(\d+)
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
            '\.(\d+)'
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
                name = name[match.end(0):]
            else:
                break
        if name:  # if there's any residual text then it's not a valid name!
            return ()
        else:
            return tuple(ids)

    def __repr__(self):
        return f"<Project at: '{self.project_folder}' hierarchy: '{self.hierarchy}' ({env})>"


class _Env:
    """
    Essentially a global object that describes the state of the project for this interpreter.

    As each notebook has its own interpreter, each notebook also has its own env that basically stores what the current
    project is and what tier this `ipynb` file corresponds to.

    Attributes
    ----------
    project : Project
        reference to the current project object. Returns `None` if one not set yet.

    Warnings
    --------
    This object is a singleton, so only one instance can exist at a time.

    This object shouldn't be created directly, instead you should call `project.env('...')` to set its value.
    """

    instance = None

    def __new__(cls, *args, **kwargs):
        if cls.instance:
            raise RuntimeError("Attempted to create new _Env instance, only 1 _instance permitted per interpreter")
        instance = object.__new__(cls)
        cls.instance = instance
        return instance

    def __init__(self):
        self.project = None
        self._o = None

    @property
    def o(self) -> 'TierBase':
        """
        Reference to current Tier object.
        """
        return self._o

    def update(self, obj: 'TierBase'):
        self._o = obj


env = _Env()
