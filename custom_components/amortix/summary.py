"""Datenaufbereitung fuer das Amortix-Panel (ohne Home-Assistant-Importe, daher testbar)."""
from __future__ import annotations

from typing import Any

from .coordinator import MetricsMixin, OverviewManager


class _Totals(MetricsMixin):
    """Summe ueber mehrere Manager; nutzt dieselben Kennzahlen wie jeder Einzelmanager."""

    def __init__(self, managers: list) -> None:
        self.investment = _sum_known([m.investment for m in managers])
        self.total_savings = sum(m.total_savings for m in managers)
        self.initial_credit = sum(m.initial_credit for m in managers)
        times = [m.start_time for m in managers if m.start_time]
        self.start_time = min(times) if times else None


def _sum_known(values: list[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def _round(value: float | None, digits: int = 2) -> float | None:
    return round(value, digits) if value is not None else None


def metrics(source: Any) -> dict[str, Any]:
    """Kennzahlen eines Managers, einer Geraetesicht oder einer Summe."""
    payback = source.payback_date
    return {
        "investment": _round(source.investment),
        "savings": _round(source.total_savings),
        "initial_credit": _round(source.initial_credit),
        "progress": _round(source.progress, 1),
        "remaining": _round(source.remaining),
        "daily_average": _round(source.daily_average),
        "remaining_days": _round(source.remaining_days, 0),
        "payback_date": payback.isoformat() if payback is not None else None,
        "start_time": source.start_time,
    }


def build_summary(entries: list[tuple[str, str, str, Any]]) -> dict[str, Any]:
    """entries: (entry_id, titel, modus, manager); Uebersichts-Eintraege werden ignoriert."""
    items = [e for e in entries if not isinstance(e[3], OverviewManager)]
    out_entries = []
    for entry_id, title, mode, manager in items:
        item = {"entry_id": entry_id, "title": title, "mode": mode, **metrics(manager)}
        views = getattr(manager, "views", None)
        if views:
            item["devices"] = [
                {"name": view.name, "kind": "pv" if key.startswith("prod") else "storage", **metrics(view)}
                for key, view in views.items()
            ]
        out_entries.append(item)
    return {
        "total": metrics(_Totals([e[3] for e in items])),
        "entries": out_entries,
    }
