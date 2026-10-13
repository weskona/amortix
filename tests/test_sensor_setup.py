"""Smoke-Test: Sensor-Aufbau je Modus (eindeutige IDs, Werte berechenbar)."""
import asyncio
from unittest.mock import MagicMock

import pytest

from custom_components.amortix import const as c
from custom_components.amortix import sensor
from custom_components.amortix.coordinator import OverviewManager, PlantManager
from tests.test_managers import make
from tests.test_plant import PLANT_CFG, STATES


def build(mode, cls, cfg, states):
    manager = make(cls, {**cfg, "mode": mode}, states)
    manager.entry.entry_id = "x"
    hass = MagicMock()
    hass.data = {c.DOMAIN: {"x": manager}}
    added = []
    asyncio.run(sensor.async_setup_entry(hass, manager.entry, lambda ents: added.extend(ents)))
    return added


@pytest.mark.parametrize(
    "mode,cls,cfg,states,expected",
    [
        (c.MODE_PLANT, PlantManager, PLANT_CFG, STATES, 37),
        (c.MODE_OVERVIEW, OverviewManager, {}, {}, 7),
    ],
)
def test_sensors_have_unique_ids_and_values(mode, cls, cfg, states, expected):
    entities = build(mode, cls, cfg, states)
    ids = [e._attr_unique_id for e in entities]
    assert len(ids) == len(set(ids))
    assert len(entities) == expected
    for entity in entities:
        entity.native_value  # darf nicht werfen


def test_plant_creates_a_sensor_set_per_device():
    names = [e._attr_name for e in build(c.MODE_PLANT, PlantManager, PLANT_CFG, STATES)]
    for device in ("Grosse PV", "BKW 1", "BKW 2", "DC-Speicher"):
        assert f"Amortisation Fortschritt {device}" in names
        assert f"Einsparung {device}" in names
