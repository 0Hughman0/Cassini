from cassini import Project, DEFAULT_TIERS
from cassini.ext import cassini_lib

project = Project(DEFAULT_TIERS, __file__)

if __name__ == '__main__':
    project.launch()
