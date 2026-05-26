# Worktree Manager

A GUI app for managing Git worktrees across multiple repositories.

## Development

**Always use `python3.14`** to run tests and scripts in this project.

```bash
python3.14 -m pytest
```

### Running from a worktree

Use `run.py` to launch the app from any git worktree. It forces Python to load
the source in the current checkout, regardless of any editable install pointing
elsewhere:

```bash
python3.14 run.py
```

This works from any working directory — just provide the full path if you're not
in the `worktree-manager/` folder:

```bash
python3.14 /path/to/worktree-manager/run.py
```

### Running via the editable install

Install once and use the console script (always runs the main checkout, not a
worktree):

```bash
python3.14 -m pip install -e .
worktree-manager
# or
python3.14 -m worktree_manager.cli
```

Or activate the venv if present:

```bash
source .venv/bin/activate
python3.14 -m pytest
```
