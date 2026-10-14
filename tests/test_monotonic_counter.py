"""Tests fuer MonotonicCounter (Reset-/Glitch-Erkennung)."""
import time

import pytest

from custom_components.amortix.coordinator import MonotonicCounter


def feed(readings, start=None):
    counter = MonotonicCounter()
    if start is not None:
        counter.update(start)
    for r in readings:
        counter.update(r)
    return counter


def test_first_reading_only_seeds():
    c = feed([100.0])
    assert c.total == 0.0
    assert c.raw_last == 100.0


def test_normal_increase_accumulates():
    c = feed([100.0, 101.5, 103.0])
    assert c.total == pytest.approx(3.0)


def test_small_dip_is_ignored():
    c = feed([100.0, 99.9, 101.0])
    assert c.total == pytest.approx(1.0)


def test_single_zero_glitch_is_not_counted_twice():
    c = feed([1000.0, 0.0, 1001.0])
    assert c.total == pytest.approx(1.0)


def test_real_reset_to_zero_continues_counting():
    c = feed([1000.0, 0.0, 0.2, 1.0])
    # 0.2 bestaetigt den Reset, danach zaehlt 1.0 - 0.2 dazu
    assert c.total == pytest.approx(1.0)


def test_restore_keeps_total_and_raw_last():
    c = MonotonicCounter()
    c.restore(500.0, 42.0)
    c.update(501.0)
    assert c.total == pytest.approx(43.0)


# ----------------------------------------------------------------------
# Regressionstests fuer die im Review gefundenen Schwaechen
# ----------------------------------------------------------------------
def test_double_zero_glitch_then_recovery_is_not_double_counted():
    c = feed([1000.0, 0.0, 0.0, 1000.0, 1001.0])
    assert c.total == pytest.approx(1.0)


def test_mid_value_reset_is_detected():
    # 12 -> 2 kWh ist ein Reset; seit dem Reset sind 5 kWh angefallen (Zaehler steht bei 5)
    c = feed([12.0, 2.0, 3.0, 5.0])
    assert c.total == pytest.approx(5.0)


def test_mid_value_reset_loses_no_energy():
    c = feed([12.0, 2.0, 4.0, 6.0, 8.0])
    # nach dem Reset sind 6 kWh (2 -> 8) angefallen, plus 2 bis zum Reset-Wert selbst
    assert c.total >= 6.0


def test_glitch_with_different_low_values_is_rolled_back():
    c = feed([1000.0, 0.0, 5.0, 1000.0, 1001.0])
    assert c.total == pytest.approx(1.0)


def test_partial_recovery_clears_candidate():
    # 1000 -> 0 (Kandidat) -> 700 (Erholung, ignoriert) -> 0: neuer Kandidat, kein Reset
    c = feed([1000.0, 0.0, 700.0, 0.0, 1002.0])
    assert c.total == pytest.approx(2.0)


def test_moderate_correction_is_not_treated_as_reset():
    c = feed([100.0, 85.0, 86.0, 101.0])
    assert c.total == pytest.approx(1.0)


def test_falling_low_values_keep_candidate_until_stable():
    c = feed([1000.0, 5.0, 2.0, 2.5, 3.0])
    # Reset bestaetigt bei 2.5 -> +2.5, danach +0.5
    assert c.total == pytest.approx(3.0)


def test_guard_expires_so_later_high_readings_are_normal_increase():
    c = feed([1000.0, 0.0, 0.0, 1.0, 2.0, 3.0, 4.0])
    assert c.total == pytest.approx(4.0)
    # weit nach dem Reset (20 h spaeter): normaler Anstieg, kein Rollback
    c.update(1500.0, now=time.time() + 20 * 3600)
    assert c.total == pytest.approx(4.0 + 1496.0)


# --- Plausibilitaet nach oben (Sprung-Schutz) --------------------------------

T0 = 1_000_000.0


def timed(readings, start=1000.0):
    """readings: Liste (Sekunden seit Start, Wert)."""
    c = MonotonicCounter()
    c.update(start, now=T0)
    for dt, r in readings:
        c.update(r, now=T0 + dt)
    return c


def test_huge_upward_jump_is_not_booked():
    c = timed([(60, 1000.5), (120, 19206.5)])
    assert c.total == pytest.approx(0.5)
    assert c.jumps_rejected == 1


def test_jump_that_falls_back_is_a_glitch_and_booking_continues():
    c = timed([(60, 1000.5), (120, 19206.5), (180, 1001.0)])
    assert c.total == pytest.approx(1.0)
    assert c.raw_last == pytest.approx(1001.0)
    assert c.jumps_rebased == 0


def test_stable_new_level_is_rebased_without_booking():
    # z. B. Utility-Meter-Kalibrierung: neues Niveau haelt -> kein Ertrag gebucht
    c = timed([(60, 1000.5), (120, 19206.5), (180, 19206.6), (240, 19206.7), (300, 19207.0)])
    assert c.jumps_rebased == 1
    assert c.total == pytest.approx(0.5 + 0.3)  # nur echter Zuwachs nach dem Rebase
    assert c.raw_last == pytest.approx(19207.0)


def test_normal_power_never_counts_as_jump():
    # 30 kW ueber eine Stunde = 30 kWh
    c = timed([(3600, 1030.0)])
    assert c.total == pytest.approx(30.0)
    assert c.jumps_rejected == 0


def test_long_gap_scales_the_allowance():
    # 2 Tage Ausfall: 100 kW * 48 h waeren erlaubt, 300 kWh sind plausibel
    c = timed([(2 * 86400, 1300.0)])
    assert c.total == pytest.approx(300.0)


def test_first_update_after_restore_tolerates_a_day_of_catchup_but_not_a_jump():
    c = MonotonicCounter()
    c.restore(1000.0, 50.0)
    c.update(1400.0, now=T0)  # 400 kWh <= 24 h * 100 kW
    assert c.total == pytest.approx(450.0)
    c2 = MonotonicCounter()
    c2.restore(1000.0, 50.0)
    c2.update(19206.0, now=T0)
    assert c2.total == pytest.approx(50.0)
    assert c2.jumps_rejected == 1


def test_jump_during_reset_guard_does_not_break_glitch_recovery():
    c = MonotonicCounter()
    c.update(1000.0, now=T0)
    c.update(0.0, now=T0 + 60)
    c.update(0.0, now=T0 + 120)  # Reset bestaetigt (Guard aktiv)
    c.update(1000.0, now=T0 + 180)  # Rueckkehr auf alten Stand: Rollback
    assert c.total == pytest.approx(0.0)


# --- Preis-/Verguetungs-Plausibilitaet ----------------------------------------

from types import SimpleNamespace

from custom_components.amortix.coordinator import BaseManager


def _reader(states):
    fake = SimpleNamespace(
        hass=SimpleNamespace(
            states=SimpleNamespace(
                get=lambda eid: (
                    SimpleNamespace(state=states[eid][0], attributes={"unit_of_measurement": states[eid][1]})
                    if eid in states
                    else None
                )
            )
        )
    )
    return lambda eid, rate=False: BaseManager._read_entity(fake, eid, rate)


@pytest.mark.parametrize("raw", ["-0.3", "29.77", "nan", "inf", "1000"])
def test_implausible_rate_is_ignored(raw):
    read = _reader({"sensor.p": (raw, "EUR/kWh")})
    assert read("sensor.p", rate=True) is None


def test_cent_price_is_converted_then_checked():
    read = _reader({"sensor.p": ("29.77", "ct/kWh")})
    assert read("sensor.p", rate=True) == pytest.approx(0.2977)


def test_non_rate_values_are_not_range_checked():
    read = _reader({"sensor.inv": ("26023.67", "EUR")})
    assert read("sensor.inv") == pytest.approx(26023.67)


# --- Diagnose-Attribute und Benachrichtigung ----------------------------------

from unittest.mock import patch


def _manager_with(counters):
    fake = SimpleNamespace(_counters=lambda: counters, hass=object())
    fake.jump_attributes = lambda: BaseManager.jump_attributes(fake)
    fake._notify_rebase = lambda eid, jump: BaseManager._notify_rebase(fake, eid, jump)
    return fake


def test_jump_attributes_are_zero_without_jumps():
    m = _manager_with({"sensor.a": timed([(60, 1001.0)])})
    assert m.jump_attributes() == {"spruenge_verworfen": 0, "spruenge_neu_aufgesetzt": 0}


def test_jump_attributes_report_latest_jump():
    a = timed([(60, 19206.0)])
    b = timed([(60, 1001.0), (120, 5000.0)])
    b.last_jump["ts"] += 10  # b ist juenger
    m = _manager_with({"sensor.a": a, "sensor.b": b})
    attrs = m.jump_attributes()
    assert attrs["spruenge_verworfen"] == 2
    assert attrs["letzter_sprung"]["sensor"] == "sensor.b"
    assert attrs["letzter_sprung"]["aktion"] == "rejected"
    assert attrs["letzter_sprung"]["von_kwh"] == pytest.approx(1001.0)


def test_rebase_creates_a_persistent_notification_once_per_sensor():
    m = _manager_with({})
    jump = {"from": 1000.0, "to": 19206.0, "action": "rebase", "ts": T0}
    with patch("custom_components.amortix.coordinator.persistent_notification.async_create") as create:
        m._notify_rebase("sensor.x", jump)
    args, kwargs = create.call_args
    assert kwargs["notification_id"] == "amortix_jump_sensor.x"
    assert "sensor.x" in args[1] and "nicht als" in args[1]
