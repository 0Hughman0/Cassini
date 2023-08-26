import re
from typing import List, Callable, TypeVar

import nbformat
from nbformat import NotebookNode

CellProcessor = Callable[[NotebookNode], None]


class BaseUpdater:
    cell_processors: List[CellProcessor]

    def cell_processor(self, f: CellProcessor):
        self.cell_processors.append(f)
        return f


class V0_1to0_2(BaseUpdater):
    def __init__(self):
        from .. import env

        assert env.project

        self.home = env.project.home
        self.cell_processors = []

        @self.cell_processor
        def fix_imports(cell):
            text = cell["source"]
            text = text.replace(
                "from htools.exp import g", "from htools.scify import *"
            )
            cell["source"] = text

        @self.cell_processor
        def fix_g_references(cell):
            text = cell["source"]

            def replace(match):
                return f"env.{match.group(1)}"

            cell["source"] = re.sub("g\.(.+)", replace, text)

        @self.cell_processor
        def replace_mksmpl(cell):
            pattern = "%%mksmpl (.+)"
            text = cell["source"]

            match = re.search(pattern, text)
            if match:
                cell["source"] = f"smpl = env('{match.group(1)}')\nsmpl.header()"

        @self.cell_processor
        def replace_smplconc(cell):
            text = cell["source"]
            cell["source"] = text.replace("%%smplconc", "%%conc")

        @self.cell_processor
        def replace_expconc(cell):
            text = cell["source"]
            cell["source"] = text.replace("%%expconc", "%%conc")

        @self.cell_processor
        def fix_meta_store(cell):
            text = cell["source"]
            pattern = "smpl\.write_meta\('(.+)', (.+)\)"

            def replace(match):
                return f"smpl.{match.group(1)} = {match.group(2)}"

            cell["source"] = re.sub(pattern, replace, text)

    def walk_nbs(self):
        for wp in self.home:
            for exp in wp:
                for smpl in exp:
                    yield smpl

    def update(self):
        for smpl in self.walk_nbs():
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
