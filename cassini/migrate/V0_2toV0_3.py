import json
import datetime
import shutil

from .base import BaseMigrator


class V0_2toV0_3(BaseMigrator):
    def __init__(self, project) -> None:
        self.project = project
        self.home = project.home

    def migrate(self):
        from cassini import NotebookTierBase

        for tier in self.walk_tiers():
            if not isinstance(tier, NotebookTierBase):
                continue
            else:
                backup_path = shutil.copy(
                    tier.meta_file, tier.meta_file.with_suffix(".backup")
                )
                try:
                    self.migrate_meta(tier)
                except Exception:
                    raise RuntimeError(
                        "Error occured, please restore from backup", backup_path
                    )

    def migrate_meta(self, tier):
        with open(tier.meta_file, "r") as fs:
            meta = json.load(fs)

        started = meta.get("started")

        if started:
            started_dt = datetime.datetime.strptime(started, "%d/%m/%Y")
            meta["started"] = str(started_dt)

        with open(tier.meta_file, "w") as fs:
            json.dump(meta, fs)
