import sys
import os
from typing import Set

from semantic_version import Version, validate, SimpleSpec


def latest_version(cas_lib_dir):
    return max([Version(entry.name) for entry in os.scandir(cas_lib_dir) if validate(entry.name)])


class PatchImporter:

    _imported: Set[object] = set()
    
    def __init__(self, version, cas_lib_dir):
        self._modules_before = None
        spec = SimpleSpec('{major}.{minor}.*'.format(major=version.major, minor=version.minor))
        max_compatible = spec.select(Version(entry.name) for entry in os.scandir(cas_lib_dir) if validate(entry.name))
        
        if max_compatible is None:
            raise ImportError("No compatible version of tools exists to match {}".format(spec))
                
        print("Using tools version {}".format(max_compatible))

        self.path = str(cas_lib_dir / str(max_compatible))
    
    def __enter__(self):
        while self._imported:
            del sys.modules[self._imported.pop()]
        
        sys.path.append(self.path)
        self._modules_before = set(sys.modules)
    
    def __exit__(self, *args):
        sys.path.remove(self.path)
        self._imported.update(set(sys.modules) - self._modules_before)

