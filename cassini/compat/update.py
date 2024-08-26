import json
import re
from typing import List, Callable, TypeVar
import datetime
from abc import abstractmethod

import nbformat
from nbformat import NotebookNode

CellProcessor = Callable[[NotebookNode], None]


class BaseUpdater:
    cell_processors: List[CellProcessor] = []

    def __init_subclass__(cls) -> None:
        cls.cell_processors = []

    @abstractmethod
    def get_project(self):
        pass

    @classmethod
    def _cell_processor(cls, f: CellProcessor):
        cls.cell_processors.append(f)
        return f

    def __init__(self) -> None:
        self.project = self.get_project()
        self.home = self.project.home

    def walk_tiers(self):
        yield self.home

        for wp in self.home:
            yield wp

            for exp in wp:
                yield exp

                for smpl in exp:
                    yield smpl


def cell_processor(f):
    return BaseUpdater._cell_processor(f)


class V0_1to0_2(BaseUpdater):
    def get_project(self):
        from .. import env

        assert env.project
        return env.project

    def __init__(self):
        super().__init__()

    @cell_processor
    def fix_imports(cell):
        text = cell["source"]
        text = text.replace("from htools.exp import g", "from htools.scify import *")
        cell["source"] = text

    @cell_processor
    def fix_g_references(cell):
        text = cell["source"]

        def replace(match):
            return f"env.{match.group(1)}"

        cell["source"] = re.sub("g\.(.+)", replace, text)

    @cell_processor
    def replace_mksmpl(cell):
        pattern = "%%mksmpl (.+)"
        text = cell["source"]

        match = re.search(pattern, text)
        if match:
            cell["source"] = f"smpl = env('{match.group(1)}')\nsmpl.header()"

    @cell_processor
    def replace_smplconc(cell):
        text = cell["source"]
        cell["source"] = text.replace("%%smplconc", "%%conc")

    @cell_processor
    def replace_expconc(cell):
        text = cell["source"]
        cell["source"] = text.replace("%%expconc", "%%conc")

    @cell_processor
    def fix_meta_store(cell):
        text = cell["source"]
        pattern = "smpl\.write_meta\('(.+)', (.+)\)"

        def replace(match):
            return f"smpl.{match.group(1)} = {match.group(2)}"

        cell["source"] = re.sub(pattern, replace, text)

    def walk_smpls(self):
        for wp in self.home:
            for exp in wp:
                for smpl in exp:
                    yield smpl

    def update(self):
        for smpl in self.walk_smpls():
            if not smpl.file.exists():
                print(f"No file found for {smpl} - skippiping")
                continue

            print("Fixing", smpl)
            with open(smpl.file, "rb") as f:
                nb = nbformat.read(f, 4)

            print("Backing up old file")
            try:
                new_name = smpl.file.rename(
                    smpl.file.with_name(f"{smpl.name}-old.ipynb")
                )
            except FileExistsError:
                print(f"Already updated {smpl} - skipping")
                continue

            try:
                print("Applying processors")
                for cell in nb["cells"]:
                    for processor in self.cell_processors:
                        processor(cell)
                print("Success")
                print("Errors: ", nbformat.validate(nb, version=4))

                print("Writing new file")
                with open(smpl.file, "w", encoding="utf-8") as f:
                    nbformat.write(nb, f, 4)
                print("Success")
            except Exception:
                print("Exception occured, rolling back")
                new_name.rename(smpl.file.name)


class V0_2to0_3(BaseUpdater):
    def get_project(self):
        from .. import env

        assert env.project
        return env.project

    def __init__(self) -> None:
        super().__init__()

    def update(self):
        from cassini import NotebookTierBase

        for tier in self.walk_tiers():
            if not isinstance(tier, NotebookTierBase):
                continue
            else:
                self.update_meta(tier)

    def update_meta(self, tier):
        with open(tier.meta_file, "r") as fs:
            meta = json.load(fs)

        started = meta.get("started")

        if started:
            started_dt = datetime.datetime.strptime(started, "%d/%m/%Y")
            meta["started"] = str(started_dt)

        with open(tier.meta_file, "w") as fs:
            json.dump(meta, fs)
