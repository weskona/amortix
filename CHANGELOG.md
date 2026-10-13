# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.3.1] - 2026-10-13

### Changed
- Energy sensors chosen during setup must report kWh. Sensors with another unit (Wh, MWh, …) are rejected with a clear message, because they would be off by a factor of 1000. The entity picker still lists only `device_class: energy` sensors.

## [1.3.0] - 2026-10-13

### Added
- New mode **System**: any number of producers (large PV, each balcony plant on its own counter) and storage units (DC or AC) on one grid connection. Cost, savings, progress, remaining time and payback date **per device**; the savings split per device always adds up to the total. Per-device starting values (flat euro amount) for systems that are already running, plus the automatic starting credit split across the devices.
- New mode **Overview**: combines all other Amortix entries (total savings, total investment, progress, remaining time) and exposes a full breakdown per device in the attribute `geraete` of the *Einsparung gesamt* sensor.

### Changed
- The mode *PV with storage (combined)* from 1.2.0 is replaced by **System** in the setup menu. Existing combined entries keep working unchanged.

## [1.2.0] - 2026-10-13

### Added
- Four new modes: **PV with storage** (combined, handles grid charging), **Wallbox / EV**, **Heat pump** (incl. coefficient of performance) and **General** (kWh counter against a reference price). Each has its own setup dialog, options flow, sensors and German/English texts.
- Price entities may be `input_number`, `number` or (dynamic) sensors; prices reported in ct/kWh are converted to €/kWh automatically.
- Starting credit for the new modes: flat amount and/or automatically from the current meter readings.
- README (EN/DE): documentation of all modes and a note on the battery-to-grid limitation.

### Changed
- Price and feed-in entities reporting ct/kWh are converted to €/kWh automatically (also in the existing Direct use and Storage modes).
- Price entities can additionally be `number` entities.
- The "same sensor" error message now covers all modes.

## [1.1.0] - 2026-10-13

### Added
- Unit tests (`tests/`, pytest, run in GitHub Actions on Python 3.12 and 3.13) for `MonotonicCounter`, the direct-use and storage valuation logic and the deferred starting credit.
- GitHub Release notes are taken from the matching `CHANGELOG.md` section by the release workflow.
- README (EN/DE): documentation of reset handling, the deferred starting credit and a new "Limitations" section (grid charging in storage mode is not priced, linear projection, negative prices, resets below 50 %, price units in €/kWh).

### Changed
- README reworked to match the project's documentation standard.
- Meter resets are now detected when the reading drops below 50 % of the last value (previously below 10 %), so resets to mid-range values are no longer missed. Smaller dips are ignored.
- The storage-mode starting credit may now be negative so that it always equals the sum of its breakdown attributes.

### Fixed
- Counter glitches: if a glitch (e.g. repeated `0` readings) was confirmed as a reset and the meter then jumps back to its old level within a few updates, the wrong booking is rolled back. Previously the entire history was counted a second time.
- Starting credit is no longer silently set to 0 when a sensor, the price or the feed-in entity is unavailable on first start. It is held back (`initial_pending`) and computed as soon as everything is readable, based on the meter values at the first reading.

## [1.0.2] - 2026-08-12

### Changed
- Release workflow commits the version bump of `manifest.json` back to `main`.

## [1.0.1] - 2026-08-12

### Added
- Brand assets for HACS brands validation.
- `codeowners` in `manifest.json`.
- `workflow_dispatch` trigger for the validate workflow.

### Changed
- Revised installation and use case sections in the README (EN/DE).

### Fixed
- Options flow: a stale `feed_in_entity` was kept after changing the configuration.
- `KeyError` when unloading the config entry.
- False meter-reset detection.
- Amortization progress is clamped at 0 % and can no longer become negative.

## [1.0.0] - 2026-06-22

### Added
- Initial release: device-independent amortization integration for Home Assistant.
- Two modes: direct use (balcony/PV without storage) and storage (charge/discharge balance).
- Multiple production sensors, summed automatically.
- Starting credit for systems that were already running, entered manually or computed from the current meter readings.
- Reset-safe cumulative counters, evaluated every 60 seconds against live price entities (works with dynamic tariffs).
- Round-trip efficiency in storage mode, calculated or taken from an existing sensor.
- Investment, price and feed-in tariff adjustable afterwards via **Configure**.
- English and German translations.

[Unreleased]: https://github.com/weskona/amortix/compare/v1.3.1...HEAD
[1.3.1]: https://github.com/weskona/amortix/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/weskona/amortix/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/weskona/amortix/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/weskona/amortix/compare/v1.0.2...v1.1.0
[1.0.2]: https://github.com/weskona/amortix/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/weskona/amortix/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/weskona/amortix/releases/tag/v1.0.0
