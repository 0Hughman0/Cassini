from abc import abstractmethod
from typing import Callable, List

from nbformat import NotebookNode

CellProcessor = Callable[[NotebookNode], None]


class BaseUpdater:
    cell_processors: List[CellProcessor] = []

    def __init_subclass__(cls) -> None:
        cls.cell_processors = []

    @classmethod
    def _cell_processor(cls, f: CellProcessor):
        cls.cell_processors.append(f)
        return f

    def walk_tiers(self):
        yield self.home

        for wp in self.home:
            yield wp

            for exp in wp:
                yield exp

                for smpl in exp:
                    yield smpl

    @abstractmethod
    def migrate(self):
        """
        Perform the migration.
        """


def cell_processor(f):
    return BaseUpdater._cell_processor(f)
