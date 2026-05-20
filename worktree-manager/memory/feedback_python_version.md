---
name: feedback-python-version
description: Always use python3.14 to run tests and scripts in the worktree-manager project
metadata:
  type: feedback
---

Always use `python3.14` (not `python` or `.venv/bin/python`) when running tests or scripts in the worktree-manager project.

**Why:** User corrected this explicitly during Phase 1 implementation.

**How to apply:** Any `pytest`, `python -m pytest`, or script execution in `/Users/ahmedhhw/repos/dev-tools/worktree-manager` should use `python3.14 -m pytest` or `python3.14 <script>`.
