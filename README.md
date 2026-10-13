# Amortix

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![GitHub Release](https://img.shields.io/github/v/release/weskona/amortix)](https://github.com/weskona/amortix/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![HA min version](https://img.shields.io/badge/Home%20Assistant-2024.4%2B-blue)](https://www.home-assistant.io)
[![Validate](https://github.com/weskona/amortix/actions/workflows/validate.yml/badge.svg)](https://github.com/weskona/amortix/actions/workflows/validate.yml)

[🇩🇪 Deutsche Version](README.de.md)

A **device-agnostic amortization tracker for Home Assistant**. From cumulative kWh sensors and a few prices, Amortix works out when an energy investment pays for itself — for balcony solar plants, PV systems, and battery storage. No vendor API, no cloud account: any integration that reports cumulative kWh works.

> Two kWh sensors + prices (as `input_number` or sensor) are enough. The calculation is measured, jump-free (60 s cycle, incremental valuation) and works with dynamic tariffs (e.g. Tibber).

---

## Features

- **Device-agnostic** — works with any HA entity that reports cumulative kWh (inverter, wallbox, BMS, ...), no manufacturer integration required.
- **Two modes** — Direct consumption (balcony/PV without storage) or Storage (battery charge/discharge balance), each with its own sensor set.
- **Measured, not estimated** — evaluates every 60 seconds against your actual live price/tariff entities, so it stays accurate with dynamic tariffs instead of a flat average.
- **Multiple production sources** — select several production sensors at once (e.g. balcony + roof PV); they're summed automatically.
- **Starting credit** — an already-running system can start with its accumulated savings applied, either entered manually or computed automatically from current meter readings.
- **Meter-reset safe** — a cumulative counter that genuinely resets (firmware update, device swap) is recognized and keeps counting forward without losing history; a single-sample glitch (e.g. a brief `0` instead of `unavailable`) is told apart from a real reset and doesn't get double-counted.
- **Roundtrip efficiency** (storage mode) — computed from your charge/discharge totals, or an existing efficiency sensor can be used instead.
- **Adjustable later** — investment cost, grid price, and feed-in tariff entities can be changed anytime via **Configure**, without losing accumulated history.

---

## Installation

### HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=weskona&repository=amortix&category=integration)

Click the button above to add Amortix to HACS, then **Download** and restart Home Assistant.

<details>
<summary>Manual HACS steps</summary>

1. HACS → three dots (top right) → **Custom repositories**.
2. URL `https://github.com/weskona/amortix`, category **Integration**.
3. Add, then open **Amortix** and **Download**.
4. Restart Home Assistant.
</details>

### Manual (without HACS)

1. Copy `custom_components/amortix/` into your Home Assistant `config` directory.
2. Restart Home Assistant.

---

## Configuration

**Settings → Devices & Services → Add Integration → "Amortix"**, then choose a mode. Every field in the dialog has an inline description explaining exactly what to select and why.

| Mode | Required sensors | Optional | Calculation |
|------|-------------------|----------|-------------|
| **Direct use** (balcony/PV without storage) | Production (one or more), export/`to_grid` | Feed-in tariff entity, starting credit | `self-consumption × grid price + export × feed-in tariff` |
| **Storage** | Charge, discharge | Roundtrip-efficiency sensor, feed-in tariff entity, starting credit | `discharge × grid price − charge × feed-in tariff` |

Both modes also require an **investment cost** entity and a **grid price** entity (`input_number` or sensor — a live tariff sensor such as Tibber works too).

Requirements for all sensors:
- **Cumulative kWh meters** (`state_class: total`/`total_increasing`), not watt sensors.
- Must have **`device_class: energy`** set — the entity picker only lists sensors with that device class, so a template/utility_meter sensor without it won't show up until you add it.
- Export/charge/discharge as the actual meter register — not a signed/net value, not per-phase.

**Investment cost, grid price, and feed-in tariff can be changed later** without losing history: **Settings → Devices & Services → Amortix → Configure**. The production/export/charge/discharge sensors and the starting credit are fixed at setup and not editable afterward (they define the accounting baseline).

---

## Sensors

### Shared (both modes)

| Key | Name | Description |
|-----|------|--------------|
| `fortschritt` | Amortisation Fortschritt | Share of the investment recovered so far, 0–100 % (floored at 0 %, capped at 100 %). `unknown` without an investment value. |
| `verbleibend` | Amortisation verbleibend | Remaining amount (€) until the investment is fully recovered. |
| `tagesschnitt` | Ersparnis pro Tag | Average daily savings (€) since the starting credit was applied. `unknown` with less than 12 hours of history or no net savings yet. |
| `resttage` | Amortisation Restzeit | Estimated days remaining until payback, from the daily average. |
| `datum` | Amortisation Datum | Estimated payback date/time, from the daily average. |

### Direct use only

| Key | Name | Description |
|-----|------|--------------|
| `einsparung` | Einsparung gesamt | Total savings (€): grid-purchase savings + feed-in revenue, including the starting credit. Attributes: `startgutschrift_eur`, `einsparung_seit_start_eur`, `erzeugung_kwh`, `eigenverbrauch_kwh`, `einspeisung_kwh`, `inbetriebnahme`. |
| `einsparung_netzbezug` | Einsparung Netzbezug | Savings (€) from self-consumption offsetting grid purchase. |
| `einsparung_einspeisung` | Einsparung Einspeisung | Revenue (€) from feed-in. |
| `eigenverbrauch` | Eigenverbrauch gesamt | Total self-consumed energy (kWh). |

### Storage only

| Key | Name | Description |
|-----|------|--------------|
| `einsparung` | Speicher-Ersparnis gesamt | Total storage savings (€): discharge value minus foregone feed-in for charging, including the starting credit. Same attributes as direct-use `einsparung`, adapted to `entladung_kwh`/`ladung_kwh`. |
| `entladung` | Entladung gesamt | Total discharged energy (kWh). |
| `ladung` | Ladung gesamt | Total charged energy (kWh). |
| `roundtrip` | Roundtrip-Wirkungsgrad | Roundtrip efficiency (%) — from a configured sensor if set, otherwise `discharge ÷ charge`. Not capped at 100 % (needs several full cycles to settle); purely informational, not used in the € calculation. |

---

## How It Works

Amortix doesn't estimate — it evaluates your configured sensors every 60 seconds and only credits progress when the underlying meters have genuinely moved forward.

- **Monotonic accounting.** Each cumulative sensor is tracked as an ever-increasing running total, independent of what the raw sensor itself does. A genuine meter reset (firmware update, device swap — reading drops below half of the last value) is recognized and continues counting from there instead of losing history. A reset is only confirmed after two consecutive low readings, so a brief glitch (e.g. a temporary `0` instead of `unavailable`) isn't mistaken for one. If a glitch lasts long enough to be confirmed as a reset but the meter then jumps back to its old level within a few updates, the wrong booking is rolled back, so the history is never counted twice. Smaller dips (rounding, minor corrections) are ignored.
- **Savings only move forward.** Each 60-second evaluation adds newly produced/self-consumed/discharged energy at the currently valid price — nothing is ever recomputed from scratch, so changing the price entity later doesn't retroactively rewrite past savings.
- **Starting credit.** For a system that was already running before Amortix was set up, a one-time starting credit is computed once at setup — either from manually entered historical kWh figures, or automatically from the sensors' current readings — and added to the running total. If a sensor, the price or the feed-in entity is unavailable during the first start, the credit is not silently set to 0: it is held back (`initial_pending`, logged as a warning) and computed as soon as everything is readable, based on the meter values at that first reading. It's never recalculated afterward, and the sensor/price entities can still be changed later via **Configure** without disturbing it.
- **Progress can't go negative.** In storage mode, a stretch of charging without discharging while a feed-in tariff applies can temporarily reduce total savings below the starting credit. The amortization progress sensor is floored at 0 % regardless. For the same reason the storage starting credit can be negative (e.g. a lot of charging, little discharging so far); it always equals the sum of its breakdown attributes.


### Limitations

- **Storage: charging from the grid isn't priced.** The storage calculation assumes the battery is charged from your own PV surplus: charged energy only costs the feed-in tariff you would have received. If you also charge from the grid (dynamic tariff, night rate), the cost of that electricity is **not** deducted and the savings are overstated.
- **Projection is linear.** *Savings per day*, *Remaining time* and *Payback date* extrapolate the average since setup. With PV the yield is strongly seasonal, so a start in winter or summer skews the estimate; it becomes more reliable after a full year.
- **Negative prices.** If the price entity goes negative (dynamic tariffs), self-consumed energy is valued negatively as well.
- **Meter resets.** A reset that only drops the reading by less than half (e.g. 12 → 8 kWh) is treated as a normal correction and not detected, since treating every moderate dip as a reset would risk counting energy twice.
- **Sensor units.** Price entities must provide €/kWh (not ct/kWh), energy sensors kWh.
---

## Requirements

- **Home Assistant 2024.4** or later
- Cumulative kWh sensors for production/export (direct use) or charge/discharge (storage)
- `input_number` or sensor entities for investment cost and grid price

---

## License

MIT – see [LICENSE](LICENSE).
