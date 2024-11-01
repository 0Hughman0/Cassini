from typing import List, Union, TYPE_CHECKING

from IPython.display import publish_display_data


if TYPE_CHECKING:
    from .core import TierABC, Project


class JLGui:
    """
    Provides UI for interacting with tiers in JupyterLab.

    Parameters
    ----------
    tier: TierABC
        Tier to provide a gui for.

    """

    def __init__(self, tier: "TierABC"):
        self.tier = tier

    def header(self):
        """
        Display header widget.
        """
        publish_display_data({"application/cassini.header+json": {}})

    def meta_editor(self, name: Union[str, List[str]]):
        """
        Display meta editor widget.

        Parameters
        ----------
        name: Union[str, List[str]]
            name or names of the meta attributes to edit.
        """
        if isinstance(name, str):
            name = [name]

        publish_display_data({"application/cassini.metaeditor+json": {"values": name}})


def extend_project(project: "Project"):
    """
    Extend a project to insert JLGui as the `TierBase.gui_class`. Not usually required as the JLGui is the default.

    Parameters
    ----------
    project: Project
        The project to extend.

    Returns
    -------
    project: Project
        The extended project.

    Example
    -------
    ```python
    ...
    from cassini import jlgui

    project = Project(...)
    jlgui.extend_project(project)
    ```
    """
    for tier_class in project.hierarchy:
        tier_class.gui_cls = JLGui

    return project
