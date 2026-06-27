# Amortix

[English] · [Deutsch](README.de.md)

[![Validate](https://github.com/weskona/amortix/actions/workflows/validate.yml/badge.svg)](https://github.com/weskona/amortix/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)
[![release](https://img.shields.io/github/v/release/weskona/amortix)](https://github.com/weskona/amortix/releases)
[![license](https://img.shields.io/github/license/weskona/amortix)](LICENSE)

A **device-agnostic amortization integration** for Home Assistant. From cumulative kWh
sensors and a few prices it works out when an energy investment pays for itself – for
balcony solar plants, PV systems and battery storage.

> Two kWh sensors + prices (as `input_number` or sensor) are enough. The calculation is
> measured, jump-free (60 s cycle, incremental valuation) and works with dynamic tariffs
> (e.g. Tibber).

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

## Setup
**Settings → Devices & Services → Add Integration → "Amortix"**, then choose the use case.
Each dialog includes hints about the required sensors and correct setup.

Requirements:
- **Cumulative kWh meters** (`state_class: total`/`total_increasing`), not watt sensors.
- Export as the **netted** value at the grid connection point.
- `input_number` helpers for purchase cost, grid price and (optional) feed-in tariff.

## Use cases

| Mode | Required sensors | Calculation |
|------|------------------|-------------|
| **Direct use** (balcony/PV without storage) | production, export (to_grid) | `self-consumption × grid price + export × feed-in tariff` |
| **Storage** | charge, discharge | `discharge × grid price − charge × feed-in tariff` |

- **Multiple producers** (e.g. balcony + large PV on the same meter) can be selected
  together in direct mode and are summed.
- Storage works for **AC- and DC-coupled** systems (only charge/discharge energy matters).
- **Roundtrip efficiency** is computed, or an existing sensor is used (informational only).
- **Starting credit** lets already-running systems begin with their accumulated savings
  (manual or automatic from current meter readings).

## Created sensors
**Direct use:** total savings (€), grid-purchase savings (€), feed-in savings (€),
self-consumption (kWh), amortization progress (%), remaining (€), savings/day (€),
remaining time (d), payback date.

**Storage:** storage savings (€), discharge (kWh), charge (kWh), roundtrip η (%) plus the
shared amortization metrics.

## License
MIT – see [LICENSE](LICENSE).
