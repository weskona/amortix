"""Die Amortisations-Integration für Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_MODE,
    DOMAIN,
    MODE_COMBINED,
    MODE_DIRECT,
    MODE_GENERIC,
    MODE_HEATPUMP,
    MODE_OVERVIEW,
    MODE_STORAGE,
    MODE_PLANT,
    MODE_WALLBOX,
    PLATFORMS,
    SIGNAL_MANAGERS_CHANGED,
)
from .coordinator import (
    CombinedManager,
    DirectManager,
    GenericManager,
    HeatPumpManager,
    OverviewManager,
    StorageManager,
    PlantManager,
)

MANAGERS = {
    MODE_DIRECT: DirectManager,
    MODE_STORAGE: StorageManager,
    MODE_COMBINED: CombinedManager,
    MODE_WALLBOX: GenericManager,
    MODE_GENERIC: GenericManager,
    MODE_HEATPUMP: HeatPumpManager,
    MODE_PLANT: PlantManager,
    MODE_OVERVIEW: OverviewManager,
}


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Alte Einträge auf das aktuelle Schema heben."""
    if entry.version > 4:
        return False  # Downgrade nicht unterstützt
    if entry.version < 4:
        new_data = {**entry.data}
        # Einträge vor dem Speicher-Modus sind immer Direktverbrauch
        new_data.setdefault(CONF_MODE, MODE_DIRECT)
        hass.config_entries.async_update_entry(entry, data=new_data, version=4)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    mode = entry.data.get(CONF_MODE, MODE_DIRECT)
    manager = MANAGERS.get(mode, DirectManager)(hass, entry)
    await manager.async_start()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = manager

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    async_dispatcher_send(hass, SIGNAL_MANAGERS_CHANGED)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        manager = hass.data[DOMAIN].pop(entry.entry_id, None)
        if manager is not None:
            manager.async_stop()
        async_dispatcher_send(hass, SIGNAL_MANAGERS_CHANGED)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
