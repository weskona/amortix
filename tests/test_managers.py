"""Tests fuer die Bewertungslogik von DirectManager und StorageManager."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.amortix import const as c
from custom_components.amortix.coordinator import DirectManager, StorageManager


def make(manager_cls, data, states):
    hass = MagicMock()
    hass.states.get.side_effect = lambda eid: (
        SimpleNamespace(state=str(states[eid])) if eid in states else None
    )
    entry = SimpleNamespace(entry_id="e1", title="Test", data=data, options={})
    return manager_cls(hass, entry)


DIRECT_CFG = {
    c.CONF_PRODUCTION_SENSOR: ["sensor.prod"],
    c.CONF_TO_GRID_SENSOR: "sensor.grid",
    c.CONF_INVESTMENT_ENTITY: "input_number.inv",
    c.CONF_PRICE_ENTITY: "input_number.price",
    c.CONF_FEED_IN_ENTITY: "input_number.feed",
}
STORAGE_CFG = {
    c.CONF_CHARGE_SENSOR: "sensor.chg",
    c.CONF_DISCHARGE_SENSOR: "sensor.dis",
    c.CONF_INVESTMENT_ENTITY: "input_number.inv",
    c.CONF_PRICE_ENTITY: "input_number.price",
    c.CONF_FEED_IN_ENTITY: "input_number.feed",
}
RATES = {"input_number.inv": 1000, "input_number.price": 0.30, "input_number.feed": 0.08}


def test_direct_self_consumption_and_export_are_valued_separately():
    m = make(DirectManager, DIRECT_CFG, RATES)
    m.prod_counters["sensor.prod"].total = 10.0
    m.grid.total = 4.0
    m._async_evaluate()
    assert m.savings_self == pytest.approx(6.0 * 0.30)
    assert m.savings_export == pytest.approx(4.0 * 0.08)
    assert m.total_savings == pytest.approx(6.0 * 0.30 + 4.0 * 0.08)


def test_direct_evaluation_is_incremental_and_idempotent():
    m = make(DirectManager, DIRECT_CFG, RATES)
    m.prod_counters["sensor.prod"].total = 10.0
    m._async_evaluate()
    first = m.total_savings
    m._async_evaluate()
    assert m.total_savings == pytest.approx(first)
    m.prod_counters["sensor.prod"].total = 12.0
    m._async_evaluate()
    assert m.total_savings == pytest.approx(first + 2.0 * 0.30)


def test_direct_uses_price_at_time_of_evaluation():
    states = dict(RATES)
    m = make(DirectManager, DIRECT_CFG, states)
    m.prod_counters["sensor.prod"].total = 1.0
    m._async_evaluate()
    states["input_number.price"] = 0.50
    m.prod_counters["sensor.prod"].total = 2.0
    m._async_evaluate()
    assert m.total_savings == pytest.approx(0.30 + 0.50)


def test_direct_lagging_grid_sensor_nets_out_eventually():
    m = make(DirectManager, DIRECT_CFG, RATES)
    prod = m.prod_counters["sensor.prod"]
    prod.total = 5.0            # Erzeugung aktualisiert, Einspeisung hinkt
    m._async_evaluate()
    m.grid.total = 5.0          # Einspeisung holt auf
    m._async_evaluate()
    assert m.credited_self == pytest.approx(5.0)       # Maximum bleibt stehen
    assert m.credited_grid == pytest.approx(5.0)
    prod.total = 8.0
    m._async_evaluate()
    # erst wenn raw_self (8-5=3) das alte Maximum (5) ueberschreitet, gibt es wieder Eigenverbrauch
    assert m.credited_self == pytest.approx(5.0)


def test_direct_no_price_means_no_evaluation():
    m = make(DirectManager, DIRECT_CFG, {"input_number.inv": 1000})
    m.prod_counters["sensor.prod"].total = 10.0
    m._async_evaluate()
    assert m.total_savings == 0.0


def test_direct_manual_initial_credit():
    cfg = {**DIRECT_CFG, c.CONF_INITIAL_SELF_KWH: 100, c.CONF_INITIAL_EXPORT_KWH: 50, c.CONF_INITIAL_SAVINGS: 5}
    m = make(DirectManager, cfg, RATES)
    credit = m._compute_initial_credit()
    assert credit == pytest.approx(5 + 100 * 0.30 + 50 * 0.08)
    assert m.total_self_consumed == pytest.approx(100)
    assert m.total_fed_in == pytest.approx(50)


def test_direct_auto_initial_credit_from_raw_values():
    cfg = {**DIRECT_CFG, c.CONF_INITIAL_AUTO: True}
    m = make(DirectManager, cfg, RATES)
    m.prod_counters["sensor.prod"].raw_last = 200.0
    m.grid.raw_last = 50.0
    assert m._compute_initial_credit() == pytest.approx(150 * 0.30 + 50 * 0.08)


def test_storage_savings_discharge_minus_forgone_feed_in():
    m = make(StorageManager, STORAGE_CFG, RATES)
    m.discharge.total = 8.0
    m.charge.total = 10.0
    m._async_evaluate()
    assert m.total_savings == pytest.approx(8.0 * 0.30 - 10.0 * 0.08)


def test_storage_savings_can_go_negative_but_progress_is_clamped():
    m = make(StorageManager, STORAGE_CFG, RATES)
    m.charge.total = 10.0
    m._async_evaluate()
    assert m.total_savings < 0
    assert m.progress == 0.0


def test_roundtrip_from_counters():
    m = make(StorageManager, STORAGE_CFG, RATES)
    m.charge.total = 10.0
    m.discharge.total = 8.5
    assert m.roundtrip == pytest.approx(85.0)


def test_roundtrip_none_without_charge():
    assert make(StorageManager, STORAGE_CFG, RATES).roundtrip is None


def test_remaining_and_progress():
    m = make(DirectManager, DIRECT_CFG, RATES)
    m.total_savings = 250.0
    assert m.progress == pytest.approx(25.0)
    assert m.remaining == pytest.approx(750.0)
    m.total_savings = 5000.0
    assert m.progress == 100.0
    assert m.remaining == 0.0


def test_storage_initial_credit_matches_breakdown():
    cfg = {**STORAGE_CFG, c.CONF_INITIAL_DISCHARGE_KWH: 10, c.CONF_INITIAL_CHARGE_KWH: 100}
    m = make(StorageManager, cfg, RATES)
    credit = m._compute_initial_credit()
    parts = m.credit_breakdown
    assert credit == pytest.approx(
        parts["entladung_eur"] + parts["entgangene_einspeisung_eur"] + parts["pauschal_eur"]
    )


# ----------------------------------------------------------------------
# Startgutschrift wartet auf nicht verfuegbare Sensoren/Preise
# ----------------------------------------------------------------------
def start(manager):
    import asyncio
    from unittest.mock import AsyncMock

    manager.store.async_load = AsyncMock(return_value=None)
    asyncio.run(manager.async_start())


@pytest.fixture(autouse=True)
def _no_ha_tracking(monkeypatch):
    from custom_components.amortix import coordinator

    monkeypatch.setattr(coordinator, "async_track_state_change_event", MagicMock())
    monkeypatch.setattr(coordinator, "async_track_time_interval", MagicMock())


def test_auto_credit_is_deferred_while_sensor_unavailable():
    cfg = {**DIRECT_CFG, c.CONF_INITIAL_AUTO: True}
    states = dict(RATES)                      # Zaehler unavailable (nicht in states)
    m = make(DirectManager, cfg, states)
    start(m)
    assert m.initial_pending
    assert m.total_savings == 0.0

    # Sensoren werden lesbar: erster Wert seeded, danach Zuwachs
    m.prod_counters["sensor.prod"].update(200.0)
    m.grid.update(50.0)
    m.prod_counters["sensor.prod"].update(201.0)
    m._async_tick()
    assert not m.initial_pending
    assert m.initial_credit == pytest.approx(150 * 0.30 + 50 * 0.08)
    # Zuwachs nach dem Seed ist nicht Teil der Startgutschrift, sondern normale Ersparnis
    assert m.total_savings == pytest.approx(m.initial_credit + 1.0 * 0.30)


def test_credit_is_deferred_while_price_unavailable():
    cfg = {**DIRECT_CFG, c.CONF_INITIAL_SELF_KWH: 100}
    states = {"input_number.inv": 1000, "input_number.feed": 0.08}  # kein Preis
    m = make(DirectManager, cfg, states)
    start(m)
    assert m.initial_pending
    states["input_number.price"] = 0.30
    m._async_tick()
    assert not m.initial_pending
    assert m.initial_credit == pytest.approx(100 * 0.30)


def test_credit_applied_immediately_when_everything_available():
    cfg = {**DIRECT_CFG, c.CONF_INITIAL_AUTO: True}
    states = {**RATES, "sensor.prod": 200, "sensor.grid": 50}
    m = make(DirectManager, cfg, states)
    start(m)
    assert not m.initial_pending
    assert m.initial_credit == pytest.approx(150 * 0.30 + 50 * 0.08)


def test_storage_auto_credit_deferred_until_both_sensors_seeded():
    cfg = {**STORAGE_CFG, c.CONF_INITIAL_AUTO: True}
    m = make(StorageManager, cfg, dict(RATES))
    start(m)
    assert m.initial_pending
    m.discharge.update(100.0)
    m._async_tick()
    assert m.initial_pending                  # Ladezaehler fehlt noch
    m.charge.update(120.0)
    m._async_tick()
    assert not m.initial_pending
    assert m.initial_credit == pytest.approx(100 * 0.30 - 120 * 0.08)


def test_pending_flag_is_persisted():
    m = make(DirectManager, {**DIRECT_CFG, c.CONF_INITIAL_AUTO: True}, dict(RATES))
    start(m)
    assert m._data_to_save()["initial_pending"] is True


def restart(manager_cls, cfg, states, saved):
    """Neuen Manager mit dem gespeicherten Store-Inhalt starten (HA-Neustart)."""
    import asyncio
    from unittest.mock import AsyncMock

    m = make(manager_cls, cfg, states)
    m.store.async_load = AsyncMock(return_value=saved)
    asyncio.run(m.async_start())
    return m


def test_pending_credit_survives_restart_and_is_applied_once():
    cfg = {**DIRECT_CFG, c.CONF_INITIAL_AUTO: True}

    # 1. Erststart: Zaehler unavailable -> Gutschrift zurueckgestellt
    first = make(DirectManager, cfg, dict(RATES))
    start(first)
    assert first.initial_pending
    saved = first._data_to_save()

    # 2. Neustart, Sensoren jetzt verfuegbar: Gutschrift wird nachgeholt
    states = {**RATES, "sensor.prod": 200, "sensor.grid": 50}
    second = restart(DirectManager, cfg, states, saved)
    assert second.initial_pending                 # noch nicht angewendet
    second._async_tick()
    assert not second.initial_pending
    expected = 150 * 0.30 + 50 * 0.08
    assert second.initial_credit == pytest.approx(expected)
    assert second.total_savings == pytest.approx(expected)

    # 3. weiterer Neustart: Gutschrift wird nicht erneut berechnet/addiert
    third = restart(DirectManager, cfg, states, second._data_to_save())
    assert not third.initial_pending
    third._async_tick()
    assert third.initial_credit == pytest.approx(expected)
    assert third.total_savings == pytest.approx(expected)


def test_pending_storage_credit_survives_restart():
    cfg = {**STORAGE_CFG, c.CONF_INITIAL_AUTO: True}
    first = make(StorageManager, cfg, dict(RATES))
    start(first)
    saved = first._data_to_save()
    assert saved["initial_pending"] is True

    states = {**RATES, "sensor.chg": 120, "sensor.dis": 100}
    second = restart(StorageManager, cfg, states, saved)
    second._async_tick()
    assert not second.initial_pending
    assert second.initial_credit == pytest.approx(100 * 0.30 - 120 * 0.08)
