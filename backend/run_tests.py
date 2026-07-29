from __future__ import annotations

from pathlib import Path
import shutil
import sys
from uuid import uuid4

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
base_temp = PROJECT_ROOT / ".tmp" / f"pytest-{uuid4().hex}"
sys.path.insert(0, str(PROJECT_ROOT))

try:
    exit_code = pytest.main(
        [
            "backend/tests",
            "-q",
            "-p",
            "no:cacheprovider",
            f"--basetemp={base_temp}",
        ]
    )
finally:
    shutil.rmtree(base_temp, ignore_errors=True)

sys.exit(exit_code)
