# Amortix

[English] · [Deutsch](README.de.md)

[![Validate](https://github.com/USERNAME/amortix/actions/workflows/validate.yml/badge.svg)](https://github.com/USERNAME/amortix/actions/workflows/validate.yml)
[![hacs](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz)

A **device-agnostic amortization integration** for Home Assistant. From cumulative kWh
sensors and a few prices it works out when an energy investment pays for itself – for
balcony solar plants, PV systems and battery storage.

> Core idea: two kWh sensors + prices (as `input_number` or sensor) are enough. The
> calculation is measured, jump-free (60 s cycle, incremental valuation) and works with
> dynamic tariffs (e.g. Tibber).

## Use cases

| Mode | Required sensors | Calculation |
|------|------------------|-------------|
| **Direct use** (balcony/PV without storage) | production, export (to_grid) | `self-consumption × grid price + export × feed-in tariff` |
| **Storage** | charge, discharge | `discharge × grid price − charge × feed-in tariff` |

- **Multiple producers** (e.g. balcony + large PV on the same meter) can be selected
  together in direct mode and are summed.
- Storage works for **AC- and DC-coupled** systems (only charge/discharge energy matters).
- **Roundtrip efficiency** is computed, or an existing sensor is used (informational only).

## Installation

### HACS (recommended)
1. HACS → three dots → **Custom repositories**.
2. Add this repo's URL, category **Integration**.
3. Install "Amortix", restart Home Assistant.

### Manual
1. Copy the `custom_components/amortix/` folder into your Home Assistant config directory.
2. Restart Home Assistant.

## Setup
**Settings → Devices & Services → Add Integration → "Amortix"**, then choose the use case.
Each dialog includes hints about the required sensors and correct setup.

Requirements:
- **Cumulative kWh meters** (`state_class: total`/`total_increasing`), not watt sensors.
- Export as the **netted** value at the grid connection point.
- `input_number` helpers for purchase cost, grid price and (optional) feed-in tariff.

## Created sensors
**Direct use:** total savings (€), grid-purchase savings (€), feed-in savings (€),
self-consumption (kWh), amortization progress (%), remaining (€), savings/day (€),
remaining time (d), payback date.

**Storage:** storage savings (€), discharge (kWh), charge (kWh), roundtrip η (%) plus the
shared amortization metrics.

## Icon
Icons live under `icons/`. To show them in Home Assistant they must go into the
[home-assistant/brands](https://github.com/home-assistant/brands) repo under
`custom_integrations/amortix/icon.png` (256×256) and `icon@2x.png` (512×512).

## License
MIT – see [LICENSE](LICENSE).
