"""Seitenleisten-Panel fuer Amortix: Registrierung, statische Datei und Websocket-API.

Home-Assistant-Importe erfolgen erst in den Funktionen, damit das Paket auch
ohne Home Assistant importierbar (und testbar) bleibt.
"""
from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from .const import DOMAIN, SIGNAL_MANAGERS_CHANGED
from .summary import build_summary

PANEL_URL_PATH = "amortix"
PANEL_COMPONENT = "amortix-panel"
STATIC_URL = "/amortix_panel"
FRONTEND_DIR = Path(__file__).parent / "frontend"
PANEL_FILE = FRONTEND_DIR / "amortix-panel.js"
FONT_FILE = FRONTEND_DIR / "outfit.woff2"
REFRESH_SECONDS = 60
_FLAG = f"{DOMAIN}_panel_assets"      # Websocket + statische Datei (einmalig je Laufzeit)
_PANEL_FLAG = f"{DOMAIN}_panel_active"  # Sidebar-Eintrag (kommt und geht mit den Eintraegen)


def _entries(hass) -> list[tuple[str, str, str, object]]:
    result = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
        if manager is not None:
            result.append((entry.entry_id, entry.title, entry.data.get("mode", "direct"), manager))
    return result


def summary(hass) -> dict:
    return build_summary(_entries(hass))


async def async_register_panel(hass) -> None:
    """Panel und Websocket-Befehle registrieren (idempotent)."""
    if hass.data.get(_PANEL_FLAG):
        return
    from homeassistant.components import panel_custom, websocket_api

    url = f"{STATIC_URL}/amortix-panel.js"
    if not hass.data.get(_FLAG):
        hass.data[_FLAG] = True
        _register_websocket(hass, websocket_api)
        try:
            from homeassistant.components.http import StaticPathConfig

            await hass.http.async_register_static_paths(
                [
                    StaticPathConfig(url, str(PANEL_FILE), False),
                    StaticPathConfig(f"{STATIC_URL}/outfit.woff2", str(FONT_FILE), True),
                ]
            )
        except ImportError:  # aeltere Home-Assistant-Versionen
            hass.http.register_static_path(url, str(PANEL_FILE), False)
            hass.http.register_static_path(f"{STATIC_URL}/outfit.woff2", str(FONT_FILE), True)
    hass.data[_PANEL_FLAG] = True

    version = (await _manifest_version(hass)) or "0"
    await panel_custom.async_register_panel(
        hass,
        webcomponent_name=PANEL_COMPONENT,
        frontend_url_path=PANEL_URL_PATH,
        module_url=f"{url}?v={version}",
        sidebar_title="Amortix",
        sidebar_icon="mdi:cash-clock",
        require_admin=False,
        config={},
    )


async def async_unregister_panel(hass) -> None:
    """Panel entfernen, wenn der letzte Amortix-Eintrag entladen wurde."""
    if not hass.data.get(_PANEL_FLAG) or hass.data.get(DOMAIN):
        return
    from homeassistant.components import frontend

    frontend.async_remove_panel(hass, PANEL_URL_PATH)
    hass.data[_PANEL_FLAG] = False


async def _manifest_version(hass) -> str | None:
    try:
        from homeassistant.loader import async_get_integration

        return (await async_get_integration(hass, DOMAIN)).version.__str__()
    except Exception:  # noqa: BLE001 - nur Cache-Buster, darf nie scheitern
        return None


def _register_websocket(hass, websocket_api) -> None:
    import voluptuous as vol
    from homeassistant.core import callback
    from homeassistant.helpers.dispatcher import async_dispatcher_connect
    from homeassistant.helpers.event import async_track_time_interval

    @websocket_api.websocket_command({vol.Required("type"): "amortix/summary"})
    @callback
    def ws_summary(hass_, connection, msg) -> None:
        connection.send_result(msg["id"], summary(hass_))

    @websocket_api.websocket_command({vol.Required("type"): "amortix/subscribe"})
    @callback
    def ws_subscribe(hass_, connection, msg) -> None:
        listener_unsubs: list = []

        @callback
        def _send(*_args) -> None:
            connection.send_message(websocket_api.event_message(msg["id"], summary(hass_)))

        @callback
        def _rebind(*_args) -> None:
            for unsub in listener_unsubs:
                unsub()
            listener_unsubs.clear()
            for _eid, _title, _mode, manager in _entries(hass_):
                listener_unsubs.append(manager.add_listener(_send))
            _send()

        unsub_signal = async_dispatcher_connect(hass_, SIGNAL_MANAGERS_CHANGED, _rebind)
        unsub_timer = async_track_time_interval(
            hass_, _send, timedelta(seconds=REFRESH_SECONDS)
        )

        @callback
        def _cleanup() -> None:
            unsub_signal()
            unsub_timer()
            for unsub in listener_unsubs:
                unsub()
            listener_unsubs.clear()

        connection.subscriptions[msg["id"]] = _cleanup
        connection.send_result(msg["id"])
        _rebind()

    websocket_api.async_register_command(hass, ws_summary)
    websocket_api.async_register_command(hass, ws_subscribe)
