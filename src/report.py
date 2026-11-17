"""Tabular views of solutions, shared by the CLI demo and the UI."""
from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from src.models import Solution

PLAN_COLUMNS = ["rider_id", "sequence", "order_id", "arrival_min", "deadline_min", "slack_min", "items", "load_after"]


def comparison_table(solutions: list[Solution]) -> pd.DataFrame:
    return pd.DataFrame([{
        "method": s.method,
        "riders": s.riders_used,
        "distance_km": round(s.total_distance_km, 2),
        "travel_min": round(s.total_travel_min, 1),
        "avg_slack_min": round(s.avg_slack_min, 2),
        "min_slack_min": round(s.min_slack_min, 2),
        "late": s.late_orders,
        "solve_s": round(s.solve_time_s, 2),
    } for s in solutions])


def plan_table(solution: Solution) -> pd.DataFrame:
    """One row per stop."""
    rows = [{"rider_id": r.rider_id, **asdict(s)} for r in solution.routes for s in r.stops]
    return pd.DataFrame(rows, columns=PLAN_COLUMNS).round(2)


def route_table(solution: Solution) -> pd.DataFrame:
    """One row per rider."""
    return pd.DataFrame([{
        "rider": r.rider_id,
        "route": " → ".join(s.order_id for s in r.stops),
        "stops": len(r.stops),
        "items": r.items,
        "distance_km": round(r.distance_km, 2),
        "back_at_min": round(r.duration_min, 1),
        "min_slack_min": round(min(s.slack_min for s in r.stops), 2),
    } for r in solution.routes])
