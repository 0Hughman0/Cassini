from cassini import Project, DEFAULT_TIERS
from cassini.jlgui import extend_project
import os

project = Project(DEFAULT_TIERS, __file__)
extend_project(project)

os.environ['PYTHONPATH'] = os.get('PYTHONPATH', '') + os.pathsep + os.path.pardir(__file__)

if __name__ == '__main__':
    project.launch()
