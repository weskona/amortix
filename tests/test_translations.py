"""Konsistenz der Uebersetzungsdateien."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "custom_components" / "amortix"


def load(name):
    return json.loads((BASE / name).read_text(encoding="utf-8"))


def keys(d, prefix=""):
    out = set()
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out |= keys(v, path)
        else:
            out.add(path)
    return out


def test_strings_json_matches_german_translation():
    assert load("strings.json") == load("translations/de.json")


def test_german_and_english_have_the_same_keys():
    assert keys(load("translations/de.json")) == keys(load("translations/en.json"))


def test_every_menu_option_has_a_step():
    for name in ("strings.json", "translations/en.json"):
        d = load(name)["config"]["step"]
        for option in d["user"]["menu_options"]:
            assert option in d, f"{name}: Schritt fuer Menue-Eintrag {option} fehlt"


def test_every_step_field_has_a_description():
    for name in ("strings.json", "translations/en.json"):
        for step, body in load(name)["config"]["step"].items():
            if "data" in body:
                assert set(body["data"]) == set(body["data_description"]), f"{name}:{step}"
