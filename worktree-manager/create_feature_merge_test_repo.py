"""
Creates a test git repo at /tmp/wm-feature-merge-test with branches merged into
feature branches — for manually testing the cleanup wizard's 'merged into feature/X'
detection.

Branch structure:
  main
  ├── fix/old-bug          → merged into main (appears as "merged into main")
  ├── feature/payments     → NOT merged into main yet (protected)
  │   ├── fix/ticket-123   → merged into feature/payments
  │   └── fix/ticket-456   → merged into feature/payments
  └── feature/auth         → NOT merged into main yet (protected)
      └── fix/auth-bug     → merged into feature/auth

Expected cleanup wizard output:
  Merged:
    → into feature/auth
      ☑ fix/auth-bug
    → into feature/payments
      ☑ fix/ticket-123
      ☑ fix/ticket-456
    → into main
      ☑ fix/old-bug
  Protected:
    feature/auth  (⚠ feature)
    feature/payments  (⚠ feature)

Usage:
    python3.14 create_feature_merge_test_repo.py           # create
    python3.14 create_feature_merge_test_repo.py --remove  # remove
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_PATH = Path("/tmp/wm-feature-merge-test")
CONFIG = Path.home() / ".config" / "worktree-manager" / "config.json"


def _git(repo, *args):
    result = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"  git error: {result.stderr.strip()}", file=sys.stderr)
        sys.exit(1)


def _commit(repo, filename, content, message):
    (repo / filename).write_text(content)
    _git(repo, "add", filename)
    _git(repo, "commit", "-m", message)


def create():
    if REPO_PATH.exists():
        print(f"Removing existing {REPO_PATH} …")
        shutil.rmtree(REPO_PATH)

    REPO_PATH.mkdir(parents=True)
    print(f"Creating repo at {REPO_PATH} …")

    _git(REPO_PATH, "init", "-b", "main")
    _git(REPO_PATH, "config", "user.email", "test@test.com")
    _git(REPO_PATH, "config", "user.name", "Test")

    _commit(REPO_PATH, "README.md", "# test repo\n", "init: project scaffold")

    # fix/old-bug → merged into main
    print("  creating fix/old-bug → merge into main …")
    _git(REPO_PATH, "checkout", "-b", "fix/old-bug")
    _commit(REPO_PATH, "fix_old_bug.txt", "old bug fix\n", "fix: resolve old bug")
    _git(REPO_PATH, "checkout", "main")
    _git(REPO_PATH, "merge", "--no-ff", "fix/old-bug", "-m", "merge fix/old-bug into main")

    # feature/payments — branched from main
    print("  creating feature/payments …")
    _git(REPO_PATH, "checkout", "-b", "feature/payments")
    _commit(REPO_PATH, "payments.txt", "payments feature\n", "feat: payments scaffold")

    # fix/ticket-123 → merged into feature/payments
    print("  creating fix/ticket-123 → merge into feature/payments …")
    _git(REPO_PATH, "checkout", "-b", "fix/ticket-123")
    _commit(REPO_PATH, "ticket_123.txt", "ticket 123 fix\n", "fix: resolve ticket 123")
    _git(REPO_PATH, "checkout", "feature/payments")
    _git(REPO_PATH, "merge", "--no-ff", "fix/ticket-123", "-m", "merge fix/ticket-123 into feature/payments")

    # fix/ticket-456 → merged into feature/payments
    print("  creating fix/ticket-456 → merge into feature/payments …")
    _git(REPO_PATH, "checkout", "-b", "fix/ticket-456")
    _commit(REPO_PATH, "ticket_456.txt", "ticket 456 fix\n", "fix: resolve ticket 456")
    _git(REPO_PATH, "checkout", "feature/payments")
    _git(REPO_PATH, "merge", "--no-ff", "fix/ticket-456", "-m", "merge fix/ticket-456 into feature/payments")

    # feature/auth — branched from main
    print("  creating feature/auth …")
    _git(REPO_PATH, "checkout", "main")
    _git(REPO_PATH, "checkout", "-b", "feature/auth")
    _commit(REPO_PATH, "auth.txt", "auth feature\n", "feat: auth scaffold")

    # fix/auth-bug → merged into feature/auth
    print("  creating fix/auth-bug → merge into feature/auth …")
    _git(REPO_PATH, "checkout", "-b", "fix/auth-bug")
    _commit(REPO_PATH, "auth_bug.txt", "auth bug fix\n", "fix: resolve auth bug")
    _git(REPO_PATH, "checkout", "feature/auth")
    _git(REPO_PATH, "merge", "--no-ff", "fix/auth-bug", "-m", "merge fix/auth-bug into feature/auth")

    _git(REPO_PATH, "checkout", "main")

    wt_storage = Path("/tmp/wm-feature-merge-test-worktrees")
    wt_storage.mkdir(exist_ok=True)

    # Add to worktree-manager config
    if CONFIG.exists():
        data = json.loads(CONFIG.read_text())
    else:
        data = {"repos": {}}

    data.setdefault("repos", {})
    data["repos"][str(REPO_PATH)] = {
        "worktree_storage": str(wt_storage),
        "stale_days": 30,
        "last_editor": "cursor",
        "last_editor_mode": "new",
        "last_opened": "2026-05-23T00:00:00",
        "commands": [],
    }
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, indent=2))

    print()
    print("Done.")
    print()
    print(f"Repo:      {REPO_PATH}")
    print(f"Config:    {CONFIG}")
    print()
    print("Expected cleanup wizard state:")
    print("  Merged → into feature/auth:     fix/auth-bug")
    print("  Merged → into feature/payments: fix/ticket-123, fix/ticket-456")
    print("  Merged → into main:             fix/old-bug")
    print("  Protected:                      feature/auth, feature/payments")
    print()
    print("Open the worktree-manager app, select this repo, and open Cleanup Wizard.")


def remove():
    if CONFIG.exists():
        data = json.loads(CONFIG.read_text())
        data.setdefault("repos", {})
        if str(REPO_PATH) in data["repos"]:
            del data["repos"][str(REPO_PATH)]
            CONFIG.write_text(json.dumps(data, indent=2))
            print(f"Removed {REPO_PATH} from config.")

    wt_storage = Path("/tmp/wm-feature-merge-test-worktrees")
    for path in (REPO_PATH, wt_storage):
        if path.exists():
            shutil.rmtree(path)
            print(f"Deleted {path}")

    print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    if args.remove:
        remove()
    else:
        create()
