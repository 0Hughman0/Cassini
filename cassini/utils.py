from pathlib import Path
import os
import sys
import functools
from typing import Union, Callable, Any
from typing_extensions import Self


class FileMaker:
    """
    Utility class for making files, and then rolling back if an exception occurs.
    """

    def __init__(self):
        self.folders_made = []
        self.files_made = []

    def __enter__(self):
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
            path.write_text(contents)
            self.files_made.append(path)
            return path
        if exist_ok:
            return None
        raise FileExistsError(path)

    def copy_file(self, source, dest):
        self.write_file(dest, source.read_text())
        return source, dest

    def __exit__(self, exc_type, exc_val, exc_tb):
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


class XPlatform:
    """
    Class for easily making cross platform functions/ methods(?). Stops nasty if elses.
    """

    def __init__(self) -> None:
        self._func: Union[Callable, None] = None
        self._default: Union[Callable, None] = None

    @property
    def func(self) -> Callable:
        """
        Returns the platform appropriate function (or default if not known)
        """
        if self._func:
            return self._func
        
        assert self._default

        return self._default        

    def __call__(self, *args, **kwargs):
        return self.func(*args, **kwargs)

    def add(self, platform: str) -> Callable[[Any], Self]:
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
        def wrapper(func):
            if sys.platform == platform:
                self._func = func
                functools.update_wrapper(self, func)
            return self

        return wrapper

    def default(self, func: Callable) -> 'XPlatform':
        """
        Fallback functional called if no matching function added for current platform.

        Parameters
        ----------
        func: Callable

        Returns
        -------
        self: XPlatform
            Callable that will always call the appropriate function for the current platform.
        """
        self._default = func
        return self


open_file = XPlatform()


@open_file.add('win32')
def win_open_file(filename: str):
    """
    Windows open file implementation.
    """
    # mypy doesn't understand XPlatform implementation... maybe this is working too hard to please?
    if sys.platform != 'win32':
        raise RuntimeError("Calling win32 specific method in wrong platform")
    
    os.startfile(filename)


@open_file.default
def nix_open_file(filename: str):
    """
    *Nix open file implementation.
    """
    import subprocess
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    subprocess.call([opener, filename])
