"""Einheiten-Prüfung für die Einrichtung (ohne Home-Assistant-Importe, daher testbar)."""
from __future__ import annotations

from typing import Any


def non_kwh_entity(hass, user_input: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    """Erste gewählte Entität, deren Einheit nicht kWh ist.

    Der Entity-Picker kann in Home Assistant 2024.4 nur nach device_class filtern,
    nicht nach Einheit. Wh/MWh würden um den Faktor 1000 falsch rechnen, deshalb
    wird die Einheit nach der Auswahl geprüft. Eine (noch) unbekannte Einheit, etwa
    bei einem gerade nicht verfügbaren Sensor, gilt als ok.
    """
    for key in keys:
        value = user_input.get(key)
        if not value:
            continue
        for entity_id in value if isinstance(value, list) else [value]:
            state = hass.states.get(entity_id)
            unit = state.attributes.get("unit_of_measurement") if state else None
            if unit is not None and unit.strip().lower() != "kwh":
                return entity_id
    return None
