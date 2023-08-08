from pathlib import Path
from typing import Union


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
