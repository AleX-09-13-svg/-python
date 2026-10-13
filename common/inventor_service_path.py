from __future__ import annotations

import sys
from pathlib import Path


INVENTOR_SERVICE_ROOT = (
    Path(__file__).resolve().parents[2] / "01_inventor_service"
)


def ensure_inventor_service_path() -> Path:
    """Make the sibling inventor_service package importable for launcher scripts."""
    root_text = str(INVENTOR_SERVICE_ROOT)

    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    return INVENTOR_SERVICE_ROOT
