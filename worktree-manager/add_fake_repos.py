"""
Populates ~/.config/worktree-manager/config.json with fake repos for
stress-testing the sidebar repo list UI.

All fake repos live under /tmp/wm-fake-repos/ — delete that directory
plus run `python3.14 remove_fake_repos.py` to clean up.

Usage:
    python3.14 add_fake_repos.py
    python3.14 add_fake_repos.py --remove
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

CONFIG = Path.home() / ".config" / "worktree-manager" / "config.json"
FAKE_ROOT = Path("/tmp/wm-fake-repos")

FAKE_NAMES = [
    "frontend-react-app",
    "backend-api-server",
    "mobile-ios-client",
    "mobile-android-client",
    "design-system",
    "data-pipeline",
    "ml-model-training",
    "auth-service",
    "notification-service",
    "billing-service",
    "analytics-dashboard",
    "admin-portal",
    "devops-infra",
    "docs-site",
    "sdk-python",
    "sdk-javascript",
    "sdk-go",
    "legacy-monolith",
    "event-bus",
    "search-service",
]


def _load() -> dict:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text())
    return {"repos": {}}


def _save(data: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, indent=2))


def add_fake_repos() -> None:
    FAKE_ROOT.mkdir(parents=True, exist_ok=True)

    data = _load()
    data.setdefault("repos", {})

    now = datetime.now(tz=timezone.utc)
    added = 0

    for i, name in enumerate(FAKE_NAMES):
        repo_path = str(FAKE_ROOT / name)
        if repo_path in data["repos"]:
            print(f"  skip (already exists): {name}")
            continue

        path = FAKE_ROOT / name
        path.mkdir(exist_ok=True)
        subprocess.run(["git", "init", str(path)], capture_output=True)
        subprocess.run(["git", "-C", str(path), "config", "user.email", "fake@test.com"], capture_output=True)
        subprocess.run(["git", "-C", str(path), "config", "user.name", "Fake"], capture_output=True)
        (path / "README.md").write_text(f"# {name}\n")
        subprocess.run(["git", "-C", str(path), "add", "."], capture_output=True)
        subprocess.run(["git", "-C", str(path), "commit", "-m", "init"], capture_output=True)

        last_opened = (now - timedelta(days=i)).isoformat()
        data["repos"][repo_path] = {
            "worktree_storage": str(FAKE_ROOT / f"{name}-worktrees"),
            "stale_days": 30,
            "last_editor": "cursor",
            "last_editor_mode": "new",
            "last_opened": last_opened,
            "commands": [],
        }
        print(f"  added: {name}")
        added += 1

    _save(data)
    print(f"\nDone. Added {added} fake repos under {FAKE_ROOT}")
    print("Run with --remove to undo.")


def remove_fake_repos() -> None:
    import shutil

    data = _load()
    data.setdefault("repos", {})

    removed = 0
    for name in FAKE_NAMES:
        repo_path = str(FAKE_ROOT / name)
        if repo_path in data["repos"]:
            del data["repos"][repo_path]
            removed += 1
            print(f"  removed from config: {name}")

    _save(data)

    if FAKE_ROOT.exists():
        shutil.rmtree(FAKE_ROOT)
        print(f"\nDeleted {FAKE_ROOT}")

    print(f"Done. Removed {removed} fake repos from config.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true", help="Remove all fake repos")
    args = parser.parse_args(sys.argv[1:])

    if args.remove:
        remove_fake_repos()
    else:
        add_fake_repos()
