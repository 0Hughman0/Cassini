from cassini import Project, DEFAULT_TIERS

my_project = Project(DEFAULT_TIERS, __file__)
my_project.test_project = True

if __name__ == '__main__':
    my_project.launch()
