import json
import datetime
import shutil

from .base import BaseMigrator


class V0_2toV0_3(BaseMigrator):
    """
    Migrate from cassini version `0.2.x` to `0.3.x`.

    This class should not be used directly, instead use the CLI app! `python -m cassini.migrate --help`.

    Parameters
    ----------
    project : Project
        The project to migrate.
    """
    
    def __init__(self, project) -> None:
        self.project = project
        self.home = project.home

    def migrate(self):
        """
        Perform the migration.
        """
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
                else:
                    print("Successfully migrated, removing backup")
                    backup_path.unlink()

    def migrate_meta(self, tier):
        """
        Upgrade the format of `started` meta value to Timezone aware ISO string. Uses system timezone.        
        """
        with open(tier.meta_file, "r") as fs:
            meta = json.load(fs)

        started = meta.get("started")

        if started:
            started_dt = datetime.datetime.strptime(
                started, "%d/%m/%Y"
            ).astimezone()  # assume local timezone.
            meta["started"] = str(started_dt)

        with open(tier.meta_file, "w") as fs:
            json.dump(meta, fs)
