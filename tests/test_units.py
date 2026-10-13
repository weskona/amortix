"""Einheiten-Pruefung der Energie-Sensoren bei der Einrichtung."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.amortix.units import non_kwh_entity

KEYS = ("production_sensor", "to_grid_sensor")


def hass_with(units):
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(attributes={"unit_of_measurement": units[eid]}) if eid in units else None
    )
    return hass


def test_kwh_sensors_are_accepted():
    hass = hass_with({"sensor.a": "kWh", "sensor.b": "kWh"})
    assert non_kwh_entity(hass, {"production_sensor": ["sensor.a"], "to_grid_sensor": "sensor.b"}, KEYS) is None


@pytest.mark.parametrize("unit", ["Wh", "MWh", "W", "kW", "J"])
def test_other_units_are_rejected(unit):
    hass = hass_with({"sensor.a": "kWh", "sensor.b": unit})
    result = non_kwh_entity(hass, {"production_sensor": ["sensor.a", "sensor.b"]}, KEYS)
    assert result == "sensor.b"


def test_single_value_field_is_checked():
    hass = hass_with({"sensor.g": "Wh"})
    assert non_kwh_entity(hass, {"to_grid_sensor": "sensor.g"}, KEYS) == "sensor.g"


def test_unit_check_is_case_insensitive_and_trims():
    hass = hass_with({"sensor.a": " KWH "})
    assert non_kwh_entity(hass, {"production_sensor": ["sensor.a"]}, KEYS) is None


def test_unknown_unit_or_missing_state_is_accepted():
    hass = hass_with({"sensor.a": None})
    data = {"production_sensor": ["sensor.a", "sensor.gone"]}
    assert non_kwh_entity(hass, data, KEYS) is None


def test_empty_fields_are_ignored():
    assert non_kwh_entity(hass_with({}), {}, KEYS) is None
