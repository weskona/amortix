"""Tests fuer die Anlage (mehrere Erzeuger/Speicher, Kosten je Geraet) und die Gesamtuebersicht."""
import pytest

from custom_components.amortix import const as c
from custom_components.amortix.coordinator import (
    DirectManager,
    GenericManager,
    OverviewManager,
    PlantManager,
)
from tests.test_managers import make, restart, start

PLANT_CFG = {
    c.CONF_PRODUCTION_SENSOR: ["sensor.pv", "sensor.bkw1", "sensor.bkw2"],
    c.CONF_TO_GRID_SENSOR: "sensor.grid",
    c.CONF_DEVICES: [
        {"sensor": "sensor.pv", "name": "Grosse PV", "investment_entity": "input_number.inv_pv"},
        {"sensor": "sensor.bkw1", "name": "BKW 1", "investment_entity": "input_number.inv_b1"},
        {"sensor": "sensor.bkw2", "name": "BKW 2", "investment_entity": "input_number.inv_b2"},
    ],
    c.CONF_STORAGES: [
        {
            "name": "DC-Speicher",
            "charge_sensor": "sensor.dc_c",
            "discharge_sensor": "sensor.dc_d",
            "investment_entity": "input_number.inv_dc",
        },
    ],
    c.CONF_PRICE_ENTITY: "input_number.price",
    c.CONF_FEED_IN_ENTITY: "input_number.feed",
}
STATES = {
    "input_number.price": 0.30,
    "input_number.feed": 0.08,
    "input_number.inv_pv": 8000,
    "input_number.inv_b1": 500,
    "input_number.inv_b2": 500,
    "input_number.inv_dc": 5000,
}


def put(m, key, value):
    next(iter(m.groups[key].values())).total = value


def fill(m, pv=0.0, b1=0.0, b2=0.0, export=0.0, chg=0.0, dis=0.0):
    put(m, "prod0", pv)
    put(m, "prod1", b1)
    put(m, "prod2", b2)
    put(m, "export", export)
    put(m, "chg0", chg)
    put(m, "dis0", dis)


def test_total_matches_single_formula_and_devices_sum_to_total():
    m = make(PlantManager, PLANT_CFG, dict(STATES))
    fill(m, pv=80, b1=10, b2=10, export=30, chg=20, dis=16)
    m._async_evaluate()
    expected = (100 - 30 - 20 + 16) * 0.30 + 30 * 0.08
    assert m.total_savings == pytest.approx(expected)
    assert sum(m.dev_savings.values()) == pytest.approx(m.total_savings)
    assert m.parts["self"] + m.parts["export"] == pytest.approx(m.total_savings)


def test_producers_share_pool_by_production():
    m = make(PlantManager, PLANT_CFG, dict(STATES))
    fill(m, pv=80, b1=10, b2=10, export=30, chg=20, dis=16)
    m._async_evaluate()
    pool = (100 - 30 - 20) * 0.30 + (30 + 20) * 0.08
    assert m.dev_savings["prod0"] == pytest.approx(pool * 0.8)
    assert m.dev_savings["prod1"] == pytest.approx(pool * 0.1)
    assert m.dev_savings["prod2"] == pytest.approx(pool * 0.1)


def test_storage_value_is_discharge_minus_forgone_feed_in():
    m = make(PlantManager, PLANT_CFG, dict(STATES))
    fill(m, pv=80, b1=10, b2=10, export=30, chg=20, dis=16)
    m._async_evaluate()
    assert m.dev_savings["sto0"] == pytest.approx(16 * 0.30 - 20 * 0.08)


def test_second_storage_for_ac_storage_is_supported():
    cfg = {
        **PLANT_CFG,
        c.CONF_STORAGES: PLANT_CFG[c.CONF_STORAGES]
        + [{"name": "AC-Speicher", "charge_sensor": "sensor.ac_c", "discharge_sensor": "sensor.ac_d"}],
    }
    m = make(PlantManager, cfg, dict(STATES))
    fill(m, pv=100, export=40, chg=10, dis=8)
    put(m, "chg1", 5.0)
    put(m, "dis1", 4.0)
    m._async_evaluate()
    assert m.total_savings == pytest.approx((100 - 40 - 15 + 12) * 0.30 + 40 * 0.08)
    assert m.dev_savings["sto1"] == pytest.approx(4 * 0.30 - 5 * 0.08)
    assert sum(m.dev_savings.values()) == pytest.approx(m.total_savings)
    assert m.kwh("charge") == pytest.approx(15)
    assert m.kwh("discharge") == pytest.approx(12)


def test_total_investment_is_sum_of_devices_and_each_device_has_progress():
    m = make(PlantManager, PLANT_CFG, dict(STATES))
    assert m.investment == pytest.approx(8000 + 500 + 500 + 5000)
    m.dev_savings["prod1"] = 250.0
    view = m.views["prod1"]
    assert view.investment == pytest.approx(500)
    assert view.progress == pytest.approx(50.0)
    assert view.remaining == pytest.approx(250.0)
    assert view.name == "BKW 1"


def test_device_without_investment_has_no_progress():
    cfg = {**PLANT_CFG, c.CONF_STORAGES: [{"name": "S", "charge_sensor": "sensor.dc_c", "discharge_sensor": "sensor.dc_d"}]}
    m = make(PlantManager, cfg, dict(STATES))
    assert m.views["sto0"].progress is None
    assert m.investment == pytest.approx(9000)


def test_grid_arbitrage_goes_to_the_storage():
    states = dict(STATES)
    states["input_number.price"] = 0.10
    m = make(PlantManager, PLANT_CFG, states)
    fill(m, chg=10)
    m._async_evaluate()
    states["input_number.price"] = 0.40
    fill(m, chg=10, dis=10)
    m._async_evaluate()
    assert m.total_savings == pytest.approx(-1.0 + 4.0)
    assert sum(m.dev_savings.values()) == pytest.approx(m.total_savings)


def test_export_arriving_before_production_nets_out():
    m = make(PlantManager, PLANT_CFG, dict(STATES))
    fill(m, export=4)
    m._async_evaluate()
    fill(m, pv=10, export=4)
    m._async_evaluate()
    ref = make(PlantManager, PLANT_CFG, dict(STATES))
    fill(ref, pv=10, export=4)
    ref._async_evaluate()
    assert m.total_savings == pytest.approx(ref.total_savings)


# ---------------------------------------------------------------- Startwerte
def test_per_device_starting_values_for_a_running_system():
    cfg = {
        **PLANT_CFG,
        c.CONF_DEVICES: [
            {**PLANT_CFG[c.CONF_DEVICES][0], "initial_savings": 1200},
            {**PLANT_CFG[c.CONF_DEVICES][1], "initial_savings": 80},
            PLANT_CFG[c.CONF_DEVICES][2],
        ],
        c.CONF_STORAGES: [{**PLANT_CFG[c.CONF_STORAGES][0], "initial_savings": 300}],
        c.CONF_INITIAL_SAVINGS: 10,
    }
    m = make(PlantManager, cfg, dict(STATES))
    start(m)
    assert not m.initial_pending
    assert m.initial_credit == pytest.approx(1200 + 80 + 300 + 10)
    assert m.total_savings == pytest.approx(1590)
    assert m.dev_savings["prod0"] == pytest.approx(1200)
    assert m.dev_initial["prod1"] == pytest.approx(80)
    assert m.views["sto0"].initial_credit == pytest.approx(300)
    # bisherige Ersparnis zaehlt zum Fortschritt, nicht zum Tagesschnitt
    assert m.views["prod0"].progress == pytest.approx(15.0)
    assert m.views["prod0"].daily_average is None


def test_auto_starting_credit_is_split_across_devices():
    cfg = {**PLANT_CFG, c.CONF_INITIAL_AUTO: True}
    states = {
        **STATES,
        "sensor.pv": 800, "sensor.bkw1": 100, "sensor.bkw2": 100,
        "sensor.grid": 300, "sensor.dc_c": 200, "sensor.dc_d": 160,
    }
    m = make(PlantManager, cfg, states)
    start(m)
    assert not m.initial_pending
    expected = (1000 - 300 - 200 + 160) * 0.30 + 300 * 0.08
    assert m.initial_credit == pytest.approx(expected)
    assert sum(m.dev_initial.values()) == pytest.approx(expected)
    assert m.kwh("production") == pytest.approx(1000)


def test_auto_starting_credit_deferred_until_all_meters_readable():
    cfg = {**PLANT_CFG, c.CONF_INITIAL_AUTO: True}
    m = make(PlantManager, cfg, dict(STATES))
    start(m)
    assert m.initial_pending
    for key, value in (("prod0", 800), ("prod1", 100), ("prod2", 100), ("export", 300), ("chg0", 200), ("dis0", 160)):
        next(iter(m.groups[key].values())).update(value)
    m._async_tick()
    assert not m.initial_pending
    assert sum(m.dev_initial.values()) == pytest.approx(m.initial_credit)


def test_plant_state_survives_restart_without_double_booking():
    states = {**STATES, "sensor.pv": 0, "sensor.bkw1": 0, "sensor.bkw2": 0, "sensor.grid": 0, "sensor.dc_c": 0, "sensor.dc_d": 0}
    m = make(PlantManager, PLANT_CFG, states)
    start(m)
    fill(m, pv=80, b1=10, b2=10, export=30, chg=20, dis=16)
    m._async_evaluate()
    again = restart(PlantManager, PLANT_CFG, states, m._data_to_save())
    assert again.total_savings == pytest.approx(m.total_savings)
    assert again.dev_savings == pytest.approx(m.dev_savings)
    again._async_evaluate()
    assert again.total_savings == pytest.approx(m.total_savings)


def test_breakdown_lists_devices_and_flat_credit():
    cfg = {**PLANT_CFG, c.CONF_INITIAL_SAVINGS: 50}
    m = make(PlantManager, cfg, dict(STATES))
    start(m)
    names = [line["name"] for line in m.breakdown()]
    assert names == ["Grosse PV", "BKW 1", "BKW 2", "DC-Speicher", "Pauschale Startgutschrift"]
    assert m.breakdown()[-1]["savings"] == pytest.approx(50)


# ---------------------------------------------------------------- Gesamtuebersicht
def test_overview_sums_all_other_entries_and_ignores_itself():
    plant = make(PlantManager, PLANT_CFG, dict(STATES))
    fill(plant, pv=80, b1=10, b2=10, export=30, chg=20, dis=16)
    plant._async_evaluate()
    wallbox = make(
        GenericManager,
        {
            c.CONF_ENERGY_SENSOR: "sensor.ev",
            c.CONF_INVESTMENT_ENTITY: "input_number.inv_ev",
            c.CONF_REFERENCE_PRICE_ENTITY: "input_number.ref",
            c.CONF_OWN_PRICE_ENTITY: "input_number.price",
        },
        {"input_number.inv_ev": 1500, "input_number.ref": 0.60, "input_number.price": 0.30},
    )
    next(iter(wallbox.groups["energy"].values())).total = 100
    wallbox._async_evaluate()

    over = make(OverviewManager, {}, {})
    over.entry.entry_id = "over"
    over.hass.data = {c.DOMAIN: {"p": plant, "w": wallbox, "over": over}}

    assert over.total_savings == pytest.approx(plant.total_savings + wallbox.total_savings)
    assert over.investment == pytest.approx(plant.investment + 1500)
    assert over.progress == pytest.approx(over.total_savings / over.investment * 100)
    lines = over.breakdown()
    assert [line["name"] for line in lines][:4] == ["Grosse PV", "BKW 1", "BKW 2", "DC-Speicher"]
    assert len(lines) == 5
    assert sum(line["savings"] for line in lines) == pytest.approx(over.total_savings, abs=0.02)
    assert over.attributes()["eintraege"] == 2


def test_overview_without_entries_is_empty():
    over = make(OverviewManager, {}, {})
    over.entry.entry_id = "over"
    over.hass.data = {c.DOMAIN: {"over": over}}
    assert over.total_savings == 0
    assert over.investment is None
    assert over.breakdown() == []


def test_overview_start_time_is_earliest_entry():
    a = make(DirectManager, {c.CONF_PRODUCTION_SENSOR: ["x"], c.CONF_TO_GRID_SENSOR: "y"}, {})
    b = make(DirectManager, {c.CONF_PRODUCTION_SENSOR: ["x"], c.CONF_TO_GRID_SENSOR: "y"}, {})
    a.start_time = "2026-06-01T00:00:00+00:00"
    b.start_time = "2026-03-01T00:00:00+00:00"
    over = make(OverviewManager, {}, {})
    over.entry.entry_id = "over"
    over.hass.data = {c.DOMAIN: {"a": a, "b": b, "over": over}}
    assert over.start_time == "2026-03-01T00:00:00+00:00"


# ---------------------------------------------------------------- Nachtraegliche Aenderungen
RUNNING = {**STATES, "sensor.pv": 0, "sensor.bkw1": 0, "sensor.bkw2": 0, "sensor.grid": 0, "sensor.dc_c": 0, "sensor.dc_d": 0}


def running_plant(cfg=None, states=None):
    m = make(PlantManager, cfg or PLANT_CFG, dict(states or RUNNING))
    start(m)
    fill(m, pv=80, b1=10, b2=10, export=30, chg=20, dis=16)
    m._async_evaluate()
    return m


def test_ac_storage_added_later_starts_counting_from_now_with_its_flat_value():
    before = running_plant()
    saved = before._data_to_save()
    cfg = {
        **PLANT_CFG,
        c.CONF_STORAGES: PLANT_CFG[c.CONF_STORAGES]
        + [{"name": "AC-Speicher", "charge_sensor": "sensor.ac_c", "discharge_sensor": "sensor.ac_d", "initial_savings": 200}],
    }
    states = {**RUNNING, "sensor.ac_c": 500, "sensor.ac_d": 450}   # Zaehler hat eigene Historie
    after = restart(PlantManager, cfg, states, saved)

    assert after.total_savings == pytest.approx(before.total_savings + 200)
    assert after.dev_savings["sto1"] == pytest.approx(200)
    assert after.views["sto1"].initial_credit == pytest.approx(200)
    assert after.dev_savings["prod0"] == pytest.approx(before.dev_savings["prod0"])   # bestehende Geraete unveraendert
    after._async_evaluate()                      # Historie des neuen Zaehlers wird nicht nachgebucht
    assert after.total_savings == pytest.approx(before.total_savings + 200)
    # ab jetzt zaehlt der neue Speicher
    put(after, "chg1", 10.0)
    put(after, "dis1", 8.0)
    after._async_evaluate()
    assert after.dev_savings["sto1"] == pytest.approx(200 + 8 * 0.30 - 10 * 0.08)


def test_changed_flat_value_books_only_the_difference_once():
    before = running_plant(
        {**PLANT_CFG, c.CONF_DEVICES: [{**PLANT_CFG[c.CONF_DEVICES][0], "initial_savings": 1000}, *PLANT_CFG[c.CONF_DEVICES][1:]]}
    )
    start_total = before.total_savings
    cfg = {**PLANT_CFG, c.CONF_DEVICES: [{**PLANT_CFG[c.CONF_DEVICES][0], "initial_savings": 1500}, *PLANT_CFG[c.CONF_DEVICES][1:]]}
    again = restart(PlantManager, cfg, RUNNING, before._data_to_save())
    assert again.total_savings == pytest.approx(start_total + 500)
    assert again.dev_initial["prod0"] == pytest.approx(before.dev_initial["prod0"] + 500)
    third = restart(PlantManager, cfg, RUNNING, again._data_to_save())
    assert third.total_savings == pytest.approx(again.total_savings)      # nicht erneut gebucht


def test_flat_value_lowered_reduces_savings():
    cfg_hi = {**PLANT_CFG, c.CONF_DEVICES: [{**PLANT_CFG[c.CONF_DEVICES][0], "initial_savings": 1000}, *PLANT_CFG[c.CONF_DEVICES][1:]]}
    before = running_plant(cfg_hi)
    cfg_lo = {**PLANT_CFG, c.CONF_DEVICES: [{**PLANT_CFG[c.CONF_DEVICES][0], "initial_savings": 400}, *PLANT_CFG[c.CONF_DEVICES][1:]]}
    again = restart(PlantManager, cfg_lo, RUNNING, before._data_to_save())
    assert again.total_savings == pytest.approx(before.total_savings - 600)


def test_existing_entries_without_applied_flat_do_not_double_book():
    cfg = {**PLANT_CFG, c.CONF_DEVICES: [{**PLANT_CFG[c.CONF_DEVICES][0], "initial_savings": 1000}, *PLANT_CFG[c.CONF_DEVICES][1:]]}
    before = running_plant(cfg)
    saved = before._data_to_save()
    saved.pop("applied_flat")                      # Stand vor dieser Funktion
    again = restart(PlantManager, cfg, RUNNING, saved)
    assert again.total_savings == pytest.approx(before.total_savings)


def test_replaced_sensor_keeps_history_and_counts_on_from_the_new_meter():
    before = running_plant()
    saved = before._data_to_save()
    devices = [{**PLANT_CFG[c.CONF_DEVICES][0], "sensor": "sensor.pv_new"}, *PLANT_CFG[c.CONF_DEVICES][1:]]
    cfg = {**PLANT_CFG, c.CONF_DEVICES: devices, c.CONF_PRODUCTION_SENSOR: ["sensor.pv_new", "sensor.bkw1", "sensor.bkw2"]}
    states = {**RUNNING, "sensor.pv_new": 3}       # neuer Wechselrichter, Zaehler bei 3 kWh
    after = restart(PlantManager, cfg, states, saved)
    assert after.total("prod0") == pytest.approx(before.total("prod0"))
    after._async_evaluate()
    assert after.total_savings == pytest.approx(before.total_savings)      # nichts doppelt
    next(iter(after.groups["prod0"].values())).update(8)                   # +5 kWh neuer Zaehler
    after._async_evaluate()
    assert after.total_savings > before.total_savings


def test_replaced_export_sensor_keeps_history():
    before = running_plant()
    cfg = {**PLANT_CFG, c.CONF_TO_GRID_SENSOR: "sensor.grid_new"}
    after = restart(PlantManager, cfg, {**RUNNING, "sensor.grid_new": 12}, before._data_to_save())
    assert after.total("export") == pytest.approx(before.total("export"))
    after._async_evaluate()
    assert after.total_savings == pytest.approx(before.total_savings)


def test_pending_credit_with_device_flat_values_is_booked_once_after_restart():
    cfg = {
        **PLANT_CFG,
        c.CONF_INITIAL_AUTO: True,
        c.CONF_DEVICES: [
            {**PLANT_CFG[c.CONF_DEVICES][0], "initial_savings": 100},
            *PLANT_CFG[c.CONF_DEVICES][1:],
        ],
    }
    first = make(PlantManager, cfg, dict(STATES))
    start(first)
    assert first.initial_pending
    saved = first._data_to_save()

    readable = {
        **STATES,
        "sensor.pv": 800, "sensor.bkw1": 100, "sensor.bkw2": 100,
        "sensor.grid": 300, "sensor.dc_c": 200, "sensor.dc_d": 160,
    }
    second = restart(PlantManager, cfg, readable, saved)
    assert second.total_savings == 0.0            # Startwerte warten auf die Gutschrift
    second._async_tick()
    assert not second.initial_pending
    assert second.total_savings == pytest.approx(second.initial_credit)
    assert sum(second.dev_savings.values()) == pytest.approx(second.total_savings)
    assert second.dev_initial["prod0"] >= 100
