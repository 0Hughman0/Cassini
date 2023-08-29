from cassini import Project, DEFAULT_TIERS
from cassini.jlgui import extend_project

project = Project(DEFAULT_TIERS, __file__)
extend_project(project)

if __name__ == '__main__':
    project.launch()
