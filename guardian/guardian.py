"""
Uncensored Guardian - A self-repairing agent framework.

This module provides:
- Configuration-driven provider selection for uncensored model endpoints.
- A placeholder sub-agent spawning mechanism.
- Self-repair logic that reads its own source and suggests fixes on failure.
"""

import json
import inspect
import logging
import os
import sys
import difflib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config.json"


@dataclass
class Provider:
    name: str
    endpoint: str
    model: str
    priority: int = 1
    enabled: bool = True


@dataclass
class GuardianConfig:
    providers: list = field(default_factory=list)
    self_repair_enabled: bool = True
    max_repair_attempts: int = 3
    health_check_interval_seconds: int = 60
    log_level: str = "INFO"
    max_concurrent_agents: int = 5
    default_agent_timeout: int = 120


def load_config(config_path: Optional[Path] = None) -> GuardianConfig:
    """Load and parse the guardian configuration file."""
    path = config_path or CONFIG_PATH
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(path, "r") as f:
        raw = json.load(f)

    providers = [
        Provider(**p) for p in raw.get("providers", [])
    ]
    guardian_section = raw.get("guardian", {})
    agents_section = raw.get("sub_agents", {})

    return GuardianConfig(
        providers=providers,
        self_repair_enabled=guardian_section.get("self_repair_enabled", True),
        max_repair_attempts=guardian_section.get("max_repair_attempts", 3),
        health_check_interval_seconds=guardian_section.get("health_check_interval_seconds", 60),
        log_level=guardian_section.get("log_level", "INFO"),
        max_concurrent_agents=agents_section.get("max_concurrent", 5),
        default_agent_timeout=agents_section.get("default_timeout_seconds", 120),
    )


def get_active_providers(config: GuardianConfig) -> list:
    """Return enabled providers sorted by priority."""
    active = [p for p in config.providers if p.enabled]
    return sorted(active, key=lambda p: p.priority)


# ---------------------------------------------------------------------------
# Sub-Agent Spawning (Placeholder)
# ---------------------------------------------------------------------------

@dataclass
class SubAgentResult:
    agent_name: str
    task: str
    status: str  # "pending", "running", "completed", "failed"
    output: Optional[str] = None


def spawn_agent(
    task: str,
    name: str = "sub-agent",
    provider: Optional[Provider] = None,
    timeout: int = 120,
    run_in_background: bool = True,
) -> SubAgentResult:
    """
    Spawn a sub-agent to perform a task.

    This is a placeholder that simulates agent spawning. In production,
    this would make API calls to the configured uncensored model provider.

    Args:
        task: Description of what the agent should accomplish.
        name: Identifier for the sub-agent.
        provider: The model provider to use. If None, uses highest-priority.
        timeout: Max seconds to wait for completion.
        run_in_background: If True, returns immediately with pending status.

    Returns:
        SubAgentResult with the current status.
    """
    logger.info(f"Spawning sub-agent '{name}' with task: {task[:80]}...")

    if provider:
        logger.info(f"Using provider: {provider.name} ({provider.model})")

    # Placeholder: In a real implementation, this would:
    # 1. Select the best available provider
    # 2. Format the task as a prompt
    # 3. Send the request to the provider's API
    # 4. Return or poll for results

    status = "pending" if run_in_background else "completed"
    output = None if run_in_background else f"[PLACEHOLDER] Task '{task}' would be executed here."

    return SubAgentResult(
        agent_name=name,
        task=task,
        status=status,
        output=output,
    )


# ---------------------------------------------------------------------------
# Self-Repair Logic
# ---------------------------------------------------------------------------

@dataclass
class HealthCheckResult:
    passed: bool
    check_name: str
    message: str = ""


@dataclass
class RepairSuggestion:
    file_path: str
    original_lines: list
    suggested_lines: list
    reason: str
    diff: str = ""


def read_own_source(file_path: Optional[str] = None) -> str:
    """Read the source code of a given file (defaults to this module)."""
    target = file_path or __file__
    with open(target, "r") as f:
        return f.read()


def run_health_checks(config: GuardianConfig) -> list:
    """
    Run a series of health checks on the guardian system.

    Returns a list of HealthCheckResult objects.
    """
    results = []

    # Check 1: Config file exists and is valid
    try:
        load_config()
        results.append(HealthCheckResult(passed=True, check_name="config_valid"))
    except Exception as e:
        results.append(HealthCheckResult(
            passed=False, check_name="config_valid", message=str(e)
        ))

    # Check 2: At least one provider is enabled
    active = get_active_providers(config)
    if active:
        results.append(HealthCheckResult(
            passed=True, check_name="providers_available",
            message=f"{len(active)} provider(s) active"
        ))
    else:
        results.append(HealthCheckResult(
            passed=False, check_name="providers_available",
            message="No enabled providers found in config"
        ))

    # Check 3: Source file integrity (can we read ourselves?)
    try:
        source = read_own_source()
        if len(source) > 0:
            results.append(HealthCheckResult(
                passed=True, check_name="source_readable"
            ))
        else:
            results.append(HealthCheckResult(
                passed=False, check_name="source_readable",
                message="Source file is empty"
            ))
    except Exception as e:
        results.append(HealthCheckResult(
            passed=False, check_name="source_readable", message=str(e)
        ))

    # Check 4: Required functions exist
    required_functions = ["spawn_agent", "load_config", "self_repair"]
    for func_name in required_functions:
        if func_name in dir(sys.modules[__name__]):
            results.append(HealthCheckResult(
                passed=True, check_name=f"function_exists_{func_name}"
            ))
        else:
            results.append(HealthCheckResult(
                passed=False, check_name=f"function_exists_{func_name}",
                message=f"Function '{func_name}' not found in module"
            ))

    return results


def generate_repair_suggestion(
    check_result: HealthCheckResult,
    source_code: str,
    file_path: str,
) -> Optional[RepairSuggestion]:
    """
    Given a failed health check, analyze the source and suggest a repair.

    This is a rule-based repair engine. In production, you could send the
    source + error to an uncensored model for more sophisticated fixes.
    """
    if check_result.passed:
        return None

    lines = source_code.splitlines(keepends=True)

    if check_result.check_name == "providers_available":
        # Suggest enabling the first disabled provider
        for i, line in enumerate(lines):
            if '"enabled": false' in line.lower() or "'enabled': false" in line.lower():
                original = [lines[i]]
                suggested = [line.replace("false", "true").replace("False", "True")]
                diff = "".join(difflib.unified_diff(
                    original, suggested,
                    fromfile=file_path, tofile=file_path,
                    lineterm=""
                ))
                return RepairSuggestion(
                    file_path=file_path,
                    original_lines=original,
                    suggested_lines=suggested,
                    reason=f"No providers enabled. Suggesting re-enable at line {i+1}.",
                    diff=diff,
                )

        # If the issue is in config.json, suggest a config fix
        return RepairSuggestion(
            file_path=str(CONFIG_PATH),
            original_lines=['"enabled": false'],
            suggested_lines=['"enabled": true'],
            reason="No active providers. Enable at least one provider in config.json.",
            diff="",
        )

    if check_result.check_name == "config_valid":
        return RepairSuggestion(
            file_path=str(CONFIG_PATH),
            original_lines=[],
            suggested_lines=["Create a valid config.json with provider definitions."],
            reason=f"Config error: {check_result.message}",
            diff="",
        )

    return RepairSuggestion(
        file_path=file_path,
        original_lines=[],
        suggested_lines=[],
        reason=f"Check '{check_result.check_name}' failed: {check_result.message}. Manual review needed.",
        diff="",
    )


def self_repair(config: Optional[GuardianConfig] = None) -> dict:
    """
    Main self-repair entry point.

    1. Runs health checks.
    2. For any failures, reads source code and generates repair suggestions.
    3. Returns a report of findings and suggestions.

    Returns:
        Dictionary with 'healthy' bool, 'checks' list, and 'suggestions' list.
    """
    if config is None:
        config = load_config()

    if not config.self_repair_enabled:
        return {"healthy": True, "checks": [], "suggestions": [], "skipped": True}

    checks = run_health_checks(config)
    failed = [c for c in checks if not c.passed]
    suggestions = []

    if failed:
        source = read_own_source()
        for check in failed:
            suggestion = generate_repair_suggestion(check, source, __file__)
            if suggestion:
                suggestions.append(suggestion)

    return {
        "healthy": len(failed) == 0,
        "checks": checks,
        "suggestions": suggestions,
    }


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    """Run the guardian in CLI mode."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    logger.info("Loading configuration...")
    config = load_config()
    logger.info(f"Loaded {len(config.providers)} provider(s)")

    active = get_active_providers(config)
    logger.info(f"Active providers: {[p.name for p in active]}")

    logger.info("Running self-repair diagnostics...")
    report = self_repair(config)

    if report["healthy"]:
        logger.info("All health checks passed.")
    else:
        logger.warning(f"{len(report['suggestions'])} repair suggestion(s) generated:")
        for s in report["suggestions"]:
            logger.warning(f"  - {s.reason}")
            if s.diff:
                print(s.diff)

    # Demo: spawn a sub-agent
    logger.info("Spawning demo sub-agent...")
    result = spawn_agent(
        task="Analyze repository for security vulnerabilities",
        name="security-scanner",
        provider=active[0] if active else None,
    )
    logger.info(f"Sub-agent '{result.agent_name}' status: {result.status}")


if __name__ == "__main__":
    main()
