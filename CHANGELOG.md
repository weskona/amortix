# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Unit tests (`tests/`, pytest, run in GitHub Actions on Python 3.12 and 3.13) for `MonotonicCounter`, the direct-use and storage valuation logic and the deferred starting credit.
- README (EN/DE): documentation of reset handling, the deferred starting credit and a new "Limitations" section (grid charging in storage mode is not priced, linear projection, negative prices, resets below 50 %, price units in €/kWh).

### Changed
- Meter resets are now detected when the reading drops below 50 % of the last value (previously below 10 %), so resets to mid-range values are no longer missed. Smaller dips are ignored.
- The storage-mode starting credit may now be negative so that it always equals the sum of its breakdown attributes.

### Fixed
- Counter glitches: if a glitch (e.g. repeated `0` readings) was confirmed as a reset and the meter then jumps back to its old level within a few updates, the wrong booking is rolled back. Previously the entire history was counted a second time.
- Starting credit is no longer silently set to 0 when a sensor, the price or the feed-in entity is unavailable on first start. It is held back (`initial_pending`) and computed as soon as everything is readable, based on the meter values at the first reading.

## [1.0.2] - 2026-08-12

### Added
- Brand assets for HACS brands validation.

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

[Unreleased]: https://github.com/weskona/amortix/compare/v1.0.2...HEAD
[1.0.2]: https://github.com/weskona/amortix/compare/v1.0.0...v1.0.2
[1.0.0]: https://github.com/weskona/amortix/releases/tag/v1.0.0
