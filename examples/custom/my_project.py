from cassini import TierBase, Home, Project


class Book(Home):
    pass


class Chapter(TierBase):
    name_part_template = 'Chapter {}'


class Page(TierBase):
    name_part_template = 'pg. {}'


project = Project([Book, Chapter, Page], __file__)

if __name__ == '__main__':
    project.launch()
