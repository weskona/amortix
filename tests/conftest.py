"""Stubs fuer homeassistant, damit die reine Berechnungslogik ohne HA testbar ist."""
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _module(name: str, **attrs) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__dict__.update(attrs)
    sys.modules[name] = mod
    return mod


if "homeassistant" not in sys.modules:
    _module("homeassistant")
    _module("homeassistant.config_entries", ConfigEntry=object)
    _module(
        "homeassistant.core",
        CALLBACK_TYPE=object,
        Event=object,
        HomeAssistant=object,
        State=object,
        callback=lambda f: f,
    )
    _module("homeassistant.helpers")
    _module(
        "homeassistant.helpers.event",
        async_track_state_change_event=MagicMock(),
        async_track_time_interval=MagicMock(),
    )
    _module("homeassistant.helpers.storage", Store=MagicMock())
    _module("homeassistant.util")
    _module(
        "homeassistant.util.dt",
        utcnow=lambda: datetime.now(timezone.utc),
        parse_datetime=datetime.fromisoformat,
    )
    sys.modules["homeassistant.util"].dt = sys.modules["homeassistant.util.dt"]
