from pathlib import Path
from dataclasses import dataclass


SCIFY_DIR = Path(__file__).parent


@dataclass
class Config:
    SCIFY_DIR = SCIFY_DIR
    DATE_FORMAT = "%d/%m/%Y"
    META_DIR_TEMPLATE = ".{}s"

    DEFAULT_TEMPLATE_DIR = SCIFY_DIR / "defaults" / "templates"
    TEMPLATE_EXT = ".tmplt.ipynb"
    BASE_TEMPLATE = DEFAULT_TEMPLATE_DIR / "Tier.tmplt.ipynb"


config = Config()
