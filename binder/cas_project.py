from cassini import Project, DEFAULT_TIERS, WorkPackage

project = Project(DEFAULT_TIERS, __file__)

if __name__ == '__main__':
    project.launch()
