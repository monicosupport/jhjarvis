"""Tests for the Uncensored Guardian framework."""

import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent))

from guardian import (
    Provider,
    GuardianConfig,
    SubAgentResult,
    HealthCheckResult,
    RepairSuggestion,
    load_config,
    get_active_providers,
    spawn_agent,
    read_own_source,
    run_health_checks,
    generate_repair_suggestion,
    self_repair,
)


# ---------------------------------------------------------------------------
# Config Loading Tests
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_loads_default_config(self):
        config = load_config()
        assert isinstance(config, GuardianConfig)
        assert len(config.providers) >= 1

    def test_parses_providers(self):
        config = load_config()
        for p in config.providers:
            assert isinstance(p, Provider)
            assert p.name
            assert p.endpoint
            assert p.model

    def test_parses_guardian_settings(self):
        config = load_config()
        assert isinstance(config.self_repair_enabled, bool)
        assert config.max_repair_attempts >= 1
        assert config.health_check_interval_seconds > 0

    def test_missing_config_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config(Path("/nonexistent/config.json"))

    def test_custom_config_path(self, tmp_path):
        custom = tmp_path / "test_config.json"
        custom.write_text(json.dumps({
            "providers": [
                {"name": "Test", "endpoint": "http://localhost", "model": "test-model", "priority": 1, "enabled": True}
            ],
            "guardian": {"self_repair_enabled": False},
            "sub_agents": {}
        }))
        config = load_config(custom)
        assert len(config.providers) == 1
        assert config.providers[0].name == "Test"
        assert config.self_repair_enabled is False


# ---------------------------------------------------------------------------
# Provider Selection Tests
# ---------------------------------------------------------------------------

class TestGetActiveProviders:
    def test_returns_only_enabled(self):
        config = GuardianConfig(providers=[
            Provider(name="A", endpoint="http://a", model="m", priority=1, enabled=True),
            Provider(name="B", endpoint="http://b", model="m", priority=2, enabled=False),
            Provider(name="C", endpoint="http://c", model="m", priority=3, enabled=True),
        ])
        active = get_active_providers(config)
        assert len(active) == 2
        assert all(p.enabled for p in active)

    def test_sorted_by_priority(self):
        config = GuardianConfig(providers=[
            Provider(name="Low", endpoint="http://l", model="m", priority=5, enabled=True),
            Provider(name="High", endpoint="http://h", model="m", priority=1, enabled=True),
            Provider(name="Mid", endpoint="http://m", model="m", priority=3, enabled=True),
        ])
        active = get_active_providers(config)
        assert active[0].name == "High"
        assert active[1].name == "Mid"
        assert active[2].name == "Low"

    def test_empty_when_all_disabled(self):
        config = GuardianConfig(providers=[
            Provider(name="A", endpoint="http://a", model="m", priority=1, enabled=False),
        ])
        assert get_active_providers(config) == []


# ---------------------------------------------------------------------------
# Sub-Agent Spawning Tests
# ---------------------------------------------------------------------------

class TestSpawnAgent:
    def test_returns_pending_for_background(self):
        result = spawn_agent(task="do something", name="test-agent", run_in_background=True)
        assert isinstance(result, SubAgentResult)
        assert result.status == "pending"
        assert result.output is None
        assert result.agent_name == "test-agent"
        assert result.task == "do something"

    def test_returns_completed_for_foreground(self):
        result = spawn_agent(task="analyze code", name="analyzer", run_in_background=False)
        assert result.status == "completed"
        assert result.output is not None
        assert "analyze code" in result.output

    def test_accepts_provider(self):
        provider = Provider(name="Venice", endpoint="http://v", model="llama", priority=1)
        result = spawn_agent(task="test", provider=provider)
        assert result.status == "pending"

    def test_default_name(self):
        result = spawn_agent(task="test")
        assert result.agent_name == "sub-agent"


# ---------------------------------------------------------------------------
# Self-Repair Tests
# ---------------------------------------------------------------------------

class TestReadOwnSource:
    def test_reads_guardian_source(self):
        source = read_own_source()
        assert "def self_repair" in source
        assert "def spawn_agent" in source
        assert len(source) > 100

    def test_reads_specified_file(self):
        source = read_own_source(__file__)
        assert "TestReadOwnSource" in source


class TestHealthChecks:
    def test_all_pass_with_valid_config(self):
        config = load_config()
        results = run_health_checks(config)
        assert all(isinstance(r, HealthCheckResult) for r in results)
        assert all(r.passed for r in results)

    def test_providers_fail_when_none_enabled(self):
        config = GuardianConfig(providers=[
            Provider(name="X", endpoint="http://x", model="m", priority=1, enabled=False),
        ])
        results = run_health_checks(config)
        provider_check = next(r for r in results if r.check_name == "providers_available")
        assert not provider_check.passed


class TestGenerateRepairSuggestion:
    def test_no_suggestion_for_passing_check(self):
        check = HealthCheckResult(passed=True, check_name="test")
        result = generate_repair_suggestion(check, "source", "file.py")
        assert result is None

    def test_suggestion_for_config_error(self):
        check = HealthCheckResult(passed=False, check_name="config_valid", message="File not found")
        result = generate_repair_suggestion(check, "", "guardian.py")
        assert isinstance(result, RepairSuggestion)
        assert "config.json" in result.file_path.lower() or "Config error" in result.reason

    def test_suggestion_for_no_providers(self):
        check = HealthCheckResult(passed=False, check_name="providers_available", message="None enabled")
        source = '"enabled": false\n'
        result = generate_repair_suggestion(check, source, "guardian.py")
        assert result is not None
        assert "enable" in result.reason.lower() or "provider" in result.reason.lower()

    def test_generic_suggestion_for_unknown_check(self):
        check = HealthCheckResult(passed=False, check_name="unknown_check", message="Something broke")
        result = generate_repair_suggestion(check, "source", "file.py")
        assert result is not None
        assert "Manual review" in result.reason


class TestSelfRepair:
    def test_healthy_system(self):
        config = load_config()
        report = self_repair(config)
        assert report["healthy"] is True
        assert len(report["suggestions"]) == 0

    def test_skipped_when_disabled(self):
        config = GuardianConfig(self_repair_enabled=False, providers=[])
        report = self_repair(config)
        assert report.get("skipped") is True

    def test_unhealthy_generates_suggestions(self):
        config = GuardianConfig(
            self_repair_enabled=True,
            providers=[
                Provider(name="X", endpoint="http://x", model="m", priority=1, enabled=False),
            ],
        )
        report = self_repair(config)
        assert report["healthy"] is False
        assert len(report["suggestions"]) > 0
