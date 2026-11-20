"""Resolve explicitly selected data before importing the backend."""
import os
from pathlib import Path


def configure_paths(here: str, backend: str, data_dir: str | None = None) -> None:
    here, backend = Path(here), Path(backend)
    selected = data_dir or os.environ.get("SLT_DATA_DIR")
    if not selected:
        candidates = (here, backend.parent / "local_data", backend)
        selected = next((p for p in candidates if (p / "config.yaml").is_file()), candidates[1])
    selected = Path(selected).resolve()
    if not (selected / "config.yaml").is_file():
        raise FileNotFoundError(f"Missing config.yaml in {selected}. Use init_local_data.py for mock data.")
    os.environ["SLT_DATA_DIR"] = str(selected)
    if not os.environ.get("SLT_FRONTEND_DIST"):
        front = here / "frontend_dist"
        if not front.is_dir():
            front = backend.parent / "frontend/dist"
        os.environ["SLT_FRONTEND_DIST"] = str(front.resolve())
