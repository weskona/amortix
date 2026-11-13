"""Tests fuer die Panel-Datenaufbereitung und die Panel-Dateien."""
import json
from pathlib import Path

import pytest

from custom_components.amortix import const as c
from custom_components.amortix.coordinator import OverviewManager, PlantManager
from custom_components.amortix.summary import build_summary
from tests.test_managers import make
from tests.test_plant import PLANT_CFG, STATES, fill

PKG = Path(__file__).resolve().parent.parent / "custom_components" / "amortix"


def test_empty_summary():
    s = build_summary([])
    assert s["entries"] == []
    assert s["total"]["investment"] is None
    assert s["total"]["savings"] == 0
    assert s["total"]["progress"] is None


def test_plant_summary_has_devices_and_totals_match():
    m = make(PlantManager, PLANT_CFG, dict(STATES))
    fill(m, pv=80, b1=10, b2=10, export=30, chg=20, dis=16)
    m._async_evaluate()
    s = build_summary([("e1", "Haus", "plant", m)])
    entry = s["entries"][0]
    assert [d["name"] for d in entry["devices"]] == ["Grosse PV", "BKW 1", "BKW 2", "DC-Speicher"]
    assert sum(d["savings"] for d in entry["devices"]) == pytest.approx(entry["savings"], abs=0.02)
    assert s["total"]["investment"] == 14000
    assert s["total"]["savings"] == entry["savings"]
    assert json.dumps(s)  # muss serialisierbar sein (Websocket)


def test_overview_entries_are_not_double_counted():
    m = make(PlantManager, PLANT_CFG, dict(STATES))
    fill(m, pv=100)
    m._async_evaluate()
    overview = OverviewManager.__new__(OverviewManager)
    s = build_summary([("a", "A", "plant", m), ("o", "Gesamt", "overview", overview)])
    assert len(s["entries"]) == 1
    assert s["total"]["savings"] == s["entries"][0]["savings"]


def test_manifest_declares_panel_dependencies_sorted():
    manifest = json.loads((PKG / "manifest.json").read_text())
    assert {"frontend", "http", "panel_custom", "websocket_api"} <= set(manifest["dependencies"])
    keys = list(manifest)
    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])


def test_panel_js_exists_and_registers_component():
    js = (PKG / "frontend" / "amortix-panel.js").read_text()
    assert 'customElements.define("amortix-panel"' in js
    assert "amortix/subscribe" in js


def test_font_ships_with_license_and_is_served():
    fe = PKG / "frontend"
    assert (fe / "outfit.woff2").read_bytes()[:4] == b"wOF2"
    assert "SIL OPEN FONT LICENSE" in (fe / "OFL-Outfit.txt").read_text().upper()
    assert "outfit.woff2" in (PKG / "panel.py").read_text()
    assert "/amortix_panel/outfit.woff2" in (fe / "amortix-panel.js").read_text()
