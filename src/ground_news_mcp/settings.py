"""Settings persistence for ground-news-mcp.

Settings are stored in ~/.ground-news-mcp/settings.json.
Users change settings by telling their assistant: "enable bias checking mode".
The model calls update_settings(), which persists to disk.
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SETTINGS_DIR = Path.home() / ".ground-news-mcp"
SETTINGS_FILE = SETTINGS_DIR / "settings.json"

PROFILES: dict[str, dict[str, Any]] = {
    "minimal": {
        "passive_context": False,
        "bias_checker": False,
        "missing_perspectives": False,
    },
    "balanced": {
        "passive_context": False,
        "bias_checker": False,
        "missing_perspectives": True,
    },
    "full": {
        "passive_context": True,
        "bias_checker": True,
        "missing_perspectives": True,
    },
}

DEFAULTS: dict[str, Any] = {
    "profile": "balanced",
    "passive_context": False,
    "bias_checker": False,
    "missing_perspectives": True,
}

VALID_KEYS = set(DEFAULTS.keys())


def _load_raw() -> dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}
    try:
        return json.loads(SETTINGS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not read settings file: %s", e)
        return {}


def get_settings() -> dict[str, Any]:
    """Return current settings merged with defaults."""
    raw = _load_raw()
    return {**DEFAULTS, **raw}


def update_settings(key: str, value: Any) -> dict[str, Any]:
    """Persist a single setting. Applying a profile sets all its keys.

    Returns the full updated settings dict.
    """
    if key not in VALID_KEYS:
        raise ValueError(f"Unknown setting '{key}'. Valid keys: {sorted(VALID_KEYS)}")

    current = _load_raw()

    if key == "profile":
        if value not in PROFILES:
            raise ValueError(
                f"Unknown profile '{value}'. Valid profiles: {sorted(PROFILES)}"
            )
        current.update(PROFILES[value])
        current["profile"] = value
    else:
        if not isinstance(value, bool):
            raise TypeError(
                f"Setting '{key}' must be a bool, got {type(value).__name__}"
            )
        current[key] = value
        # Mark as no-longer-matching-a-named-profile by removing the marker
        # rather than writing a sentinel value. Avoids the persisted-bad-state
        # bug where re-applying any subsequent profile is required to recover.
        current.pop("profile", None)

    SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(current, indent=2))
    logger.info("Settings updated: %s = %r", key, value)

    return get_settings()
