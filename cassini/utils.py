import importlib
from pathlib import Path
import os
import sys
import functools
from typing import (
    MutableMapping,
    Type,
    Union,
    Callable,
    Any,
    List,
    Tuple,
    TypeVar,
    Generic,
)
from jupyterlab.labapp import LabApp, LabServerApp
from typing_extensions import Self, ParamSpec
import datetime

from .environment import env

import jinja2


class PathLibEnv(jinja2.Environment):
    """
    Subclass of `jinja2.Environment` to enable using `pathlib.Path` for template names.
    """

    def get_template(
        self,
        name: Union[Path, str],  # type: ignore[override]
        parent: Union[str, None] = None,
        globals: Union[MutableMapping[str, Any], None] = None,
    ) -> jinja2.Template:
        return super().get_template(
            name.as_posix() if isinstance(name, Path) else name,
            parent=parent,
            globals=globals,
        )


class CassiniLabApp(LabApp):  # type: ignore[misc]
    """
    Subclass of `jupyterlab.labapp.LabApp` that ensures `ContentsManager.allow_hidden = True`
    (needed for jupyter_cassini_server)
    """

    @classmethod
    def initialize_server(
        cls: Type[LabApp], argv: Union[Any, None] = None
    ) -> LabServerApp:
        """
        Patch serverapp to ensure hidden files are allowed, needed for jupyter_cassini_server
        """
        serverapp: LabServerApp = super().initialize_server(argv)
        serverapp.contents_manager.allow_hidden = True
        return serverapp


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


def find_project(import_string=None):
    """
    Gets ahold of the Project instance for this Jupyterlab server instance.

    If server was launched via `cassini.Project.launch()`, this will already be set.

    Otherwise, `import_string` or CASSINI_PROJECT environment variable can be set.

    This should be of the form:

        path/to/module:project_obj

    By default, `project_obj` is assumed to be called `project`. This will be imported from `module`, which by default is
    assumed to be `cas_project`.

    Note that for cassini to run with a regular jupyterlab instance, `ContentsManager.allow_hidden = True` must be set, either
     via a config, or passed as a command line argument e.g. `--ContentsManager.allow_hidden=True`
    """
    if env.project:
        return env.project

    if not import_string:
        CASSINI_PROJECT = os.environ["CASSINI_PROJECT"]
    else:
        CASSINI_PROJECT = import_string

    path = Path(CASSINI_PROJECT).absolute()

    module = None
    obj = None

    if ":" in path.name:
        module, obj = path.name.split(":")
        module = module.replace(".py", "")
        directory = path.parent.as_posix()
    elif path.is_file() or path.with_suffix(".py").is_file():
        directory = path.parent.as_posix()
        module = path.stem
        obj = "project"
    elif path.is_dir():
        directory = path.as_posix()
        module = "cas_project"
        obj = "project"
    else:
        raise RuntimeError(f"Cannot parse CASSINI_PROJECT {CASSINI_PROJECT}")

    sys.path.insert(0, directory)

    try:
        env.project = getattr(importlib.import_module(module), obj)
    finally:
        sys.path.remove(directory)

    return env.project
