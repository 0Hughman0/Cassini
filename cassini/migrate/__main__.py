import sys
import argparse

from cassini.utils import find_project
from cassini import env

from .V0_1toV0_2 import V0_1toV0_2
from .V0_2toV0_3 import V0_2toV0_3


migrators = {
    ('0.1', '0.2'): V0_1toV0_2,
    ('0.2', '0.3'): V0_2toV0_3
}


def main(args):
    parser = argparse.ArgumentParser(description=("Migration tool for cassini projects. "
                                                  "It's not that fancy, so sequential updates may be needed."))
    parser.add_argument("old", choices=['0.1', '0.2'], help="which version to migrate from")
    parser.add_argument("new", choices=['0.2', '0.3'], help="which version to migrate to")
    parser.add_argument("--cassini-project", default='project.py:project',
                        help="cassini project to migrate, see cassini.utils.find_project for possible forms")

    args = parser.parse_args(args)

    project = find_project(args.cassini_project)

    print("Found project", project)
    
    old, new = args.old, args.new

    print("Looking for migrator for", old, "to", new)

    try:
        migrator = migrators[(old, new)]()
    except KeyError:
        raise ValueError("No migator available for this combination, options are", list(migrators))
    
    print("Found", migrator)
    
    print("Running migrator")
    
    migrator.migrate()

    print("Success")


if __name__ == '__main__':
    main(sys.argv[1:])
