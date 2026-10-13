"""Config- und Options-Flow für die Amortisations-Integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_CHARGE_SENSOR,
    CONF_DEVICES,
    CONF_DISCHARGE_SENSOR,
    CONF_ELECTRIC_SENSOR,
    CONF_ENERGY_SENSOR,
    CONF_FEED_IN_ENTITY,
    CONF_HEAT_SENSOR,
    CONF_INITIAL_AUTO,
    CONF_INITIAL_CHARGE_KWH,
    CONF_INITIAL_DISCHARGE_KWH,
    CONF_INITIAL_EXPORT_KWH,
    CONF_INITIAL_FEED_IN,
    CONF_INITIAL_PRICE,
    CONF_INITIAL_SAVINGS,
    CONF_INITIAL_SELF_KWH,
    CONF_INVESTMENT_ENTITY,
    CONF_MODE,
    CONF_OWN_PRICE_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_PRODUCTION_SENSOR,
    CONF_REFERENCE_PRICE_ENTITY,
    CONF_ROUNDTRIP_ENTITY,
    CONF_STORAGES,
    CONF_TO_GRID_SENSOR,
    DOMAIN,
    MODE_COMBINED,
    MODE_DIRECT,
    MODE_GENERIC,
    MODE_HEATPUMP,
    MODE_OVERVIEW,
    MODE_STORAGE,
    MODE_PLANT,
    MODE_WALLBOX,
)
from .units import non_kwh_entity

ENERGY_SENSOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
)
ENERGY_SENSORS = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="energy", multiple=True)
)
# input_number, number oder (auch dynamischer) Sensor, z. B. Tibber/aWATTar
VALUE_ENTITY = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number", "number"])
)
BOOLEAN = selector.BooleanSelector()
EURO = selector.NumberSelector(
    selector.NumberSelectorConfig(min=0, step=1, unit_of_measurement="€", mode=selector.NumberSelectorMode.BOX)
)
KWH = selector.NumberSelector(
    selector.NumberSelectorConfig(min=0, step=1, unit_of_measurement="kWh", mode=selector.NumberSelectorMode.BOX)
)
EURO_KWH = selector.NumberSelector(
    selector.NumberSelectorConfig(min=0, step=0.001, unit_of_measurement="€/kWh", mode=selector.NumberSelectorMode.BOX)
)


# Alle Energie-Sensoren der Einrichtung; müssen kWh liefern (siehe units.py).
_ENERGY_KEYS = (
    CONF_PRODUCTION_SENSOR,
    CONF_TO_GRID_SENSOR,
    CONF_CHARGE_SENSOR,
    CONF_DISCHARGE_SENSOR,
    CONF_ENERGY_SENSOR,
    CONF_HEAT_SENSOR,
    CONF_ELECTRIC_SENSOR,
)


def _non_kwh_entity(hass, user_input: dict[str, Any]) -> str | None:
    return non_kwh_entity(hass, user_input, _ENERGY_KEYS)


def _economics_schema(d: dict[str, Any]) -> dict:
    return {
        vol.Required(CONF_INVESTMENT_ENTITY, description={"suggested_value": d.get(CONF_INVESTMENT_ENTITY)}): VALUE_ENTITY,
        vol.Required(CONF_PRICE_ENTITY, description={"suggested_value": d.get(CONF_PRICE_ENTITY)}): VALUE_ENTITY,
        vol.Optional(CONF_FEED_IN_ENTITY, description={"suggested_value": d.get(CONF_FEED_IN_ENTITY)}): VALUE_ENTITY,
    }


def _economics_schema_for(mode: str, d: dict[str, Any]) -> dict:
    """Preis-/Kosten-Felder je Modus (Einrichtung und Options-Flow)."""
    investment = {
        vol.Required(CONF_INVESTMENT_ENTITY, description={"suggested_value": d.get(CONF_INVESTMENT_ENTITY)}): VALUE_ENTITY,
    }
    if mode in (MODE_WALLBOX, MODE_GENERIC):
        return {
            **investment,
            vol.Required(CONF_REFERENCE_PRICE_ENTITY, description={"suggested_value": d.get(CONF_REFERENCE_PRICE_ENTITY)}): VALUE_ENTITY,
            vol.Optional(CONF_OWN_PRICE_ENTITY, description={"suggested_value": d.get(CONF_OWN_PRICE_ENTITY)}): VALUE_ENTITY,
        }
    if mode == MODE_HEATPUMP:
        return {
            **investment,
            vol.Required(CONF_PRICE_ENTITY, description={"suggested_value": d.get(CONF_PRICE_ENTITY)}): VALUE_ENTITY,
            vol.Required(CONF_REFERENCE_PRICE_ENTITY, description={"suggested_value": d.get(CONF_REFERENCE_PRICE_ENTITY)}): VALUE_ENTITY,
        }
    return _economics_schema(d)  # direct, storage, combined


def _economics_keys(mode: str) -> tuple[str, ...]:
    if mode in (MODE_WALLBOX, MODE_GENERIC):
        return (CONF_INVESTMENT_ENTITY, CONF_REFERENCE_PRICE_ENTITY, CONF_OWN_PRICE_ENTITY)
    if mode == MODE_HEATPUMP:
        return (CONF_INVESTMENT_ENTITY, CONF_PRICE_ENTITY, CONF_REFERENCE_PRICE_ENTITY)
    return (CONF_INVESTMENT_ENTITY, CONF_PRICE_ENTITY, CONF_FEED_IN_ENTITY)


def _startup_flat_only() -> dict:
    """Startgutschrift für die Delta-Modi: automatisch aus Zählerständen und/oder pauschal."""
    return {
        vol.Optional(CONF_INITIAL_AUTO, default=False): BOOLEAN,
        vol.Optional(CONF_INITIAL_SAVINGS, default=0): EURO,
    }


def _startup_common() -> dict:
    return {
        vol.Optional(CONF_INITIAL_AUTO, default=False): BOOLEAN,
    }


def _startup_rates_and_flat() -> dict:
    return {
        vol.Optional(CONF_INITIAL_PRICE, default=0): EURO_KWH,
        vol.Optional(CONF_INITIAL_FEED_IN, default=0): EURO_KWH,
        vol.Optional(CONF_INITIAL_SAVINGS, default=0): EURO,
    }


class AmortizationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Einrichtung über die Benutzeroberfläche."""

    # Entry-Version 4. Alte Einträge (Version < 4) werden in __init__.py
    # via async_migrate_entry hochgezogen (Modus = Direktverbrauch ergänzen).
    VERSION = 4

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="user",
            menu_options=[
                MODE_PLANT,
                MODE_DIRECT,
                MODE_STORAGE,
                MODE_WALLBOX,
                MODE_HEATPUMP,
                MODE_GENERIC,
                MODE_OVERVIEW,
            ],
        )

    async def async_step_direct(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None and (bad := _non_kwh_entity(self.hass, user_input)):
            errors["base"] = "not_kwh"
            placeholders["entity"] = bad
        elif user_input is not None:
            production = user_input[CONF_PRODUCTION_SENSOR]
            if user_input[CONF_TO_GRID_SENSOR] in production:
                errors["base"] = "same_sensor"
            else:
                user_input[CONF_MODE] = MODE_DIRECT
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Balkonkraftwerk"): selector.TextSelector(),
                vol.Required(CONF_PRODUCTION_SENSOR): ENERGY_SENSORS,
                vol.Required(CONF_TO_GRID_SENSOR): ENERGY_SENSOR,
                **_economics_schema({}),
                **_startup_common(),
                vol.Optional(CONF_INITIAL_SELF_KWH, default=0): KWH,
                vol.Optional(CONF_INITIAL_EXPORT_KWH, default=0): KWH,
                **_startup_rates_and_flat(),
            }
        )
        return self.async_show_form(
            step_id="direct",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_storage(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None and (bad := _non_kwh_entity(self.hass, user_input)):
            errors["base"] = "not_kwh"
            placeholders["entity"] = bad
        elif user_input is not None:
            if user_input[CONF_CHARGE_SENSOR] == user_input[CONF_DISCHARGE_SENSOR]:
                errors["base"] = "same_sensor"
            else:
                user_input[CONF_MODE] = MODE_STORAGE
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Speicher"): selector.TextSelector(),
                vol.Required(CONF_CHARGE_SENSOR): ENERGY_SENSOR,
                vol.Required(CONF_DISCHARGE_SENSOR): ENERGY_SENSOR,
                vol.Optional(CONF_ROUNDTRIP_ENTITY): VALUE_ENTITY,
                **_economics_schema({}),
                **_startup_common(),
                vol.Optional(CONF_INITIAL_DISCHARGE_KWH, default=0): KWH,
                vol.Optional(CONF_INITIAL_CHARGE_KWH, default=0): KWH,
                **_startup_rates_and_flat(),
            }
        )
        return self.async_show_form(
            step_id="storage",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    # ------------------------------------------------------------------
    # Anlage (plant): beliebig viele Erzeuger und Speicher, Kosten je Gerät
    # ------------------------------------------------------------------
    _system: dict[str, Any] | None = None
    _device_queue: list[str] | None = None

    def _friendly_name(self, entity_id: str) -> str:
        state = self.hass.states.get(entity_id)
        return state.name if state else entity_id

    async def async_step_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None and (bad := _non_kwh_entity(self.hass, user_input)):
            errors["base"] = "not_kwh"
            placeholders["entity"] = bad
        elif user_input is not None:
            if user_input[CONF_TO_GRID_SENSOR] in user_input[CONF_PRODUCTION_SENSOR]:
                errors["base"] = "same_sensor"
            else:
                self._system = {
                    **user_input,
                    CONF_MODE: MODE_PLANT,
                    CONF_DEVICES: [],
                    CONF_STORAGES: [],
                }
                self._device_queue = list(user_input[CONF_PRODUCTION_SENSOR])
                return await self.async_step_plant_device()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Anlage"): selector.TextSelector(),
                vol.Required(CONF_PRODUCTION_SENSOR): ENERGY_SENSORS,
                vol.Required(CONF_TO_GRID_SENSOR): ENERGY_SENSOR,
                vol.Required(CONF_PRICE_ENTITY): VALUE_ENTITY,
                vol.Optional(CONF_FEED_IN_ENTITY): VALUE_ENTITY,
                **_startup_flat_only(),
            }
        )
        return self.async_show_form(
            step_id="plant",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_plant_device(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Name, Kosten und Startwert je Erzeuger (ein Durchlauf je Sensor)."""
        sensor = self._device_queue[0]
        if user_input is not None:
            device = {
                "sensor": sensor,
                "name": user_input[CONF_NAME],
                "initial_savings": user_input.get(CONF_INITIAL_SAVINGS, 0),
            }
            if user_input.get(CONF_INVESTMENT_ENTITY):
                device[CONF_INVESTMENT_ENTITY] = user_input[CONF_INVESTMENT_ENTITY]
            self._system[CONF_DEVICES].append(device)
            self._device_queue.pop(0)
            if self._device_queue:
                return await self.async_step_plant_device()
            return await self.async_step_plant_more()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=self._friendly_name(sensor)): selector.TextSelector(),
                vol.Optional(CONF_INVESTMENT_ENTITY): VALUE_ENTITY,
                vol.Optional(CONF_INITIAL_SAVINGS, default=0): EURO,
            }
        )
        return self.async_show_form(
            step_id="plant_device",
            data_schema=schema,
            description_placeholders={"sensor": sensor},
        )

    async def async_step_plant_more(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="plant_more", menu_options=["plant_storage", "plant_finish"]
        )

    async def async_step_plant_storage(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None and (bad := _non_kwh_entity(self.hass, user_input)):
            errors["base"] = "not_kwh"
            placeholders["entity"] = bad
        elif user_input is not None:
            used = {
                self._system[CONF_TO_GRID_SENSOR],
                *self._system[CONF_PRODUCTION_SENSOR],
                *(st[key] for st in self._system[CONF_STORAGES] for key in (CONF_CHARGE_SENSOR, CONF_DISCHARGE_SENSOR)),
            }
            charge, discharge = user_input[CONF_CHARGE_SENSOR], user_input[CONF_DISCHARGE_SENSOR]
            if charge == discharge or charge in used or discharge in used:
                errors["base"] = "same_sensor"
            else:
                storage = {
                    "name": user_input[CONF_NAME],
                    CONF_CHARGE_SENSOR: charge,
                    CONF_DISCHARGE_SENSOR: discharge,
                    "initial_savings": user_input.get(CONF_INITIAL_SAVINGS, 0),
                }
                if user_input.get(CONF_INVESTMENT_ENTITY):
                    storage[CONF_INVESTMENT_ENTITY] = user_input[CONF_INVESTMENT_ENTITY]
                self._system[CONF_STORAGES].append(storage)
                return await self.async_step_plant_more()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Speicher"): selector.TextSelector(),
                vol.Required(CONF_CHARGE_SENSOR): ENERGY_SENSOR,
                vol.Required(CONF_DISCHARGE_SENSOR): ENERGY_SENSOR,
                vol.Optional(CONF_INVESTMENT_ENTITY): VALUE_ENTITY,
                vol.Optional(CONF_INITIAL_SAVINGS, default=0): EURO,
            }
        )
        return self.async_show_form(
            step_id="plant_storage",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_plant_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_create_entry(title=self._system[CONF_NAME], data=self._system)

    # ------------------------------------------------------------------
    # Gesamtübersicht
    # ------------------------------------------------------------------
    async def async_step_overview(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if any(e.data.get(CONF_MODE) == MODE_OVERVIEW for e in self._async_current_entries()):
            return self.async_abort(reason="overview_exists")
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME], data={**user_input, CONF_MODE: MODE_OVERVIEW}
            )
        schema = vol.Schema({vol.Required(CONF_NAME, default="Gesamt"): selector.TextSelector()})
        return self.async_show_form(step_id="overview", data_schema=schema)

    async def _async_step_generic(
        self, mode: str, default_name: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None and (bad := _non_kwh_entity(self.hass, user_input)):
            errors["base"] = "not_kwh"
            placeholders["entity"] = bad
        elif user_input is not None:
            user_input[CONF_MODE] = mode
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=default_name): selector.TextSelector(),
                vol.Required(CONF_ENERGY_SENSOR): ENERGY_SENSOR,
                **_economics_schema_for(mode, {}),
                **_startup_flat_only(),
            }
        )
        return self.async_show_form(
            step_id=mode,
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_wallbox(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_step_generic(MODE_WALLBOX, "Wallbox", user_input)

    async def async_step_generic(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._async_step_generic(MODE_GENERIC, "Gerät", user_input)

    async def async_step_heatpump(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {}
        if user_input is not None and (bad := _non_kwh_entity(self.hass, user_input)):
            errors["base"] = "not_kwh"
            placeholders["entity"] = bad
        elif user_input is not None:
            if user_input[CONF_HEAT_SENSOR] == user_input[CONF_ELECTRIC_SENSOR]:
                errors["base"] = "same_sensor"
            else:
                user_input[CONF_MODE] = MODE_HEATPUMP
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="Wärmepumpe"): selector.TextSelector(),
                vol.Required(CONF_HEAT_SENSOR): ENERGY_SENSOR,
                vol.Required(CONF_ELECTRIC_SENSOR): ENERGY_SENSOR,
                **_economics_schema_for(MODE_HEATPUMP, {}),
                **_startup_flat_only(),
            }
        )
        return self.async_show_form(
            step_id="heatpump",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "AmortizationOptionsFlow":
        return AmortizationOptionsFlow()



class AmortizationOptionsFlow(OptionsFlow):
    """Live-Werte nachträglich anpassen (Sensoren & Startgutschrift bleiben fix)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        mode = self.config_entry.data.get(CONF_MODE, MODE_DIRECT)
        if mode == MODE_OVERVIEW:
            return self.async_abort(reason="no_options")
        if mode == MODE_PLANT:
            return await self.async_step_plant(user_input)
        if user_input is not None:
            # Vollstaendig aufgeloest in entry.data schreiben statt in
            # entry.options: {**data, **options} in BaseManager.config wuerde
            # ein hier geleertes feed_in_entity sonst auf den alten, in
            # entry.data verbliebenen Wert zurueckfallen lassen (nur die
            # tatsaechlich uebermittelten Felder landen in user_input,
            # geleerte fehlen einfach statt explizit None zu sein).
            new_data = {**self.config_entry.data, **user_input}
            mode = self.config_entry.data.get(CONF_MODE, MODE_DIRECT)
            for key in _economics_keys(mode):
                if key not in user_input:
                    new_data.pop(key, None)
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})
        current = {**self.config_entry.data, **self.config_entry.options}
        mode = current.get(CONF_MODE, MODE_DIRECT)
        schema = vol.Schema(_economics_schema_for(mode, current))
        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_plant(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Preise und Kosten je Gerät der Anlage anpassen."""
        data = {**self.config_entry.data, **self.config_entry.options}
        devices = [dict(d) for d in data.get(CONF_DEVICES, [])]
        storages = [dict(st) for st in data.get(CONF_STORAGES, [])]

        if user_input is not None:
            new_data = {**self.config_entry.data}
            new_data[CONF_PRICE_ENTITY] = user_input[CONF_PRICE_ENTITY]
            new_data.pop(CONF_FEED_IN_ENTITY, None)
            if user_input.get(CONF_FEED_IN_ENTITY):
                new_data[CONF_FEED_IN_ENTITY] = user_input[CONF_FEED_IN_ENTITY]
            for prefix, items in (("device", devices), ("storage", storages)):
                for i, item in enumerate(items):
                    item.pop(CONF_INVESTMENT_ENTITY, None)
                    value = user_input.get(f"{prefix}_{i + 1}_investment")
                    if value:
                        item[CONF_INVESTMENT_ENTITY] = value
            new_data[CONF_DEVICES] = devices
            new_data[CONF_STORAGES] = storages
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            return self.async_create_entry(title="", data={})

        fields: dict = {
            vol.Required(CONF_PRICE_ENTITY, description={"suggested_value": data.get(CONF_PRICE_ENTITY)}): VALUE_ENTITY,
            vol.Optional(CONF_FEED_IN_ENTITY, description={"suggested_value": data.get(CONF_FEED_IN_ENTITY)}): VALUE_ENTITY,
        }
        names = []
        for prefix, items in (("device", devices), ("storage", storages)):
            for i, item in enumerate(items):
                fields[vol.Optional(f"{prefix}_{i + 1}_investment", description={"suggested_value": item.get(CONF_INVESTMENT_ENTITY)})] = VALUE_ENTITY
                names.append(f"{prefix} {i + 1} = {item.get('name', '')}")
        return self.async_show_form(
            step_id="plant",
            data_schema=vol.Schema(fields),
            description_placeholders={"devices": "; ".join(names)},
        )
