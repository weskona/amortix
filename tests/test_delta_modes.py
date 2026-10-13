"""Tests fuer die Modi Wallbox/Allgemein, Waermepumpe und PV+Speicher."""
import pytest

from custom_components.amortix import const as c
from custom_components.amortix.coordinator import (
    CombinedManager,
    GenericManager,
    HeatPumpManager,
)
from tests.test_managers import make, restart, start

GENERIC_CFG = {
    c.CONF_ENERGY_SENSOR: "sensor.energy",
    c.CONF_INVESTMENT_ENTITY: "input_number.inv",
    c.CONF_REFERENCE_PRICE_ENTITY: "input_number.ref",
    c.CONF_OWN_PRICE_ENTITY: "input_number.own",
}
GENERIC_STATES = {"input_number.inv": 1000, "input_number.ref": 0.50, "input_number.own": 0.10}

HEAT_CFG = {
    c.CONF_HEAT_SENSOR: "sensor.heat",
    c.CONF_ELECTRIC_SENSOR: "sensor.elec",
    c.CONF_INVESTMENT_ENTITY: "input_number.inv",
    c.CONF_PRICE_ENTITY: "input_number.price",
    c.CONF_REFERENCE_PRICE_ENTITY: "input_number.ref",
}
HEAT_STATES = {"input_number.inv": 10000, "input_number.price": 0.30, "input_number.ref": 0.10}

COMBINED_CFG = {
    c.CONF_PRODUCTION_SENSOR: ["sensor.prod"],
    c.CONF_TO_GRID_SENSOR: "sensor.grid",
    c.CONF_CHARGE_SENSOR: "sensor.chg",
    c.CONF_DISCHARGE_SENSOR: "sensor.dis",
    c.CONF_INVESTMENT_ENTITY: "input_number.inv",
    c.CONF_PRICE_ENTITY: "input_number.price",
    c.CONF_FEED_IN_ENTITY: "input_number.feed",
}
COMBINED_STATES = {"input_number.inv": 15000, "input_number.price": 0.30, "input_number.feed": 0.08}


def feed_counters(m, key, value):
    next(iter(m.groups[key].values())).total = value


# ---------------------------------------------------------------- Allgemein
def test_generic_savings_is_kwh_times_price_difference():
    m = make(GenericManager, GENERIC_CFG, dict(GENERIC_STATES))
    feed_counters(m, "energy", 10.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(10 * (0.50 - 0.10))


def test_generic_without_own_price_uses_zero():
    cfg = {k: v for k, v in GENERIC_CFG.items() if k != c.CONF_OWN_PRICE_ENTITY}
    m = make(GenericManager, cfg, dict(GENERIC_STATES))
    feed_counters(m, "energy", 10.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(5.0)


def test_generic_is_incremental_and_uses_current_price():
    states = dict(GENERIC_STATES)
    m = make(GenericManager, GENERIC_CFG, states)
    feed_counters(m, "energy", 10.0)
    m._async_evaluate()
    m._async_evaluate()
    assert m.total_savings == pytest.approx(4.0)
    states["input_number.ref"] = 0.60
    feed_counters(m, "energy", 20.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(4.0 + 10 * (0.60 - 0.10))


def test_generic_cent_reference_price_is_converted():
    states = {**GENERIC_STATES, "input_number.ref": 50}
    m = make(GenericManager, GENERIC_CFG, states, units={"input_number.ref": "ct/kWh"})
    feed_counters(m, "energy", 10.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(4.0)


def test_generic_without_reference_price_does_not_evaluate():
    states = {k: v for k, v in GENERIC_STATES.items() if k != "input_number.ref"}
    m = make(GenericManager, GENERIC_CFG, states)
    feed_counters(m, "energy", 10.0)
    m._async_evaluate()
    assert m.total_savings == 0.0


def test_generic_dynamic_price_last_value_is_kept_when_unavailable():
    states = dict(GENERIC_STATES)
    m = make(GenericManager, GENERIC_CFG, states)
    feed_counters(m, "energy", 10.0)
    m._async_evaluate()
    del states["input_number.ref"]                 # Sensor faellt aus
    feed_counters(m, "energy", 20.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(8.0)   # letzter Preis gilt weiter


# ---------------------------------------------------------------- Waermepumpe
def test_heatpump_savings_and_cop():
    m = make(HeatPumpManager, HEAT_CFG, dict(HEAT_STATES))
    feed_counters(m, "heat", 100.0)
    feed_counters(m, "electric", 25.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(100 * 0.10 - 25 * 0.30)
    assert m.parts["heat"] == pytest.approx(10.0)
    assert m.parts["electric"] == pytest.approx(-7.5)
    assert m.cop == pytest.approx(4.0)


def test_heatpump_cop_none_without_electricity():
    assert make(HeatPumpManager, HEAT_CFG, dict(HEAT_STATES)).cop is None


# ---------------------------------------------------------------- PV + Speicher
def test_combined_savings_formula():
    m = make(CombinedManager, COMBINED_CFG, dict(COMBINED_STATES))
    feed_counters(m, "production", 10.0)
    feed_counters(m, "export", 4.0)
    feed_counters(m, "charge", 3.0)
    feed_counters(m, "discharge", 2.5)
    m._async_evaluate()
    expected_self = (10 - 4 - 3 + 2.5) * 0.30
    expected_export = 4 * 0.08
    assert m.parts["self"] == pytest.approx(expected_self)
    assert m.parts["export"] == pytest.approx(expected_export)
    assert m.total_savings == pytest.approx(expected_self + expected_export)
    assert m.total_self_consumed == pytest.approx(6.0)
    assert m.roundtrip == pytest.approx(2.5 / 3.0 * 100)


def test_combined_grid_charging_arbitrage_is_valued():
    states = dict(COMBINED_STATES)
    states["input_number.price"] = 0.10            # Nachttarif: Netzladung
    m = make(CombinedManager, COMBINED_CFG, states)
    feed_counters(m, "charge", 10.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(-1.0)  # Ladung kostet
    states["input_number.price"] = 0.40            # Tagtarif: Entladung
    feed_counters(m, "discharge", 10.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(-1.0 + 4.0)


def test_combined_pv_charged_energy_is_valued_at_discharge_time():
    states = dict(COMBINED_STATES)
    m = make(CombinedManager, COMBINED_CFG, states)
    # tagsüber: 5 kWh erzeugt, vollständig in den Speicher geladen
    feed_counters(m, "production", 5.0)
    feed_counters(m, "charge", 5.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(0.0)
    states["input_number.price"] = 0.40            # abends teurer
    feed_counters(m, "discharge", 5.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(5 * 0.40)


def test_combined_result_is_independent_of_update_order():
    a = make(CombinedManager, COMBINED_CFG, dict(COMBINED_STATES))
    feed_counters(a, "production", 10.0)
    a._async_evaluate()                            # Einspeisung hinkt hinterher
    feed_counters(a, "export", 4.0)
    a._async_evaluate()

    b = make(CombinedManager, COMBINED_CFG, dict(COMBINED_STATES))
    feed_counters(b, "production", 10.0)
    feed_counters(b, "export", 4.0)
    b._async_evaluate()
    assert a.total_savings == pytest.approx(b.total_savings)


# ---------------------------------------------------------------- Startgutschrift
def test_auto_initial_credit_for_generic_uses_current_meter_value():
    cfg = {**GENERIC_CFG, c.CONF_INITIAL_AUTO: True, c.CONF_INITIAL_SAVINGS: 5}
    states = {**GENERIC_STATES, "sensor.energy": 200}
    m = make(GenericManager, cfg, states)
    start(m)
    assert not m.initial_pending
    assert m.initial_credit == pytest.approx(5 + 200 * 0.40)
    assert m.kwh("energy") == pytest.approx(200)


def test_initial_credit_deferred_until_meter_readable_for_combined():
    cfg = {**COMBINED_CFG, c.CONF_INITIAL_AUTO: True}
    m = make(CombinedManager, cfg, dict(COMBINED_STATES))
    start(m)
    assert m.initial_pending
    for key, value in (("production", 100.0), ("export", 40.0), ("charge", 30.0), ("discharge", 25.0)):
        next(iter(m.groups[key].values())).update(value)
    m._async_tick()
    assert not m.initial_pending
    expected = (100 - 40 - 30 + 25) * 0.30 + 40 * 0.08
    assert m.initial_credit == pytest.approx(expected)


def test_flat_initial_credit_only():
    cfg = {**HEAT_CFG, c.CONF_INITIAL_SAVINGS: 250}
    m = make(HeatPumpManager, cfg, dict(HEAT_STATES))
    start(m)
    assert m.initial_credit == pytest.approx(250)
    assert m.total_savings == pytest.approx(250)


# ---------------------------------------------------------------- Persistenz
def test_delta_state_survives_restart():
    states = {**COMBINED_STATES, "sensor.prod": 0, "sensor.grid": 0, "sensor.chg": 0, "sensor.dis": 0}
    m = make(CombinedManager, COMBINED_CFG, states)
    start(m)
    feed_counters(m, "production", 10.0)
    feed_counters(m, "export", 4.0)
    m._async_evaluate()
    saved = m._data_to_save()

    again = restart(CombinedManager, COMBINED_CFG, states, saved)
    assert again.total_savings == pytest.approx(m.total_savings)
    assert again.parts == pytest.approx(m.parts)
    assert again.total("production") == pytest.approx(10.0)
    again._async_evaluate()                         # nichts wird doppelt gebucht
    assert again.total_savings == pytest.approx(m.total_savings)
