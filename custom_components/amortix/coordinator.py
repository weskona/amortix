"""Datenmanager: Basis-Mechanik + Modi Direktverbrauch / Speicher."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

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
    CONF_PRICE_ENTITY,
    CONF_PRODUCTION_SENSOR,
    CONF_ROUNDTRIP_ENTITY,
    CONF_TO_GRID_SENSOR,
    DOMAIN,
    EVALUATION_INTERVAL,
    INVALID_STATES,
    SAVE_DELAY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class MonotonicCounter:
    """Macht aus einem (ggf. resettenden) kWh-Zähler einen monoton steigenden Gesamtwert."""

    def __init__(self) -> None:
        self.raw_last: float | None = None
        self.total: float = 0.0

    def restore(self, raw_last: float | None, total: float) -> None:
        self.raw_last = raw_last
        self.total = total

    def update(self, reading: float) -> None:
        if self.raw_last is None:
            self.raw_last = reading
            return
        if reading < self.raw_last:
            if reading < self.raw_last * 0.1:  # echter Reset auf ~0
                self.total += max(reading, 0.0)
                self.raw_last = reading
            return
        self.total += reading - self.raw_last
        self.raw_last = reading


class BaseManager:
    """Gemeinsame Mechanik: Timer, Entitäts-Lesen, Persistenz, Kennzahlen."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}")

        self.total_savings: float = 0.0
        self.initial_credit: float = 0.0
        self.credit_breakdown: dict = {}  # Aufschlüsselung der Startgutschrift
        self.last_price: float | None = None
        self.last_feed_in: float | None = None
        self.last_investment: float | None = None
        self.start_time: str | None = None

        self._listeners: list[CALLBACK_TYPE] = []
        self._unsub_state: CALLBACK_TYPE | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------
    @property
    def config(self) -> dict:
        return {**self.entry.data, **self.entry.options}

    def _read_entity(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state and state.state not in INVALID_STATES:
            try:
                return float(state.state)
            except (ValueError, TypeError):
                pass
        return None

    @property
    def investment(self) -> float | None:
        value = self._read_entity(self.config.get(CONF_INVESTMENT_ENTITY))
        if value is not None:
            self.last_investment = value
            return value
        return self.last_investment

    def _current_price(self) -> float | None:
        value = self._read_entity(self.config.get(CONF_PRICE_ENTITY))
        if value is not None:
            self.last_price = value
            return value
        return self.last_price

    def _current_feed_in(self) -> float:
        entity_id = self.config.get(CONF_FEED_IN_ENTITY)
        if not entity_id:
            return 0.0
        value = self._read_entity(entity_id)
        if value is not None:
            self.last_feed_in = value
            return value
        return self.last_feed_in if self.last_feed_in is not None else 0.0

    # ------------------------------------------------------------------
    # Lifecycle (Template-Methode)
    # ------------------------------------------------------------------
    async def async_start(self) -> None:
        data = await self.store.async_load()
        first_run = data is None
        if data:
            self.total_savings = data.get("total_savings", 0.0)
            self.initial_credit = data.get("initial_credit", 0.0)
            self.credit_breakdown = data.get("credit_breakdown", {})
            self.last_price = data.get("last_price")
            self.last_feed_in = data.get("last_feed_in")
            self.last_investment = data.get("last_investment")
            self.start_time = data.get("start_time")
            self._restore_counters(data)

        if not self.start_time:
            self.start_time = dt_util.utcnow().isoformat()

        counters = self._counters()
        for entity_id, counter in counters.items():
            self._seed(entity_id, counter)

        if first_run:
            self.initial_credit = self._compute_initial_credit()
            self.total_savings = self.initial_credit

        self._unsub_state = async_track_state_change_event(
            self.hass, list(counters.keys()), self._handle_event
        )
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_evaluate, timedelta(seconds=EVALUATION_INTERVAL)
        )
        self._schedule_save()

    def _seed(self, entity_id: str, counter: MonotonicCounter) -> None:
        if counter.raw_last is not None:
            return
        state = self.hass.states.get(entity_id)
        if state and state.state not in INVALID_STATES:
            try:
                counter.raw_last = float(state.state)
            except (ValueError, TypeError):
                pass

    @callback
    def async_stop(self) -> None:
        if self._unsub_state:
            self._unsub_state()
            self._unsub_state = None
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

    # ------------------------------------------------------------------
    def add_listener(self, cb: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(cb)

        def _remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return _remove

    @callback
    def _notify(self) -> None:
        for cb in self._listeners:
            cb()

    @callback
    def _handle_event(self, event: Event) -> None:
        new_state: State | None = event.data.get("new_state")
        if new_state is None or new_state.state in INVALID_STATES:
            return
        try:
            reading = float(new_state.state)
        except (ValueError, TypeError):
            return
        counter = self._counters().get(event.data.get("entity_id"))
        if counter is not None:
            counter.update(reading)

    # ------------------------------------------------------------------
    @callback
    def _schedule_save(self) -> None:
        self.store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict:
        data = {
            "total_savings": self.total_savings,
            "initial_credit": self.initial_credit,
            "credit_breakdown": self.credit_breakdown,
            "last_price": self.last_price,
            "last_feed_in": self.last_feed_in,
            "last_investment": self.last_investment,
            "start_time": self.start_time,
        }
        data.update(self._extra_save())
        return data

    # ------------------------------------------------------------------
    # Gemeinsame Kennzahlen
    # ------------------------------------------------------------------
    @property
    def progress(self) -> float | None:
        inv = self.investment
        if not inv or inv <= 0:
            return None
        return min(self.total_savings / inv * 100.0, 100.0)

    @property
    def remaining(self) -> float | None:
        inv = self.investment
        if inv is None:
            return None
        return max(inv - self.total_savings, 0.0)

    @property
    def elapsed_days(self) -> float:
        if not self.start_time:
            return 0.0
        start = dt_util.parse_datetime(self.start_time)
        if start is None:
            return 0.0
        return max((dt_util.utcnow() - start).total_seconds() / 86400.0, 0.0)

    @property
    def daily_average(self) -> float | None:
        net = self.total_savings - self.initial_credit
        days = self.elapsed_days
        if days < 0.5 or net <= 0:
            return None
        return net / days

    @property
    def remaining_days(self) -> float | None:
        remaining = self.remaining
        if remaining is None:
            return None
        if remaining <= 0:
            return 0.0
        avg = self.daily_average
        if not avg or avg <= 0:
            return None
        return remaining / avg

    @property
    def payback_date(self):
        rd = self.remaining_days
        if rd is None:
            return None
        return dt_util.utcnow() + timedelta(days=rd)

    # ------------------------------------------------------------------
    # Von Subklassen zu implementieren
    # ------------------------------------------------------------------
    def _counters(self) -> dict[str, MonotonicCounter]:
        raise NotImplementedError

    def _restore_counters(self, data: dict) -> None:
        raise NotImplementedError

    def _extra_save(self) -> dict:
        raise NotImplementedError

    @callback
    def _async_evaluate(self, now=None) -> None:
        raise NotImplementedError

    def _compute_initial_credit(self) -> float:
        raise NotImplementedError

    def _initial_rates(self) -> tuple[float, float]:
        """(Strompreis, Einspeisevergütung) für die Startgutschrift – leer = Live-Wert."""
        cfg = self.config
        price = float(cfg.get(CONF_INITIAL_PRICE, 0) or 0)
        if price <= 0:
            price = self._current_price() or 0.0
        feed_in = float(cfg.get(CONF_INITIAL_FEED_IN, 0) or 0)
        if feed_in <= 0:
            feed_in = self._current_feed_in()
        return price, feed_in


class DirectManager(BaseManager):
    """Direktverbrauch: Eigenverbrauch = Erzeugung − Einspeisung."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        # eine oder mehrere Erzeugungsquellen -> je ein Zähler, intern summiert
        self.prod_counters: dict[str, MonotonicCounter] = {
            eid: MonotonicCounter() for eid in self._production_ids()
        }
        self.grid = MonotonicCounter()
        self.credited_self: float = 0.0
        self.credited_grid: float = 0.0
        # aufgeteilte Einsparung (parallel zur Gesamtsumme)
        self.savings_self: float = 0.0     # durch Eigenverbrauch (Netzbezug gespart)
        self.savings_export: float = 0.0   # durch Einspeisevergütung
        # historische kWh, auf denen die Startgutschrift beruht (für konsistente Anzeige)
        self.base_self: float = 0.0
        self.base_export: float = 0.0
        self.base_produced: float = 0.0

    def _production_ids(self) -> list[str]:
        val = self.config[CONF_PRODUCTION_SENSOR]
        return list(val) if isinstance(val, (list, tuple)) else [val]

    def _prod_total(self) -> float:
        return sum(c.total for c in self.prod_counters.values())

    def _prod_raw(self) -> float:
        return sum((c.raw_last or 0.0) for c in self.prod_counters.values())

    def _counters(self) -> dict[str, MonotonicCounter]:
        result = dict(self.prod_counters)
        result[self.config[CONF_TO_GRID_SENSOR]] = self.grid
        return result

    def _restore_counters(self, data: dict) -> None:
        pc = data.get("prod_counters")
        if pc:
            for eid, counter in self.prod_counters.items():
                if eid in pc:
                    counter.restore(pc[eid][0], pc[eid][1])
        else:
            # alt: Einzel-Sensor (prod_raw_last/prod_total)
            ids = list(self.prod_counters)
            if ids:
                self.prod_counters[ids[0]].restore(
                    data.get("prod_raw_last"), data.get("prod_total", 0.0)
                )
        self.grid.restore(data.get("grid_raw_last"), data.get("grid_total", 0.0))
        self.credited_self = data.get("credited_self", 0.0)
        self.credited_grid = data.get("credited_grid", 0.0)
        self.base_self = data.get("base_self", 0.0)
        self.base_export = data.get("base_export", 0.0)
        self.base_produced = data.get("base_produced", 0.0)
        # aufgeteilte Einsparung; für alte Einträge aus der Startgutschrift seeden
        self.savings_self = data.get("savings_self")
        if self.savings_self is None:
            self.savings_self = self.credit_breakdown.get("netzbezug_eur", 0.0)
        self.savings_export = data.get("savings_export")
        if self.savings_export is None:
            self.savings_export = self.credit_breakdown.get("einspeisung_eur", 0.0)

    def _extra_save(self) -> dict:
        return {
            "prod_counters": {
                eid: [c.raw_last, c.total] for eid, c in self.prod_counters.items()
            },
            "grid_raw_last": self.grid.raw_last,
            "grid_total": self.grid.total,
            "credited_self": self.credited_self,
            "credited_grid": self.credited_grid,
            "base_self": self.base_self,
            "base_export": self.base_export,
            "base_produced": self.base_produced,
            "savings_self": self.savings_self,
            "savings_export": self.savings_export,
        }

    @property
    def total_produced(self) -> float:
        return self.base_produced + self._prod_total()

    @property
    def total_self_consumed(self) -> float:
        return self.base_self + self.credited_self

    @property
    def total_fed_in(self) -> float:
        return self.base_export + self.credited_grid

    @callback
    def _async_evaluate(self, now=None) -> None:
        price = self._current_price()
        if price is None:
            return
        raw_self = self._prod_total() - self.grid.total
        delta_self = raw_self - self.credited_self
        if delta_self > 0:
            value = delta_self * price
            self.total_savings += value
            self.savings_self += value
            self.credited_self = raw_self
        delta_grid = self.grid.total - self.credited_grid
        if delta_grid > 0:
            value = delta_grid * self._current_feed_in()
            self.total_savings += value
            self.savings_export += value
            self.credited_grid = self.grid.total
        if delta_self > 0 or delta_grid > 0:
            self._schedule_save()
            self._notify()

    def _compute_initial_credit(self) -> float:
        cfg = self.config
        euro = float(cfg.get(CONF_INITIAL_SAVINGS, 0) or 0)
        price, feed_in = self._initial_rates()
        if cfg.get(CONF_INITIAL_AUTO):
            self_kwh = max(self._prod_raw() - (self.grid.raw_last or 0.0), 0.0)
            export = self.grid.raw_last or 0.0
        else:
            self_kwh = float(cfg.get(CONF_INITIAL_SELF_KWH, 0) or 0)
            export = float(cfg.get(CONF_INITIAL_EXPORT_KWH, 0) or 0)
        self.base_self = self_kwh
        self.base_export = export
        self.base_produced = self_kwh + export
        self.savings_self = self_kwh * price
        self.savings_export = export * feed_in
        self.credit_breakdown = {
            "netzbezug_eur": round(self_kwh * price, 2),
            "einspeisung_eur": round(export * feed_in, 2),
            "pauschal_eur": round(euro, 2),
        }
        # pauschaler Euro-Betrag fließt in die Gesamtsumme, nicht in die Aufteilung
        return euro + self_kwh * price + export * feed_in


class StorageManager(BaseManager):
    """Speicher: Ersparnis = Entladung × Strompreis − Ladung × Einspeisevergütung."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self.charge = MonotonicCounter()
        self.discharge = MonotonicCounter()
        self.credited_charge: float = 0.0
        self.credited_discharge: float = 0.0
        self.base_charge: float = 0.0
        self.base_discharge: float = 0.0

    def _counters(self) -> dict[str, MonotonicCounter]:
        cfg = self.config
        return {
            cfg[CONF_CHARGE_SENSOR]: self.charge,
            cfg[CONF_DISCHARGE_SENSOR]: self.discharge,
        }

    def _restore_counters(self, data: dict) -> None:
        self.charge.restore(data.get("charge_raw_last"), data.get("charge_total", 0.0))
        self.discharge.restore(data.get("discharge_raw_last"), data.get("discharge_total", 0.0))
        self.credited_charge = data.get("credited_charge", 0.0)
        self.credited_discharge = data.get("credited_discharge", 0.0)
        self.base_charge = data.get("base_charge", 0.0)
        self.base_discharge = data.get("base_discharge", 0.0)

    def _extra_save(self) -> dict:
        return {
            "charge_raw_last": self.charge.raw_last,
            "charge_total": self.charge.total,
            "discharge_raw_last": self.discharge.raw_last,
            "discharge_total": self.discharge.total,
            "credited_charge": self.credited_charge,
            "credited_discharge": self.credited_discharge,
            "base_charge": self.base_charge,
            "base_discharge": self.base_discharge,
        }

    @property
    def total_charged(self) -> float:
        return self.base_charge + self.charge.total

    @property
    def total_discharged(self) -> float:
        return self.base_discharge + self.discharge.total

    @property
    def roundtrip(self) -> float | None:
        # vorhandenen η-Sensor bevorzugen
        entity_id = self.config.get(CONF_ROUNDTRIP_ENTITY)
        if entity_id:
            value = self._read_entity(entity_id)
            if value is not None:
                return value
        # sonst aus den Zählern berechnen (ohne Deckelung -> ehrlich, auch >100 % möglich,
        # solange noch nicht über mehrere volle Zyklen eingeschwungen)
        if self.total_charged <= 0:
            return None
        return self.total_discharged / self.total_charged * 100.0

    @callback
    def _async_evaluate(self, now=None) -> None:
        price = self._current_price()
        if price is None:
            return
        feed_in = self._current_feed_in()

        delta_dis = self.discharge.total - self.credited_discharge
        if delta_dis > 0:
            self.total_savings += delta_dis * price
            self.credited_discharge = self.discharge.total

        # entgangene Einspeisung: geladene Energie hätte eingespeist werden können
        delta_chg = self.charge.total - self.credited_charge
        if delta_chg > 0:
            self.total_savings -= delta_chg * feed_in
            self.credited_charge = self.charge.total

        if delta_dis > 0 or delta_chg > 0:
            self._schedule_save()
            self._notify()

    def _compute_initial_credit(self) -> float:
        cfg = self.config
        euro = float(cfg.get(CONF_INITIAL_SAVINGS, 0) or 0)
        price, feed_in = self._initial_rates()
        if cfg.get(CONF_INITIAL_AUTO):
            discharge = self.discharge.raw_last or 0.0
            charge = self.charge.raw_last or 0.0
        else:
            discharge = float(cfg.get(CONF_INITIAL_DISCHARGE_KWH, 0) or 0)
            charge = float(cfg.get(CONF_INITIAL_CHARGE_KWH, 0) or 0)
        self.base_discharge = discharge
        self.base_charge = charge
        benefit = discharge * price - charge * feed_in
        self.credit_breakdown = {
            "entladung_eur": round(discharge * price, 2),
            "entgangene_einspeisung_eur": round(-charge * feed_in, 2),
            "pauschal_eur": round(euro, 2),
        }
        return euro + max(benefit, 0.0)
