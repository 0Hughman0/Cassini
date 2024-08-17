from __future__ import annotations

from typing import Union, TYPE_CHECKING, TypeVar, Any, List, Dict
from typing_extensions import TypeGuard

if TYPE_CHECKING:
    from .core import TierABC, Project
    from .sharing import SharedProject


class _Env:
    """
    Essentially a global object that describes the state of the project for this interpreter.

    As each notebook has its own interpreter, each notebook also has its own env that basically stores what the current
    project is and what tier this `ipynb` file corresponds to.

    Attributes
    ----------
    project : Project
        reference to the current project object. Returns `None` if one not set yet.

    Warnings
    --------
    This object is a singleton, so only one instance can exist at a time.

    This object shouldn't be created directly, instead you should call `project.env('...')` to set its value.
    """

    instance: Union[_Env, None] = None

    def __new__(cls, *args: Any, **kwargs: Any) -> _Env:
        if cls.instance:
            raise RuntimeError(
                "Attempted to create new _Env instance, only 1 _instance permitted per interpreter"
            )
        instance = object.__new__(cls)
        cls.instance = instance
        return instance

    def __init__(self) -> None:
        self.project: Union[Project, None] = None
        self._o: Union[TierABC, None] = None
        self.shareable_project: Union[SharedProject, None] = None
        self._caches: List[Dict[Any, Any]] = []

    @staticmethod
    def is_sharing(instance: _Env) -> TypeGuard["_SharingInstance"]:
        return bool(instance.shareable_project and instance.project)

    @staticmethod
    def is_shared(instance: _Env) -> TypeGuard["_SharedInstance"]:
        return bool(instance.shareable_project and not instance.project)

    @property
    def o(self) -> Union[TierABC, None]:
        """
        Reference to current Tier object.
        """
        return self._o

    def update(self, obj: TierABC) -> None:
        self._o = obj

    def create_cache(self):
        """
        Method for creating various caches throughout cassini.

        the env instances keeps track of these, to allow them to be cleared 
        cleanly during testing.

        This is an internal feature.
        """
        cache = dict()
        self._caches.append(cache)
        return cache

    def _reset(self):
        """
        Reset env instance to initial state. Used for testing.

        `project`, `shareable_project` and `caches` are cleared.
        """
        self.shareable_project = None
        self.project = None

        for cache in self._caches:
            cache.clear()


class _SharingInstance(_Env):
    shareable_project: SharedProject
    project: Project


class _SharedInstance(_Env):
    shareable_project: SharedProject
    project: None


env = _Env()
