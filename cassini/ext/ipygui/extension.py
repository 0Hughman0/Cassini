from typing import TYPE_CHECKING

from .gui import GUIS
from .components import BaseTierGui


if TYPE_CHECKING:
    from ...core import Project


def extend_project(project: "Project") -> "Project":
    for Tier in project.hierarchy:
        gui_cls = GUIS.get(Tier, BaseTierGui)
        Tier.gui_cls = gui_cls
    
    return project
