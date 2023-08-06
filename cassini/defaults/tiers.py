from pathlib import Path
import os
import html

from typing import Iterator, List, overload

import pandas as pd # type: ignore[import]
from IPython.display import display
from ipywidgets import SelectMultiple, Text, HBox, Button # type: ignore[import]

from ..core import TierBase
from ..accessors import cached_prop, cached_class_prop
from ..utils import FileMaker
from ..ipygui import InputSequence, widgetify_html, BaseTierGui, SearchWidget
from ..environment import env


def ignore_dir(name):
    if name.startswith('.'):
        return True
    if name.startswith('_'):
        return True
    return False


class HomeGui(BaseTierGui):

    def _get_header_components(self):
        components = dict()
        components['Search'] = lambda: SearchWidget().as_widget()
        child = self.tier.child_cls
        if child:
            child_name = child.pretty_type
            components[f'{child_name}s'] = self._build_children
            components[f'New {child_name}'] = self.new_child

        return components


class Home(TierBase):
    """
    Home `Tier`.

    This, or a subclass of this should generally be the first entry in your hierarchy, essentially represents the top
    level folder in your hierarchy.

    Creates the `Home.ipynb` notebook that allows easy navigation of your project.
    """

    gui_cls = HomeGui

    @cached_prop
    def name(self):
        return self.pretty_type

    @cached_prop
    def folder(self):
        assert env.project
        assert self.child_cls
        return env.project.project_folder / (self.child_cls.pretty_type + 's')

    @cached_prop
    def file(self):
        assert env.project
        return env.project.project_folder / f"{self.name}.ipynb"
        
    @cached_prop
    def meta_file(self):
        return None
    
    def serialize(self) -> dict:
        data = {}
        
        data['identifiers'] = self.name
        data['name'] = self.name
        data['file'] = str(self.file)
        data['parents'] = []
        data['children'] = [child.name for child in self]
        
        return data

    def exists(self):
        return self.folder.exists()

    def setup_files(self):
        assert self.child_cls

        with FileMaker() as maker:
            print(f"Creating {self.child_cls.pretty_type} folder")
            maker.mkdir(self.folder)
            print("Success")

        with FileMaker() as maker:
            print(f"Creating Tier File ({self.file})")
            maker.write_file(self.file, self.render_template(self.default_template))
            print("Success")


class WorkPackage(TierBase):
    """
    WorkPackage Tier.

    Intended to contain all the work towards a particular goal. i.e. prove that we can do this.

    Next level down are `Experiment`s.
    """

    name_part_template = "WP{}"
    
    short_type = 'wp'

    @property
    def exps(self):
        """
        Gets a list of all this `WorkPackage`s experiments.
        """
        return list(self)


class ExperimentGui(BaseTierGui):

    def new_dataset(self):
        """
        A handy widget for creating new `DataSets`.
        """
        samples = list(self.tier)
        option_map = {sample.name: sample for sample in samples}

        selection = SelectMultiple(
            options=option_map.keys(),
            description='Auto Add')

        def create(name, auto_add):
            with form.status:
                self.tier.setup_technique(name)
                if auto_add:
                    for sample in (option_map[name] for name in auto_add):
                        o = sample[name]
                        o.setup_files()
                        display(widgetify_html(o._repr_html_()))

        form = InputSequence(create,
                             Text(description=f'Name:', placeholder='e.g. XRD'),
                             selection)

        return form.as_widget()

    def _get_header_components(self):
        components = super()._get_header_components()
        components['New Data'] = self.new_dataset
        return components


class Experiment(TierBase):
    """
    Experiment `Tier`.

    Just below `WorkPackage`, experiments are intended to be collections of samples and datasets that work towards the
    goal of the parent `WorkPackage`.

    Each `Experiment` has a number of samples.
    """

    name_part_template = '.{}'

    short_type = 'exp'

    gui_cls = ExperimentGui

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

    def setup_technique(self, name):
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

    def children_df(self, include=None, exclude=None):
        df = super().children_df(include=include, exclude=exclude)

        if df is None:
            return None

        df['datasets'] = pd.Series({smpl.name: list(dataset.id for dataset in smpl.datasets)
                                    for smpl in self})
        return df

    @property
    def smpls(self):
        """
        Get a list of this `Experiment`s samples.
        """
        return list(self)


class SampleGui(BaseTierGui):

    def new_child(self):

        def create(name):
            with form.status:
                o = self.tier[name]
                o.setup_files()

        form = InputSequence(create,
                             Text(description=f'Name:', placeholder='e.g. XRD'))

        return form.as_widget()

    def _build_children(self):
        buttons = []
        for dataset in self.tier.datasets:
            b = Button(description=dataset.id)

            def make_callback(dataset):
                def open_folder(change):
                    dataset.open_folder()
                return open_folder

            b.on_click(make_callback(dataset))
            buttons.append(b)
        return HBox(tuple(buttons))

    def _get_header_components(self):
        components = super()._get_header_components()
        return components


class Sample(TierBase):
    """
    Sample `Tier`.

    A `Sample` is intended to represent some object that you collect data on.

    As such, each sample has its own `DataSet`s.

    Notes
    -----
    A `Sample` id can't start with a number and can't contain `'-'` (dashes), as these confuse the name parser.
    """
    name_part_template = '{}'
    id_regex = r'([^0-9^-][^-]*)'

    gui_cls = SampleGui

    @cached_prop
    def folder(self):
        assert self.parent
        return self.parent.folder

    @property
    def datasets(self) -> list:
        """
        Convenient way of getting a list of `DataSet`s this sample has.
        """
        assert self.parent
        assert self.child_cls

        techs = []
        for technique in self.parent.techniques:
            dataset = self.child_cls(*self.identifiers, technique)
            if dataset.exists():
                techs.append(dataset)
        return techs

    def __iter__(self):
        return iter(self.datasets)


class DataSet(TierBase):
    """
    `DataSet` Tier.

    The final tier, intended to represent a folder containing a collection of files relating to a particular `Sample`.
    """
    short_type = 'dset'

    name_part_template = '-{}'
    id_regex = r'(.+)'

    @cached_class_prop
    def default_template(cls):
        return None

    @cached_prop
    def folder(self):
        assert self.parent

        return self.parent / self.id / self.parent.id

    @cached_prop
    def href(self):
        return html.escape(Path(os.path.relpath(self.folder, os.getcwd())).as_posix()) + '/'

    def exists(self):
        return self.folder.exists()

    def setup_files(self, template=None):
        print(f"Creating Folder for Data: {self}")

        with FileMaker() as maker:
            maker.mkdir(self.folder.parent, exist_ok=True)
            maker.mkdir(self.folder)

        print(f"Success")

    @cached_prop
    def meta_file(self):
        """
        `DataSet`s have no meta.
        """
        return None

    @cached_prop
    def file(self):
        """
        `DataSet`s have no file
        """
        return None
    
    @classmethod
    def get_templates(cls):
        """
        Datasets have no templates.
        """
        return []

    def __truediv__(self, other):
        return self.folder / other

    def __iter__(self) -> Iterator[os.DirEntry]:
        """
        Call `os.scandir` on `self.folder`.
        """
        yield from os.scandir(self.folder)

    def __fspath__(self):
        return self.folder.__fspath__()


DEFAULT_TIERS = [Home, WorkPackage, Experiment, Sample, DataSet]
