# Worktree Manager

A GUI app for managing Git worktrees across multiple repositories.

## Development

**Always use `python3.14`** to run tests and scripts in this project.

```bash
python3.14 -m pytest
```

Run the app from the checkout with:

```bash
python3.14 -m worktree_manager.cli
```

Or install editable mode once and use the console script:

```bash
python3.14 -m pip install -e .
worktree-manager
```

Or activate the venv if present:

```bash
source .venv/bin/activate
python3.14 -m pytest
```
