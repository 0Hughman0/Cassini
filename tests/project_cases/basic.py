from cassini import Project, DEFAULT_TIERS

project = Project(DEFAULT_TIERS, __file__)
project.test_project = True

if __name__ == '__main__':
    project.launch()
