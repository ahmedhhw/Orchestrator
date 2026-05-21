from worktree_manager.models import SavedCommand, RepoConfig


def test_saved_command_has_name_and_command():
    cmd = SavedCommand(name="frontend", command="npm run dev")
    assert cmd.name == "frontend"
    assert cmd.command == "npm run dev"


def test_repo_config_has_empty_commands_by_default():
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-20T10:00:00",
    )
    assert cfg.commands == []


def test_repo_config_accepts_commands_list():
    cmds = [SavedCommand(name="frontend", command="npm run dev")]
    cfg = RepoConfig(
        repo_path="/repos/proj",
        worktree_storage="/repos/proj-wt",
        stale_days=30,
        last_editor="cursor",
        last_editor_mode="reuse",
        last_opened="2026-05-20T10:00:00",
        commands=cmds,
    )
    assert len(cfg.commands) == 1
    assert cfg.commands[0].name == "frontend"
