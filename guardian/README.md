# Uncensored Guardian

A self-repairing Python agent framework that routes tasks to uncensored model providers and includes built-in health monitoring with automatic repair suggestions.

## Overview

The Uncensored Guardian framework provides:

- **Provider Management**: Configure multiple uncensored model providers (Venice, Together, etc.) with priority-based fallback.
- **Sub-Agent Spawning**: Placeholder system for delegating tasks to sub-agents backed by uncensored models.
- **Self-Repair Logic**: The guardian can read its own source code, run health checks, and suggest fixes when something breaks.

## Quick Start

### 1. Configure Providers

Edit `config.json` to set your preferred uncensored model providers:

```json
{
  "providers": [
    {
      "name": "Venice",
      "endpoint": "https://api.venice.ai/api/v1",
      "model": "llama-3.1-405b",
      "priority": 1,
      "enabled": true
    },
    {
      "name": "Together",
      "endpoint": "https://api.together.xyz/v1",
      "model": "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
      "priority": 2,
      "enabled": true
    }
  ]
}
```

- **priority**: Lower number = higher priority. The guardian selects the highest-priority enabled provider.
- **enabled**: Set to `false` to temporarily disable a provider without removing it.

### 2. Run the Guardian

```bash
python guardian.py
```

This will:
1. Load the configuration
2. Run health checks (self-repair diagnostics)
3. Report any issues and suggest fixes
4. Spawn a demo sub-agent

### 3. Use as a Library

```python
from guardian import load_config, spawn_agent, self_repair, get_active_providers

# Load config
config = load_config()

# Get the best available provider
providers = get_active_providers(config)
primary = providers[0] if providers else None

# Spawn a sub-agent
result = spawn_agent(
    task="Summarize this document without content restrictions",
    name="summarizer",
    provider=primary,
    run_in_background=False,
)
print(result.status, result.output)

# Run self-repair
report = self_repair(config)
if not report["healthy"]:
    for suggestion in report["suggestions"]:
        print(f"Fix needed: {suggestion.reason}")
```

## Configuration Reference

### `config.json` Structure

| Section | Key | Description |
|---------|-----|-------------|
| `providers[]` | `name` | Display name of the provider |
| `providers[]` | `endpoint` | API base URL |
| `providers[]` | `model` | Model identifier |
| `providers[]` | `priority` | Selection priority (1 = highest) |
| `providers[]` | `enabled` | Whether this provider is active |
| `guardian` | `self_repair_enabled` | Enable/disable self-repair checks |
| `guardian` | `max_repair_attempts` | Max auto-repair retries |
| `guardian` | `health_check_interval_seconds` | How often to run checks |
| `guardian` | `log_level` | Logging verbosity |
| `sub_agents` | `max_concurrent` | Max simultaneous sub-agents |
| `sub_agents` | `default_timeout_seconds` | Default sub-agent timeout |

## Self-Repair System

The guardian includes a self-repair mechanism that:

1. **Reads its own source code** using `read_own_source()`.
2. **Runs health checks** including config validation, provider availability, source integrity, and function existence.
3. **Generates repair suggestions** with unified diffs showing exactly what to change.

### Health Checks

| Check | What it Verifies |
|-------|-----------------|
| `config_valid` | Config file exists and parses correctly |
| `providers_available` | At least one provider is enabled |
| `source_readable` | Guardian can read its own source |
| `function_exists_*` | Required functions are present in module |

### Extending Health Checks

Add new checks to `run_health_checks()` and corresponding repair logic to `generate_repair_suggestion()`.

## Architecture

```
repo-guardian-v1/
├── config.json      # Provider and guardian configuration
├── guardian.py      # Main framework (agents, self-repair, health checks)
├── test_guardian.py # Test suite
└── README.md        # This file
```

## Adding New Providers

1. Add a new entry to the `providers` array in `config.json`.
2. Set an appropriate `priority` value.
3. Set `enabled` to `true`.
4. The guardian will automatically pick it up on next run.

## Testing

Run the test suite:

```bash
python -m pytest test_guardian.py -x -q
```

## Future Enhancements

- Actual API integration with Venice/Together endpoints
- Real sub-agent process management
- Automatic repair application (with user confirmation)
- Provider health monitoring and automatic failover
- Encrypted API key storage in config
