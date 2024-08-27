import sys
import argparse
from typing import List

from cassini.utils import find_project

from .base import BaseMigrator
from .V0_2toV0_3 import V0_2toV0_3


migrators = {("0.2", "0.3"): V0_2toV0_3}


def main(args: List[str]) -> BaseMigrator:
    parser = argparse.ArgumentParser(
        description=(
            "Migration tool for cassini projects. "
            "It's not that fancy, so sequential updates may be needed."
        )
    )
    parser.add_argument(
        "old", choices=["0.2"], help="which version to migrate from"
    )
    parser.add_argument(
        "new", choices=["0.3"], help="which version to migrate to"
    )
    parser.add_argument(
        "--cassini-project",
        default="project.py:project",
        help="cassini project to migrate, see cassini.utils.find_project for possible forms",
    )

    out = parser.parse_args(args)

    project = find_project(out.cassini_project)

    print("Found project", project)

    old, new = out.old, out.new

    print("Looking for migrator for", old, "to", new)

    try:
        migrator = migrators[(old, new)](project)
    except KeyError:
        raise ValueError(
            "No migator available for this combination, options are", list(migrators)
        )

    print("Found", migrator)

    print("Running migrator")

    migrator.migrate()

    print("Success")

    return migrator


if __name__ == "__main__":
    main(sys.argv[1:])
