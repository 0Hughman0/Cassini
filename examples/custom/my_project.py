from cassini import TierABC, Home
from cassini.core import Project


class Book(Home):
    pass


class Chapter(TierABC):
    name_part_template = 'Chapter {}'


class Page(TierABC):
    name_part_template = 'pg. {}'


project = Project([Book, Chapter, Page], __file__)

if __name__ == '__main__':
    project.launch()
