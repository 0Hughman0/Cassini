from pathlib import Path
import os

from typing import Iterator, List, Any, cast

from ..core import TierABC, FolderTierBase, NotebookTierBase, HomeTierBase
from ..accessors import cached_prop
from ..utils import FileMaker


def ignore_dir(name: str) -> bool:
    if name.startswith("."):
        return True
    if name.startswith("_"):
        return True
    return False


class Home(HomeTierBase):
    """
    Home `Tier`.

    This, or a subclass of this should generally be the first entry in your hierarchy, essentially represents the top
    level folder in your hierarchy.

    Creates the `Home.ipynb` notebook that allows easy navigation of your project.
    """

    pass


class WorkPackage(NotebookTierBase):
    """
    WorkPackage Tier.

    Intended to contain all the work towards a particular goal. i.e. prove that we can do this.

    Next level down are `Experiment`s.
    """

    name_part_template = "WP{}"
    short_type = "wp"

    @property
    def exps(self) -> List[TierABC]:
        """
        Gets a list of all this `WorkPackage`s experiments.
        """
        return list(self)


class Experiment(NotebookTierBase):
    """
    Experiment `Tier`.

    Just below `WorkPackage`, experiments are intended to be collections of samples and datasets that work towards the
    goal of the parent `WorkPackage`.

    Each `Experiment` has a number of samples.
    """

    name_part_template = ".{}"
    short_type = "exp"

    @property
    def techniques(self) -> List[str]:
        """
        Convenience property for looking up all the techniques that have been performed on samples in this experiment.

        Notes
        -----
        This just checks for the existence of DataSet folders, and not if they have anything in them!
        """
        techs = []
        for entry in os.scandir(self.folder):
            if entry.is_dir() and not ignore_dir(entry.name):
                techs.append(entry.name)
        return techs

    def setup_technique(self, name: str) -> None:
        """
        Convenience method for adding a new technique to this experiment.

        Essentially just creates a new folder for it in the appropriate location.

        This folder can then be filled with `DataSet`s
        """
        print("Making Data Folder")
        folder = self.folder / name

        if folder.exists():
            raise FileExistsError(f"{folder} exists already")

        with FileMaker() as maker:
            maker.mkdir(folder)

        print("Done")

    @property
    def smpls(self) -> List[TierABC]:
        """
        Get a list of this `Experiment`s samples.
        """
        return list(self)


class Sample(NotebookTierBase):
    """
    Sample `Tier`.

    A `Sample` is intended to represent some object that you collect data on.

    As such, each sample has its own `DataSet`s.

    Notes
    -----
    A `Sample` id can't start with a number and can't contain `'-'` (dashes), as these confuse the name parser.
    """

    name_part_template = "{}"
    id_regex = r"([^0-9^-][^-]*)"

    @cached_prop
    def folder(self) -> Path:
        assert self.parent
        return self.parent.folder

    @property
    def datasets(self) -> List[TierABC]:
        """
        Convenient way of getting a list of `DataSet`s this sample has.
        """
        assert self.parent
        assert self.child_cls

        techs = []
        for technique in self.parent.techniques:
            dataset = self.child_cls(*self.identifiers, technique, project=self.project)
            if dataset.exists():
                techs.append(dataset)
        return techs

    def __iter__(self) -> Iterator[TierABC]:
        return iter(self.datasets)


class DataSet(FolderTierBase):
    """
    `DataSet` Tier.

    The final tier, intended to represent a folder containing a collection of files relating to a particular `Sample`.
    """

    short_type = "dset"
    name_part_template = "-{}"

    id_regex = r"(.+)"

    @cached_prop
    def folder(self) -> Path:
        assert self.parent

        return self.parent / self.id / self.parent.id

    def exists(self) -> bool:
        return self.folder.exists()

    def __truediv__(self, other: Any) -> Path:
        return cast(Path, self.folder / other)

    def __iter__(self) -> Iterator["os.DirEntry[Any]"]:
        """
        Call `os.scandir` on `self.folder`.
        """
        yield from os.scandir(self.folder)

    def __fspath__(self) -> str:
        return self.folder.__fspath__()


DEFAULT_TIERS = [Home, WorkPackage, Experiment, Sample, DataSet]
