import warnings
from typing import TYPE_CHECKING

from .gui import GUIS
from .components import BaseTierGui


warnings.warn(
    "Use of the ipy GUI is deprecrated, please use the JL GUI instead. This GUI will be removed in the next minor version",
    DeprecationWarning,
)


if TYPE_CHECKING:
    from ...core import Project


def extend_project(project: "Project") -> "Project":
    """
    Extend `project` to use the IPython gui.
    """
    for Tier in project.hierarchy:
        gui_cls = GUIS.get(Tier, BaseTierGui)
        Tier.gui_cls = gui_cls

    return project
