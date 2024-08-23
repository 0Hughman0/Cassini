from cassini import DEFAULT_TIERS
from cassini.core import Project
from cassini.jlgui import extend_project

project = Project(DEFAULT_TIERS, __file__)
extend_project(project)

if __name__ == '__main__':
    project.launch()
