from pathlib import Path
import os
import sys
import functools
from typing import Union, Callable, Any, List, Tuple, TypeVar, Generic
from typing_extensions import Self, ParamSpec
import datetime

from .config import config
from .accessors import JSONType


def str_to_date(val: JSONType) -> datetime.datetime:
    assert isinstance(val, str)
    return datetime.datetime.strptime(val, config.DATE_FORMAT)


def date_to_str(date: datetime.datetime) -> str:
    return date.strftime(config.DATE_FORMAT)


class FileMaker:
    """
    Utility class for making files, and then rolling back if an exception occurs.
    """

    def __init__(self) -> None:
        self.folders_made: List[Path] = []
        self.files_made: List[Path] = []

    def __enter__(self) -> Self:
        self.files_made = []
        self.folders_made = []
        return self

    def mkdir(self, path: Path, exist_ok: bool = False) -> Union[Path, None]:
        if not path.exists():
            path.mkdir()
            self.files_made.append(path)
            return path
        if exist_ok:
            return None
        raise FileExistsError(path)

    def write_file(
        self, path: Path, contents: str = "", exist_ok: bool = False
    ) -> Union[Path, None]:
        if not path.exists():
            path.write_text(contents, encoding="utf-8")
            self.files_made.append(path)
            return path
        if exist_ok:
            return None
        raise FileExistsError(path)

    def copy_file(self, source: Path, dest: Path) -> Tuple[Path, Path]:
        self.write_file(dest, source.read_text())
        return source, dest

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type:
            print(f"{exc_type} occured, rolling back")
            for file in self.files_made:
                print("Deleting", file)
                file.unlink()
                print("Done")

            for folder in self.folders_made:
                print("Removing", folder)
                folder.rmdir()
                print("Done")
            raise exc_type(exc_val)


R = TypeVar("R")
P = ParamSpec("P")


class XPlatform(Generic[P, R]):
    """
    Class for easily making cross platform functions/ methods(?). Stops nasty if elses.

    Fallback functional called if no matching function added for current platform.

    Parameters
    ----------
    default: Callable[P, R]

    Returns
    -------
    self: XPlatform[P, R]
        Callable that will always call the appropriate function for the current platform.
    """

    def __init__(self, default: Callable[P, R]) -> None:
        self._func: Union[Callable[P, R], None] = None
        self._default: Callable[P, R] = default

    @property
    def func(self) -> Callable[P, R]:
        """
        Returns the platform appropriate function (or default if not known)
        """
        if self._func:
            return self._func

        return self._default

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return self.func(*args, **kwargs)

    def add(self, platform: str) -> Callable[[Callable[P, R]], "XPlatform[P, R]"]:
        """
        Add a platform dependent function. To be used as a decorator.

        Parameters
        ----------
        platform: str
            platform wrapped function called for.

        Returns
        -------
        self : XPlatform
            Callable that will always call the appropriate function for the current platform.
        """

        def wrapper(func: Callable[P, R]) -> "XPlatform[P, R]":
            if sys.platform == platform:
                self._func = func
                functools.update_wrapper(self, func)
            return self

        return wrapper


@XPlatform
def open_file(filename: Union[str, Path]) -> None:
    """
    *Nix open file implementation.
    """
    import subprocess

    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.call([opener, filename])


@open_file.add("win32")
def win_open_file(filename: Union[str, Path]) -> None:
    """
    Windows open file implementation.
    """
    os.startfile(filename)  # type: ignore[attr-defined]
