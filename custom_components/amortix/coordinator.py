"""Datenmanager: Basis-Mechanik + Modi Direktverbrauch / Speicher."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, State, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

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
    CONF_OWN_PRICE_ENTITY,
    CONF_PRICE_ENTITY,
    CONF_PRODUCTION_SENSOR,
    CONF_REFERENCE_PRICE_ENTITY,
    CONF_ROUNDTRIP_ENTITY,
    CONF_STORAGES,
    CONF_TO_GRID_SENSOR,
    DOMAIN,
    EVALUATION_INTERVAL,
    INVALID_STATES,
    SAVE_DELAY,
    SIGNAL_MANAGERS_CHANGED,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


# Ein Wert unter diesem Anteil des letzten Stands gilt als Reset-/Glitch-Kandidat;
# kleinere Rücksprünge (Rundung, Korrekturen) werden ignoriert.
RESET_DROP_RATIO = 0.5
# So viele Updates nach einer Reset-Bestätigung wird ein Sprung zurück auf den
# alten Stand noch als Glitch erkannt und die Buchung zurückgenommen.
RESET_GUARD_UPDATES = 3


def _breakdown_line(name: str, mode: str | None, investment: float | None, savings: float) -> dict:
    progress = None
    if investment and investment > 0:
        progress = round(max(0.0, min(savings / investment * 100.0, 100.0)), 1)
    return {
        "name": name,
        "mode": mode,
        "investment": round(investment, 2) if investment is not None else None,
        "savings": round(savings, 2),
        "progress": progress,
        "remaining": round(max(investment - savings, 0.0), 2) if investment is not None else None,
    }


def _is_cent_unit(unit: str | None) -> bool:
    """True für Preis-Einheiten in Cent (z. B. 'ct/kWh', 'c/kWh', 'Cent/kWh')."""
    if not unit:
        return False
    unit = unit.strip().lower()
    return unit.startswith(("ct", "cent", "c/"))


class MonotonicCounter:
    """Macht aus einem (ggf. resettenden) kWh-Zähler einen monoton steigenden Gesamtwert."""

    def __init__(self) -> None:
        self.raw_last: float | None = None
        self.total: float = 0.0
        # Ein echter Reset und ein "0 statt unavailable"-Glitch (Cloud-
        # Integrationen wie Alpha ESS melden das theoretisch so) sehen beim
        # ersten niedrigen Wert identisch aus. Ein Reset wird daher erst
        # bestätigt, wenn ein zweiter niedriger Wert folgt, der nicht weiter
        # fällt. Erholt sich der Zähler dazwischen (Glitch), wird der Kandidat
        # verworfen, ohne Energie doppelt zu zählen.
        self._reset_candidate: float | None = None
        # Hält der Glitch länger (z. B. zweimal "0" hintereinander) und wurde
        # deshalb ein Reset bestätigt, merkt sich der Guard (alter Stand,
        # gebuchte kWh, Rest-Updates). Springt der Zähler dann zurück auf den
        # alten Stand, wird die irrtümliche Buchung zurückgenommen.
        self._guard: tuple[float, float, int] | None = None

    def restore(self, raw_last: float | None, total: float) -> None:
        self.raw_last = raw_last
        self.total = total

    @property
    def initial(self) -> float:
        """Zählerstand beim ersten Lesen (0, solange der Zähler noch nie gelesen wurde)."""
        if self.raw_last is None:
            return 0.0
        return max(self.raw_last - self.total, 0.0)

    def update(self, reading: float) -> None:
        if self.raw_last is None:
            self.raw_last = reading
            return

        if self._guard is not None:
            old_raw, added, ttl = self._guard
            if reading >= old_raw:
                # Der "Reset" war ein Glitch: alles seit der Bestätigung
                # Gebuchte (= raw_last) zurücknehmen, ab dem alten Stand weiterzählen.
                self.total += (reading - old_raw) - self.raw_last
                self.raw_last = reading
                self._guard = None
                self._reset_candidate = None
                return
            self._guard = (old_raw, added, ttl - 1) if ttl > 1 else None

        if reading < self.raw_last:
            if reading < self.raw_last * RESET_DROP_RATIO:  # möglicher Reset
                candidate = self._reset_candidate
                if candidate is None or reading < candidate:
                    self._reset_candidate = reading
                else:
                    # zweiter niedriger Wert, der nicht weiter fällt: Reset
                    self.total += max(reading, 0.0)
                    self._guard = (self.raw_last, max(reading, 0.0), RESET_GUARD_UPDATES)
                    self.raw_last = reading
                    self._reset_candidate = None
            else:
                # kleiner Rücksprung bzw. teilweise Erholung: ignorieren
                self._reset_candidate = None
            return
        self._reset_candidate = None
        self.total += reading - self.raw_last
        self.raw_last = reading


class MetricsMixin:
    """Fortschritt, Restbetrag und Prognose aus investment / total_savings / initial_credit.

    Wird von Managern, Gerätesichten und der Gesamtübersicht genutzt. Die
    einbindende Klasse stellt `investment`, `total_savings`, `initial_credit`
    und `start_time` bereit.
    """

    @property
    def progress(self) -> float | None:
        inv = self.investment
        if not inv or inv <= 0:
            return None
        # Bei Speicher-Betrieb kann total_savings vorübergehend unter
        # initial_credit (sogar unter 0) fallen, wenn in einer Auswertung
        # geladen, aber nicht entladen wird und die Einspeisevergütung > 0
        # ist (entgangene Einspeisung wird abgezogen, siehe
        # StorageManager._async_evaluate). Ohne Untergrenze würde die
        # Fortschritts-% dann negativ, was für eine Amortisationsanzeige
        # keinen Sinn ergibt.
        return max(0.0, min(self.total_savings / inv * 100.0, 100.0))

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


class BaseManager(MetricsMixin):
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
        # Startgutschrift wartet noch auf Sensoren/Preise (beim ersten Start nicht verfügbar)
        self.initial_pending: bool = False

        self._listeners: list[CALLBACK_TYPE] = []
        self._unsub_state: CALLBACK_TYPE | None = None
        self._unsub_timer: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------
    @property
    def config(self) -> dict:
        return {**self.entry.data, **self.entry.options}

    def _read_entity(self, entity_id: str | None, rate: bool = False) -> float | None:
        """Entität als Zahl lesen; rate=True rechnet Cent-Einheiten in € um."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state and state.state not in INVALID_STATES:
            try:
                value = float(state.state)
            except (ValueError, TypeError):
                return None
            if rate and _is_cent_unit(state.attributes.get("unit_of_measurement")):
                value /= 100.0
            return value
        return None

    @property
    def investment(self) -> float | None:
        value = self._read_entity(self.config.get(CONF_INVESTMENT_ENTITY))
        if value is not None:
            self.last_investment = value
            return value
        return self.last_investment

    def _current_price(self) -> float | None:
        value = self._read_entity(self.config.get(CONF_PRICE_ENTITY), rate=True)
        if value is not None:
            self.last_price = value
            return value
        return self.last_price

    def _current_feed_in(self) -> float:
        entity_id = self.config.get(CONF_FEED_IN_ENTITY)
        if not entity_id:
            return 0.0
        value = self._read_entity(entity_id, rate=True)
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
            self.initial_pending = data.get("initial_pending", False)
            self._restore_counters(data)

        if not self.start_time:
            self.start_time = dt_util.utcnow().isoformat()

        counters = self._counters()
        for entity_id, counter in counters.items():
            self._seed(entity_id, counter)

        if first_run:
            if self._initial_ready():
                self._apply_initial_credit()
            else:
                # Sensoren/Preise sind noch nicht verfügbar: nicht still mit 0 starten,
                # sondern die Startgutschrift nachholen, sobald alles lesbar ist.
                self.initial_pending = True
                _LOGGER.warning(
                    "Amortix %s: Startgutschrift wird berechnet, sobald alle "
                    "Sensoren und Preise verfügbar sind",
                    self.entry.title,
                )

        self._unsub_state = async_track_state_change_event(
            self.hass, list(counters.keys()), self._handle_event
        )
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_tick, timedelta(seconds=EVALUATION_INTERVAL)
        )
        self._schedule_save()

    def _apply_initial_credit(self) -> None:
        credit = self._compute_initial_credit()
        self.initial_credit = credit
        self.total_savings += credit
        self.initial_pending = False
        self._schedule_save()

    def _initial_ready(self) -> bool:
        """Alles lesbar, was die Startgutschrift braucht? Sonst wäre sie still 0."""
        cfg = self.config
        if float(cfg.get(CONF_INITIAL_PRICE, 0) or 0) <= 0 and self._current_price() is None:
            return False
        feed_in_entity = cfg.get(CONF_FEED_IN_ENTITY)
        if (
            feed_in_entity
            and float(cfg.get(CONF_INITIAL_FEED_IN, 0) or 0) <= 0
            and self._read_entity(feed_in_entity) is None
            and self.last_feed_in is None
        ):
            return False
        return self._initial_sources_ready()

    @callback
    def _async_tick(self, now=None) -> None:
        if self.initial_pending and self._initial_ready():
            self._apply_initial_credit()
            self._notify()
        self._async_evaluate(now)

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
            "initial_pending": self.initial_pending,
        }
        data.update(self._extra_save())
        return data

    def breakdown(self) -> list[dict]:
        """Aufschlüsselung für die Gesamtübersicht (Standard: eine Zeile je Eintrag)."""
        return [_breakdown_line(self.entry.title, self.entry.data.get("mode"), self.investment, self.total_savings)]

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

    def _initial_sources_ready(self) -> bool:
        """Subklasse: sind die für die automatische Startgutschrift nötigen Zähler gelesen?"""
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

    def _prod_initial(self) -> float:
        return sum(c.initial for c in self.prod_counters.values())

    def _initial_sources_ready(self) -> bool:
        if not self.config.get(CONF_INITIAL_AUTO):
            return True
        return self.grid.raw_last is not None and all(
            c.raw_last is not None for c in self.prod_counters.values()
        )

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
            # Stand beim ersten Lesen (raw_last - total), falls ein Sensor erst
            # nach dem Start verfügbar wurde
            export = self.grid.initial
            self_kwh = max(self._prod_initial() - export, 0.0)
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

    def _initial_sources_ready(self) -> bool:
        if not self.config.get(CONF_INITIAL_AUTO):
            return True
        return self.charge.raw_last is not None and self.discharge.raw_last is not None

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
            discharge = self.discharge.initial
            charge = self.charge.initial
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
        # wie im laufenden Betrieb (_async_evaluate) darf die Bilanz negativ sein,
        # damit Summe und Aufschlüsselung übereinstimmen
        return euro + benefit


class DeltaManager(BaseManager):
    """Basis für Modi, die jeden Zähler einzeln und inkrementell bewerten.

    Jede kWh-Änderung eines Zählers wird zum jeweils aktuellen Preis bewertet
    (Summe über alle Zähler). Es gibt keine Differenz zwischen Zählern, daher
    ist die Rechnung unempfindlich gegen zeitlich versetzte Sensor-Updates.
    """

    # key -> Config-Key des/der Sensoren
    SENSORS: dict[str, str] = {}
    # name -> (Config-Key der Preis-Entität, Pflicht?)
    RATES: dict[str, tuple[str, bool]] = {}
    # Teilsummen der Ersparnis
    PARTS: tuple[str, ...] = ()

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry)
        self.groups: dict[str, dict[str, MonotonicCounter]] = {
            key: {eid: MonotonicCounter() for eid in ids}
            for key, ids in self._sensor_map().items()
        }
        self.credited: dict[str, float] = {k: 0.0 for k in self.groups}
        self.base: dict[str, float] = {k: 0.0 for k in self.groups}
        self.parts: dict[str, float] = {p: 0.0 for p in self.PARTS}
        self.last_rates: dict[str, float] = {}

    def _ids(self, conf: str) -> list[str]:
        val = self.config[conf]
        return list(val) if isinstance(val, (list, tuple)) else [val]

    def _sensor_map(self) -> dict[str, list[str]]:
        """Zähler-Gruppen: key -> Entity-IDs (Standard aus SENSORS; Subklassen überschreiben)."""
        return {key: self._ids(conf) for key, conf in self.SENSORS.items()}

    # ------------------------------------------------------------------
    def total(self, key: str) -> float:
        """Seit Start gezählte kWh (ohne Startwert)."""
        return sum(c.total for c in self.groups[key].values())

    def kwh(self, key: str) -> float:
        """Gesamt-kWh inklusive Startwert aus der automatischen Startgutschrift."""
        return self.base[key] + self.total(key)

    def _counters(self) -> dict[str, MonotonicCounter]:
        return {
            eid: counter
            for group in self.groups.values()
            for eid, counter in group.items()
        }

    def _restore_counters(self, data: dict) -> None:
        saved = data.get("groups", {})
        for key, group in self.groups.items():
            for eid, counter in group.items():
                if eid in saved.get(key, {}):
                    counter.restore(*saved[key][eid])
        for key in self.groups:
            self.credited[key] = data.get("credited", {}).get(key, 0.0)
            self.base[key] = data.get("base", {}).get(key, 0.0)
        for part in self.parts:
            self.parts[part] = data.get("parts", {}).get(part, 0.0)
        self.last_rates = dict(data.get("last_rates", {}))

    def _extra_save(self) -> dict:
        return {
            "groups": {
                key: {eid: [c.raw_last, c.total] for eid, c in group.items()}
                for key, group in self.groups.items()
            },
            "credited": dict(self.credited),
            "base": dict(self.base),
            "parts": dict(self.parts),
            "last_rates": dict(self.last_rates),
        }

    # ------------------------------------------------------------------
    def _rates(self) -> dict[str, float] | None:
        """Aktuelle Preise (live gelesen, Cent -> €); None, wenn ein Pflichtpreis fehlt."""
        rates: dict[str, float] = {}
        for name, (conf, required) in self.RATES.items():
            value = self._read_entity(self.config.get(conf), rate=True)
            if value is not None:
                self.last_rates[name] = value
            else:
                value = self.last_rates.get(name)
            if value is None:
                if required:
                    return None
                value = 0.0
            rates[name] = value
        return rates

    def _value(self, key: str, delta: float, rates: dict[str, float]) -> list[tuple[str, float]]:
        """Wert von `delta` kWh des Zählers `key` als Liste (Teilsumme, Euro)."""
        raise NotImplementedError

    @callback
    def _async_evaluate(self, now=None) -> None:
        rates = self._rates()
        if rates is None:
            return
        changed = False
        for key in self.groups:
            total = self.total(key)
            delta = total - self.credited[key]
            if delta <= 0:
                continue
            for part, euros in self._value(key, delta, rates):
                self.total_savings += euros
                self.parts[part] += euros
            self.credited[key] = total
            changed = True
        if changed:
            self._schedule_save()
            self._notify()

    # ------------------------------------------------------------------
    def _initial_sources_ready(self) -> bool:
        if not self.config.get(CONF_INITIAL_AUTO):
            return True
        return all(c.raw_last is not None for c in self._counters().values())

    def _initial_ready(self) -> bool:
        return self._rates() is not None and self._initial_sources_ready()

    def _compute_initial_credit(self) -> float:
        euro = float(self.config.get(CONF_INITIAL_SAVINGS, 0) or 0)
        auto = 0.0
        if self.config.get(CONF_INITIAL_AUTO):
            rates = self._rates() or {}
            for key, group in self.groups.items():
                self.base[key] = sum(c.initial for c in group.values())
                for part, euros in self._value(key, self.base[key], rates):
                    auto += euros
                    self.parts[part] += euros
        self.credit_breakdown = {
            "zaehlerstaende_eur": round(auto, 2),
            "pauschal_eur": round(euro, 2),
        }
        return euro + auto

    # ------------------------------------------------------------------
    def attributes(self) -> dict:
        """Zusatzattribute des Gesamt-Ersparnis-Sensors (Subklassen ergänzen)."""
        attrs = {
            "startgutschrift_eur": round(self.initial_credit, 2),
            "einsparung_seit_start_eur": round(self.total_savings - self.initial_credit, 2),
            "inbetriebnahme": self.start_time,
        }
        for key, value in self.credit_breakdown.items():
            attrs[f"startgutschrift_{key}"] = value
        return attrs


class GenericManager(DeltaManager):
    """Wallbox / Allgemein: kWh × (Vergleichspreis − eigener Preis)."""

    SENSORS = {"energy": CONF_ENERGY_SENSOR}
    RATES = {
        "reference": (CONF_REFERENCE_PRICE_ENTITY, True),
        "own": (CONF_OWN_PRICE_ENTITY, False),
    }
    PARTS = ("total",)

    def _value(self, key, delta, rates):
        return [("total", delta * (rates["reference"] - rates["own"]))]

    def attributes(self) -> dict:
        attrs = super().attributes()
        attrs["energie_kwh"] = round(self.kwh("energy"), 3)
        return attrs


class HeatPumpManager(DeltaManager):
    """Wärmepumpe: Wärme × Referenzpreis − Strom × Strompreis."""

    SENSORS = {"heat": CONF_HEAT_SENSOR, "electric": CONF_ELECTRIC_SENSOR}
    RATES = {
        "reference": (CONF_REFERENCE_PRICE_ENTITY, True),
        "price": (CONF_PRICE_ENTITY, True),
    }
    PARTS = ("heat", "electric")

    def _value(self, key, delta, rates):
        if key == "heat":
            return [("heat", delta * rates["reference"])]
        return [("electric", -delta * rates["price"])]

    @property
    def cop(self) -> float | None:
        """Jahresarbeitszahl (Wärme ÷ Strom) über die gesamte Laufzeit."""
        electric = self.kwh("electric")
        if electric <= 0:
            return None
        return self.kwh("heat") / electric

    def attributes(self) -> dict:
        attrs = super().attributes()
        attrs["waerme_kwh"] = round(self.kwh("heat"), 3)
        attrs["strom_kwh"] = round(self.kwh("electric"), 3)
        return attrs


class CombinedManager(DeltaManager):
    """PV + Speicher: (Erzeugung − Einspeisung − Ladung + Entladung) × Preis + Einspeisung × Vergütung.

    Jede Komponente wird einzeln zum aktuellen Preis bewertet. Dadurch ist auch
    Netzladung (Tarif-Arbitrage) korrekt abgebildet: Ladung kostet beim Laden,
    Entladung bringt beim Entladen den dann gültigen Preis.
    """

    SENSORS = {
        "production": CONF_PRODUCTION_SENSOR,
        "export": CONF_TO_GRID_SENSOR,
        "charge": CONF_CHARGE_SENSOR,
        "discharge": CONF_DISCHARGE_SENSOR,
    }
    RATES = {
        "price": (CONF_PRICE_ENTITY, True),
        "feed_in": (CONF_FEED_IN_ENTITY, False),
    }
    PARTS = ("self", "export")

    def _value(self, key, delta, rates):
        price = rates["price"]
        if key == "production":
            return [("self", delta * price)]
        if key == "export":
            return [("self", -delta * price), ("export", delta * rates["feed_in"])]
        if key == "charge":
            return [("self", -delta * price)]
        return [("self", delta * price)]  # discharge

    @property
    def total_self_consumed(self) -> float:
        """Erzeugung − Einspeisung (enthält die in den Speicher geladene Energie)."""
        return self.kwh("production") - self.kwh("export")

    @property
    def roundtrip(self) -> float | None:
        charged = self.kwh("charge")
        if charged <= 0:
            return None
        return self.kwh("discharge") / charged * 100.0

    def attributes(self) -> dict:
        attrs = super().attributes()
        attrs.update(
            erzeugung_kwh=round(self.kwh("production"), 3),
            einspeisung_kwh=round(self.kwh("export"), 3),
            ladung_kwh=round(self.kwh("charge"), 3),
            entladung_kwh=round(self.kwh("discharge"), 3),
        )
        return attrs


class DeviceView(MetricsMixin):
    """Sicht auf ein einzelnes Gerät einer Anlage (eigene Kosten, Ersparnis, Prognose)."""

    def __init__(self, manager: "PlantManager", key: str) -> None:
        self.manager = manager
        self.key = key

    @property
    def name(self) -> str:
        return self.manager.device_name(self.key)

    @property
    def investment(self) -> float | None:
        return self.manager.device_investment(self.key)

    @property
    def total_savings(self) -> float:
        return self.manager.dev_savings[self.key]

    @property
    def initial_credit(self) -> float:
        return self.manager.dev_initial[self.key]

    @property
    def start_time(self) -> str | None:
        return self.manager.start_time

    def add_listener(self, cb: CALLBACK_TYPE) -> CALLBACK_TYPE:
        return self.manager.add_listener(cb)


class PlantManager(DeltaManager):
    """Anlage: beliebig viele Erzeuger und Speicher am selben Netzanschluss.

    Gesamt: (Σ Erzeugung − Einspeisung − Σ Ladung + Σ Entladung) × Strompreis
            + Einspeisung × Vergütung

    Aufteilung je Gerät (Summe = Gesamt):
      Erzeuger-Pool = (Σ Erzeugung − Einspeisung − Σ Ladung) × Strompreis
                      + (Einspeisung + Σ Ladung) × Vergütung,
                      verteilt nach Anteil an der Erzeugung
      Speicher      = Entladung × Strompreis − Ladung × Vergütung
    """

    RATES = {
        "price": (CONF_PRICE_ENTITY, True),
        "feed_in": (CONF_FEED_IN_ENTITY, False),
    }
    PARTS = ("self", "export")

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        cfg = self.config
        self.devices: list[dict] = list(cfg.get(CONF_DEVICES, []))
        self.storages: list[dict] = list(cfg.get(CONF_STORAGES, []))
        self.prod_keys = [f"prod{i}" for i in range(len(self.devices))]
        self.sto_keys = [f"sto{j}" for j in range(len(self.storages))]
        super().__init__(hass, entry)
        self.dev_savings: dict[str, float] = {k: 0.0 for k in self.prod_keys + self.sto_keys}
        self.dev_initial: dict[str, float] = dict(self.dev_savings)
        self.last_inv: dict[str, float] = {}
        self.views: dict[str, DeviceView] = {
            k: DeviceView(self, k) for k in self.prod_keys + self.sto_keys
        }

    # ------------------------------------------------------------------ Geräte
    def _spec(self, key: str) -> dict:
        i = int(key[4:] if key.startswith("prod") else key[3:])
        return self.devices[i] if key.startswith("prod") else self.storages[i]

    def device_name(self, key: str) -> str:
        return self._spec(key).get("name") or key

    def device_investment(self, key: str) -> float | None:
        value = self._read_entity(self._spec(key).get(CONF_INVESTMENT_ENTITY))
        if value is not None:
            self.last_inv[key] = value
            return value
        return self.last_inv.get(key)

    @property
    def investment(self) -> float | None:
        values = [self.device_investment(k) for k in self.prod_keys + self.sto_keys]
        known = [v for v in values if v is not None]
        return sum(known) if known else None

    def _sensor_map(self) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        for i, dev in enumerate(self.devices):
            mapping[f"prod{i}"] = [dev["sensor"]]
        mapping["export"] = [self.config[CONF_TO_GRID_SENSOR]]
        for j, st in enumerate(self.storages):
            mapping[f"chg{j}"] = [st[CONF_CHARGE_SENSOR]]
            mapping[f"dis{j}"] = [st[CONF_DISCHARGE_SENSOR]]
        return mapping

    # ------------------------------------------------------------------ Rechnung
    def _allocate(self, deltas: dict[str, float], rates: dict[str, float]):
        """kWh-Änderungen -> (Ersparnis je Gerät, Teilsummen)."""
        price, feed = rates["price"], rates["feed_in"]
        d_prod = {k: deltas.get(k, 0.0) for k in self.prod_keys}
        sum_p = sum(d_prod.values())
        d_exp = deltas.get("export", 0.0)
        d_chg = {j: deltas.get(f"chg{j}", 0.0) for j in range(len(self.storages))}
        d_dis = {j: deltas.get(f"dis{j}", 0.0) for j in range(len(self.storages))}
        sum_c, sum_d = sum(d_chg.values()), sum(d_dis.values())

        pool = (sum_p - d_exp - sum_c) * price + (d_exp + sum_c) * feed
        if sum_p > 0:
            shares = {k: d_prod[k] / sum_p for k in self.prod_keys}
        else:
            totals = {k: self.kwh(k) for k in self.prod_keys}
            total_sum = sum(totals.values())
            if total_sum > 0:
                shares = {k: totals[k] / total_sum for k in self.prod_keys}
            else:
                n = len(self.prod_keys) or 1
                shares = {k: 1.0 / n for k in self.prod_keys}

        incs = {k: pool * shares[k] for k in self.prod_keys}
        for j, key in enumerate(self.sto_keys):
            incs[key] = d_dis[j] * price - d_chg[j] * feed
        parts = {
            "self": (sum_p - d_exp - sum_c + sum_d) * price,
            "export": d_exp * feed,
        }
        return incs, parts

    @callback
    def _async_evaluate(self, now=None) -> None:
        rates = self._rates()
        if rates is None:
            return
        deltas = {}
        for key in self.groups:
            delta = self.total(key) - self.credited[key]
            if delta > 0:
                deltas[key] = delta
        if not deltas:
            return
        incs, parts = self._allocate(deltas, rates)
        for key, value in incs.items():
            self.dev_savings[key] += value
            self.total_savings += value
        for part, value in parts.items():
            self.parts[part] += value
        for key in deltas:
            self.credited[key] = self.total(key)
        self._schedule_save()
        self._notify()

    def _compute_initial_credit(self) -> float:
        euro = float(self.config.get(CONF_INITIAL_SAVINGS, 0) or 0)
        auto = 0.0
        if self.config.get(CONF_INITIAL_AUTO):
            rates = self._rates() or {"price": 0.0, "feed_in": 0.0}
            deltas = {}
            for key, group in self.groups.items():
                self.base[key] = sum(c.initial for c in group.values())
                deltas[key] = self.base[key]
            incs, parts = self._allocate(deltas, rates)
            for key, value in incs.items():
                self.dev_initial[key] = value
                self.dev_savings[key] += value
                auto += value
            for part, value in parts.items():
                self.parts[part] += value
        # Startwert je Gerät (bisher aufgelaufene Ersparnis bei bereits laufenden Anlagen)
        device_flat = 0.0
        for key in self.prod_keys + self.sto_keys:
            flat = float(self._spec(key).get("initial_savings", 0) or 0)
            if flat:
                self.dev_initial[key] += flat
                self.dev_savings[key] += flat
                device_flat += flat
        self.credit_breakdown = {
            "zaehlerstaende_eur": round(auto, 2),
            "geraete_pauschal_eur": round(device_flat, 2),
            "pauschal_eur": round(euro, 2),
        }
        return euro + auto + device_flat

    # ------------------------------------------------------------------ Persistenz
    def _restore_counters(self, data: dict) -> None:
        super()._restore_counters(data)
        for key in self.dev_savings:
            self.dev_savings[key] = data.get("dev_savings", {}).get(key, 0.0)
            self.dev_initial[key] = data.get("dev_initial", {}).get(key, 0.0)
        self.last_inv = dict(data.get("last_inv", {}))

    def _extra_save(self) -> dict:
        data = super()._extra_save()
        data.update(
            dev_savings=dict(self.dev_savings),
            dev_initial=dict(self.dev_initial),
            last_inv=dict(self.last_inv),
        )
        return data

    # ------------------------------------------------------------------ Kennzahlen
    def kwh(self, key: str) -> float:
        """Zähler-Gesamtwert; production/charge/discharge summieren über alle Geräte."""
        if key == "production":
            return sum(super(PlantManager, self).kwh(k) for k in self.prod_keys)
        if key == "charge":
            return sum(super(PlantManager, self).kwh(f"chg{j}") for j in range(len(self.storages)))
        if key == "discharge":
            return sum(super(PlantManager, self).kwh(f"dis{j}") for j in range(len(self.storages)))
        return super().kwh(key)

    @property
    def total_self_consumed(self) -> float:
        return self.kwh("production") - self.kwh("export")

    @property
    def roundtrip(self) -> float | None:
        charged = self.kwh("charge")
        if charged <= 0:
            return None
        return self.kwh("discharge") / charged * 100.0

    @property
    def flat_credit(self) -> float:
        return float(self.credit_breakdown.get("pauschal_eur", 0.0))

    def breakdown(self) -> list[dict]:
        lines = [
            _breakdown_line(
                self.device_name(key),
                "pv" if key.startswith("prod") else "storage",
                self.device_investment(key),
                self.dev_savings[key],
            )
            for key in self.prod_keys + self.sto_keys
        ]
        if self.flat_credit:
            lines.append(_breakdown_line("Pauschale Startgutschrift", "flat", None, self.flat_credit))
        return lines

    def attributes(self) -> dict:
        attrs = super().attributes()
        attrs["geraete"] = self.breakdown()
        attrs["erzeugung_kwh"] = round(self.kwh("production"), 3)
        attrs["einspeisung_kwh"] = round(self.kwh("export"), 3)
        attrs["ladung_kwh"] = round(self.kwh("charge"), 3)
        attrs["entladung_kwh"] = round(self.kwh("discharge"), 3)
        return attrs


class OverviewManager(MetricsMixin):
    """Gesamtübersicht: fasst alle anderen Amortix-Einträge zusammen (inkl. Breakdown)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._listeners: list[CALLBACK_TYPE] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._unsub_signal: CALLBACK_TYPE | None = None

    async def async_start(self) -> None:
        self._unsub_signal = async_dispatcher_connect(
            self.hass, SIGNAL_MANAGERS_CHANGED, self._rebind
        )
        self._rebind()

    @callback
    def async_stop(self) -> None:
        if self._unsub_signal:
            self._unsub_signal()
            self._unsub_signal = None
        self._unbind()

    def _unbind(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs = []

    @callback
    def _rebind(self) -> None:
        """An alle anderen Manager hängen (Einträge können später dazukommen/gehen)."""
        self._unbind()
        for manager in self.others():
            self._unsubs.append(manager.add_listener(self._notify))
        self._notify()

    def others(self) -> list:
        managers = self.hass.data.get(DOMAIN, {})
        return [
            m for eid, m in managers.items()
            if eid != self.entry.entry_id and not isinstance(m, OverviewManager)
        ]

    def add_listener(self, cb: CALLBACK_TYPE) -> CALLBACK_TYPE:
        self._listeners.append(cb)

        def _remove() -> None:
            if cb in self._listeners:
                self._listeners.remove(cb)

        return _remove

    @callback
    def _notify(self) -> None:
        for cb in list(self._listeners):
            cb()

    # ------------------------------------------------------------------
    @property
    def investment(self) -> float | None:
        values = [m.investment for m in self.others()]
        known = [v for v in values if v is not None]
        return sum(known) if known else None

    @property
    def total_savings(self) -> float:
        return sum(m.total_savings for m in self.others())

    @property
    def initial_credit(self) -> float:
        return sum(m.initial_credit for m in self.others())

    @property
    def start_time(self) -> str | None:
        times = [m.start_time for m in self.others() if m.start_time]
        return min(times) if times else None

    def breakdown(self) -> list[dict]:
        lines: list[dict] = []
        for manager in self.others():
            lines.extend(manager.breakdown())
        return lines

    def attributes(self) -> dict:
        return {
            "eintraege": len(self.others()),
            "startgutschrift_eur": round(self.initial_credit, 2),
            "einsparung_seit_start_eur": round(self.total_savings - self.initial_credit, 2),
            "geraete": self.breakdown(),
            "inbetriebnahme": self.start_time,
        }
