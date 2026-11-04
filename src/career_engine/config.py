"""Runtime configuration; user data is never written inside the image layer."""

import os
from pathlib import Path


def data_directory() -> Path:
    return Path(os.environ.get("CAREER_DATA_DIR", "./data")).expanduser().resolve()


def database_path() -> Path:
    return data_directory() / "career.db"


def database_path_for(data_dir: Path) -> Path:
    return data_dir / "career.db"
