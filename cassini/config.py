from pathlib import Path
from dataclasses import dataclass


SCIFY_DIR = Path(__file__).parent


@dataclass
class Config:
    """
    Basic Internal Configuration.

    Attributes
    ----------
    SCIFY_DIR : Path
        Path to cassini module. (Called SCIFY for legacy reasons).
    META_DIR_TEMPLATE : str
        Template filled in to name folder a tier's meta goes into.
    DEFAULT_TEMPLATE_DIR : Path
        Path to where the default templates are stored.
    TEMPLATE_EXT : str
        Extension appended to default template files when created.
    BASE_TEMPLATE : Path
        Path to the basic template, which is used as the default.
    """

    SCIFY_DIR = SCIFY_DIR
    META_DIR_TEMPLATE = ".{}s"

    DEFAULT_TEMPLATE_DIR = SCIFY_DIR / "defaults" / "templates"
    TEMPLATE_EXT = ".tmplt.ipynb"
    BASE_TEMPLATE = DEFAULT_TEMPLATE_DIR / "Tier.tmplt.ipynb"


config = Config()
