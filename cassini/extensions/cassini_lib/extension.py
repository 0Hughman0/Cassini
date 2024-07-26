from typing import Union, TypeVar, Type
from typing_extensions import Annotated
from pathlib import Path

from semantic_version import Version

from .import_tools import PatchImporter, latest_version
from ... import Project, NotebookTierBase


def extend_project(project: Project, cas_lib_dir: Union[str, Path] = "cas_lib"):
    cas_lib_dir = project.project_folder / cas_lib_dir

    def make_cas_lib_folder(project, cas_lib_dir=cas_lib_dir):
        if not cas_lib_dir.exists():
            cas_lib_dir.mkdir()
            (cas_lib_dir / "0.1.0").mkdir()

    project.__after_setup_files__.append(make_cas_lib_folder)

    for Tier in project.hierarchy:
        if issubclass(Tier, NotebookTierBase):
            # patch in the requried attributes to classes with notebooks!
            Tier.cas_lib_version = Tier.__meta_manager__.meta_attr(
                json_type=str,
                attr_type=Version,  # type: ignore[attr-defined]
                post_get=lambda v: Version(v) if v else v,
                pre_set=str,
                name="cas_lib_version",
            )
            Tier.cas_lib = create_cas_lib(cas_lib_dir)  # type: ignore[attr-defined]
    return project


def create_cas_lib(cas_lib_dir: Path):
    def cas_lib(self, version=None):
        if version is None:
            if self.cas_lib_version:
                version = self.cas_lib_version
            else:
                version = self.cas_lib_version = latest_version(cas_lib_dir)
                print(f"Set {self}.tools_version = {version}")

        if version == "lastest":
            version = latest_version(cas_lib_dir)

        if isinstance(version, str):
            version = Version(version)

        return PatchImporter(version, cas_lib_dir)

    return cas_lib
