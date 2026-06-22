"""Sensoren der Amortisations-Integration (modusabhängig)."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_MODE, DOMAIN, MODE_DIRECT, MODE_STORAGE


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    manager = hass.data[DOMAIN][entry.entry_id]
    mode = entry.data.get(CONF_MODE, MODE_DIRECT)

    # gemeinsame Kennzahlen-Sensoren
    common = [
        ProgressSensor(manager, entry),
        RemainingSensor(manager, entry),
        DailyAverageSensor(manager, entry),
        RemainingDaysSensor(manager, entry),
        PaybackDateSensor(manager, entry),
    ]

    if mode == MODE_STORAGE:
        specific = [
            StorageSavingsSensor(manager, entry),
            DischargeSensor(manager, entry),
            ChargeSensor(manager, entry),
            RoundtripSensor(manager, entry),
        ]
    else:
        specific = [
            DirectSavingsSensor(manager, entry),
            SavingsGridSensor(manager, entry),
            SavingsExportSensor(manager, entry),
            SelfConsumptionSensor(manager, entry),
        ]

    async_add_entities(specific + common)


class _BaseSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _key: str = ""

    def __init__(self, manager, entry: ConfigEntry) -> None:
        self.manager = manager
        self._attr_unique_id = f"{entry.entry_id}_{self._key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Amortix",
            model="Amortix",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.manager.add_listener(self._on_update))

    @callback
    def _on_update(self) -> None:
        self.async_write_ha_state()


# ---------------------------------------------------------------- gemeinsam
class ProgressSensor(_BaseSensor):
    _key = "fortschritt"
    _attr_name = "Amortisation Fortschritt"
    _attr_icon = "mdi:progress-check"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def native_value(self):
        v = self.manager.progress
        return round(v, 1) if v is not None else None


class RemainingSensor(_BaseSensor):
    _key = "verbleibend"
    _attr_name = "Amortisation verbleibend"
    _attr_icon = "mdi:cash-minus"
    _attr_native_unit_of_measurement = "€"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def native_value(self):
        v = self.manager.remaining
        return round(v, 2) if v is not None else None


class DailyAverageSensor(_BaseSensor):
    _key = "tagesschnitt"
    _attr_name = "Ersparnis pro Tag"
    _attr_icon = "mdi:calendar-clock"
    _attr_native_unit_of_measurement = "€"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 2

    @property
    def native_value(self):
        v = self.manager.daily_average
        return round(v, 2) if v is not None else None


class RemainingDaysSensor(_BaseSensor):
    _key = "resttage"
    _attr_name = "Amortisation Restzeit"
    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "d"
    _attr_suggested_display_precision = 0

    @property
    def native_value(self):
        v = self.manager.remaining_days
        return round(v) if v is not None else None


class PaybackDateSensor(_BaseSensor):
    _key = "datum"
    _attr_name = "Amortisation Datum"
    _attr_icon = "mdi:calendar-check"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        return self.manager.payback_date


# ---------------------------------------------------------------- Direkt
class DirectSavingsSensor(_BaseSensor):
    _key = "einsparung"
    _attr_name = "Einsparung gesamt"
    _attr_icon = "mdi:cash-multiple"
    _attr_native_unit_of_measurement = "€"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self):
        return round(self.manager.total_savings, 2)

    @property
    def extra_state_attributes(self):
        m = self.manager
        attrs = {
            "startgutschrift_eur": round(m.initial_credit, 2),
            "einsparung_seit_start_eur": round(m.total_savings - m.initial_credit, 2),
            "erzeugung_kwh": round(m.total_produced, 3),
            "eigenverbrauch_kwh": round(m.total_self_consumed, 3),
            "einspeisung_kwh": round(m.total_fed_in, 3),
            "inbetriebnahme": m.start_time,
        }
        for key, value in m.credit_breakdown.items():
            attrs[f"startgutschrift_{key}"] = value
        return attrs


class SavingsGridSensor(_BaseSensor):
    _key = "einsparung_netzbezug"
    _attr_name = "Einsparung Netzbezug"
    _attr_icon = "mdi:transmission-tower-import"
    _attr_native_unit_of_measurement = "€"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self):
        return round(self.manager.savings_self, 2)


class SavingsExportSensor(_BaseSensor):
    _key = "einsparung_einspeisung"
    _attr_name = "Einsparung Einspeisung"
    _attr_icon = "mdi:transmission-tower-export"
    _attr_native_unit_of_measurement = "€"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self):
        return round(self.manager.savings_export, 2)


class SelfConsumptionSensor(_BaseSensor):
    _key = "eigenverbrauch"
    _attr_name = "Eigenverbrauch gesamt"
    _attr_icon = "mdi:home-lightning-bolt"
    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    @property
    def native_value(self):
        return round(self.manager.total_self_consumed, 3)


# ---------------------------------------------------------------- Speicher
class StorageSavingsSensor(_BaseSensor):
    _key = "einsparung"
    _attr_name = "Speicher-Ersparnis gesamt"
    _attr_icon = "mdi:cash-multiple"
    _attr_native_unit_of_measurement = "€"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_suggested_display_precision = 2

    @property
    def native_value(self):
        return round(self.manager.total_savings, 2)

    @property
    def extra_state_attributes(self):
        m = self.manager
        attrs = {
            "startgutschrift_eur": round(m.initial_credit, 2),
            "einsparung_seit_start_eur": round(m.total_savings - m.initial_credit, 2),
            "entladung_kwh": round(m.total_discharged, 3),
            "ladung_kwh": round(m.total_charged, 3),
            "inbetriebnahme": m.start_time,
        }
        for key, value in m.credit_breakdown.items():
            attrs[f"startgutschrift_{key}"] = value
        return attrs


class DischargeSensor(_BaseSensor):
    _key = "entladung"
    _attr_name = "Entladung gesamt"
    _attr_icon = "mdi:battery-arrow-down"
    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    @property
    def native_value(self):
        return round(self.manager.total_discharged, 3)


class ChargeSensor(_BaseSensor):
    _key = "ladung"
    _attr_name = "Ladung gesamt"
    _attr_icon = "mdi:battery-arrow-up"
    _attr_native_unit_of_measurement = "kWh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_suggested_display_precision = 2

    @property
    def native_value(self):
        return round(self.manager.total_charged, 3)


class RoundtripSensor(_BaseSensor):
    _key = "roundtrip"
    _attr_name = "Roundtrip-Wirkungsgrad"
    _attr_icon = "mdi:battery-sync"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    @property
    def native_value(self):
        v = self.manager.roundtrip
        return round(v, 1) if v is not None else None
