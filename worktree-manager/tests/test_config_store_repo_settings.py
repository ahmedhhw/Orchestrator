"""Tests for per-repo settings in ConfigStore (muted checks, notifications, collapsed)."""
import pytest
from worktree_manager.config_store import ConfigStore


@pytest.fixture
def store(tmp_path):
    return ConfigStore(path=tmp_path / "config.json")


class TestMutedChecks:
    def test_muted_checks_round_trip(self, store):
        store.set_repo_muted_checks("org/repo", ["lint", "coverage"])
        result = store.get_repo_muted_checks("org/repo")
        assert sorted(result) == ["coverage", "lint"]


class TestNotificationPrefs:
    def test_notification_pref_defaults_to_true_when_unset(self, store):
        assert store.get_repo_notification_pref("org/repo", "ci_failed") is True

    def test_notification_pref_round_trips(self, store):
        store.set_repo_notification_pref("org/repo", "ci_failed", False)
        assert store.get_repo_notification_pref("org/repo", "ci_failed") is False


class TestCollapsed:
    def test_collapsed_defaults_to_false(self, store):
        assert store.get_repo_collapsed("org/repo") is False

    def test_collapsed_round_trips(self, store):
        store.set_repo_collapsed("org/repo", True)
        assert store.get_repo_collapsed("org/repo") is True


class TestIsolation:
    def test_settings_for_one_repo_do_not_bleed_into_another(self, store):
        store.set_repo_muted_checks("org/repo-a", ["lint"])
        store.set_repo_notification_pref("org/repo-a", "ci_failed", False)
        store.set_repo_collapsed("org/repo-a", True)

        assert store.get_repo_muted_checks("org/repo-b") == []
        assert store.get_repo_notification_pref("org/repo-b", "ci_failed") is True
        assert store.get_repo_collapsed("org/repo-b") is False
