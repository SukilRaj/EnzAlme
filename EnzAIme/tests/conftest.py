"""
tests/conftest.py
====================
Shared pytest fixtures. Ensures the shared core package and backend app
package are importable regardless of where pytest is invoked from.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "common"))
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "src"))

import pytest  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from app.main import app
    from fastapi.testclient import TestClient
    return TestClient(app)
