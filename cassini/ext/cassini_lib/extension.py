from typing import Union, TypeVar, Type
from typing_extensions import Annotated
from pathlib import Path

from semantic_version import Version

from .import_tools import PatchImporter, latest_version
from ... import Project, NotebookTierBase


def extend_project(project: Project, cas_lib_dir: Union[str, Path] = "cas_lib"):
    """
    Extend project to add `cas_lib` attribute to Tiers.
    """
    cas_lib_dir = project.project_folder / cas_lib_dir

    def make_cas_lib_folder(project, cas_lib_dir=cas_lib_dir):
        if not cas_lib_dir.exists():
            cas_lib_dir.mkdir()
            (cas_lib_dir / "0.1.0").mkdir()

    project.__before_setup_files__.append(make_cas_lib_folder)  # ensures creates folders if project already exists!

    for Tier in project.hierarchy:
        if issubclass(Tier, NotebookTierBase):
            # patch in the requried attributes to classes with notebooks!
            Tier.cas_lib_version = Tier.__meta_manager__.meta_attr(  # type: ignore[attr-defined]
                json_type=str,
                attr_type=Version,
                post_get=lambda v: Version(v) if v else v,
                pre_set=str,
                name="cas_lib_version",
            )
            Tier.cas_lib = create_cas_lib(cas_lib_dir)  # type: ignore[attr-defined]
    return project


def create_cas_lib(cas_lib_dir: Path):
    """
    Create `cas_lib` attribute for a given `cas_lib_dir`.
    """

    def cas_lib(self, version=None):
        """
        Allow importing from the appropraite `cas_lib` subdirectory for this tier.

        If the version not provided or `tier.cas_lib_version` not set, is set to the
        latest version found in `cas_lib_dir`, which is then stored in the tier's meta.

        As `cas_lib_version` is persistent after being set the first time, this will pin this version,
        unless either an explicit `version` parameter is provided, or `tier.cas_lib_version` is updated.
        """
        if version is None:
            if self.cas_lib_version:
                version = self.cas_lib_version
            else:
                version = self.cas_lib_version = latest_version(cas_lib_dir)
                print(f"Set {self}.cas_lib_version = {version}")

        if version == "lastest":
            version = latest_version(cas_lib_dir)

        if isinstance(version, str):
            version = Version(version)

        return PatchImporter(version, cas_lib_dir)

    return cas_lib
