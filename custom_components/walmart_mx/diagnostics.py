"""Diagnóstico descargable desde la UI (para reportar problemas)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import WalmartConfigEntry


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: WalmartConfigEntry) -> dict[str, Any]:
    c = entry.runtime_data
    return {
        "options": dict(entry.options),
        "last_update_success": c.last_update_success,
        "last_check": c.last_check.isoformat() if c.last_check else None,
        "pause_remaining_seconds": round(c.throttle.pause_remaining),
        "product": asdict(c.data) if c.data else None,
        "history": c.history.as_dict(),
    }
