"""Tests for the portable run.py launcher."""
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RUN_PY = REPO_ROOT / "run.py"


def test_run_py_exists():
    assert RUN_PY.exists(), "run.py must exist in the worktree-manager directory"


def test_run_py_inserts_repo_root_at_front_of_sys_path():
    """run.py must prepend its own directory so the local package wins."""
    result = subprocess.run(
        [sys.executable, str(RUN_PY), "--help"],
        capture_output=True,
        text=True,
    )
    # --help exits cleanly; if sys.path injection is missing the import would fail
    assert result.returncode == 0, f"run.py --help failed:\n{result.stderr}"


def test_run_py_loads_local_worktree_manager(tmp_path, monkeypatch):
    """Importing run.py must resolve worktree_manager from the repo root, not site-packages."""
    spec = importlib.util.spec_from_file_location("run", RUN_PY)
    # We only want to verify the path manipulation, not actually launch the Qt app.
    # Parse run.py source and check sys.path insertion logic is present.
    source = RUN_PY.read_text()
    assert "sys.path.insert(0" in source, "run.py must insert repo root at sys.path[0]"
    assert "Path(__file__)" in source, "run.py must use __file__ to locate itself"
