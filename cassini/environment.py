from __future__ import annotations

from typing import (
    Union,
    TYPE_CHECKING,
    TypeVar,
    Any,
)
from typing_extensions import TypeGuard

if TYPE_CHECKING:
    from .core import TierABC, Project


ValWithInstance = TypeVar("ValWithInstance")


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
        self.SHARED: bool = False

    def _has_instance(
        self, val: Union[ValWithInstance, None]
    ) -> TypeGuard[ValWithInstance]:
        return self.instance is not None

    @property
    def o(self) -> Union[TierABC, None]:
        """
        Reference to current Tier object.
        """
        if self._has_instance(self._o):
            return self._o

        return None

    def update(self, obj: TierABC) -> None:
        self._o = obj


env = _Env()
