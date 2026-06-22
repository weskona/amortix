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
    CONF_FEED_IN_ENTITY,
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
    CONF_PRICE_ENTITY,
    CONF_PRODUCTION_SENSOR,
    CONF_ROUNDTRIP_ENTITY,
    CONF_TO_GRID_SENSOR,
    DOMAIN,
    MODE_DIRECT,
    MODE_STORAGE,
)

ENERGY_SENSOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
)
ENERGY_SENSORS = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="energy", multiple=True)
)
VALUE_ENTITY = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "input_number"])
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
            step_id="user", menu_options=[MODE_DIRECT, MODE_STORAGE]
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
            return self.async_create_entry(title="", data=user_input)
        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(_economics_schema(current))
        return self.async_show_form(step_id="init", data_schema=schema)
