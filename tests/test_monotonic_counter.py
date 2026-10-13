"""Tests fuer MonotonicCounter (Reset-/Glitch-Erkennung)."""
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
    c.update(1500.0)  # weit nach dem Reset: normaler Anstieg, kein Rollback
    assert c.total == pytest.approx(4.0 + 1496.0)
