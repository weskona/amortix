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
    CONF_TO_GRID_SENSOR,
    DOMAIN,
    MODE_COMBINED,
    MODE_DIRECT,
    MODE_GENERIC,
    MODE_HEATPUMP,
    MODE_STORAGE,
    MODE_WALLBOX,
)

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
                MODE_DIRECT,
                MODE_STORAGE,
                MODE_COMBINED,
                MODE_WALLBOX,
                MODE_HEATPUMP,
                MODE_GENERIC,
            ],
        )

    async def async_step_direct(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
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
        return self.async_show_form(step_id="direct", data_schema=schema, errors=errors)

    async def async_step_storage(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
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
        return self.async_show_form(step_id="storage", data_schema=schema, errors=errors)

    async def async_step_combined(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            sensors = [
                user_input[CONF_TO_GRID_SENSOR],
                user_input[CONF_CHARGE_SENSOR],
                user_input[CONF_DISCHARGE_SENSOR],
                *user_input[CONF_PRODUCTION_SENSOR],
            ]
            if len(set(sensors)) != len(sensors):
                errors["base"] = "same_sensor"
            else:
                user_input[CONF_MODE] = MODE_COMBINED
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="PV mit Speicher"): selector.TextSelector(),
                vol.Required(CONF_PRODUCTION_SENSOR): ENERGY_SENSORS,
                vol.Required(CONF_TO_GRID_SENSOR): ENERGY_SENSOR,
                vol.Required(CONF_CHARGE_SENSOR): ENERGY_SENSOR,
                vol.Required(CONF_DISCHARGE_SENSOR): ENERGY_SENSOR,
                **_economics_schema_for(MODE_COMBINED, {}),
                **_startup_flat_only(),
            }
        )
        return self.async_show_form(step_id="combined", data_schema=schema, errors=errors)

    async def _async_step_generic(
        self, mode: str, default_name: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        if user_input is not None:
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
        return self.async_show_form(step_id=mode, data_schema=schema)

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
        if user_input is not None:
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
        return self.async_show_form(step_id="heatpump", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> "AmortizationOptionsFlow":
        return AmortizationOptionsFlow()



class AmortizationOptionsFlow(OptionsFlow):
    """Live-Werte nachträglich anpassen (Sensoren & Startgutschrift bleiben fix)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
