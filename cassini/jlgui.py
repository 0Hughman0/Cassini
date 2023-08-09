from typing import List, Union

from IPython.display import publish_display_data

from .environment import Project
from .ipygui import BaseTierGui


class JLGui(BaseTierGui):
    def __init__(self, tier):
        self.tier = tier

    def header(self):
        publish_display_data({"application/cassini.header+json": {}})

    def meta_editor(self, name: Union[str, List[str]]):
        if isinstance(name, str):
            name = [name]

        publish_display_data({"application/cassini.metaeditor+json": {"values": name}})


def extend_project(project: Project):
    for tier_class in project.hierarchy:
        tier_class.gui_cls = JLGui

    return project
