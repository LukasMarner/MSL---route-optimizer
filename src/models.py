"""Data classes shared by the solver, baselines and (later) the UI."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.distance import OSRMError, build_matrices, build_matrices_osrm

STORE_DEADLINE_SEC = 10**7  # "large value" for the store node
OSRM = "osrm"
STRAIGHT_LINE = "straight_line"


@dataclass
class Params:
    store_lat: float
    store_lon: float
    promise_min: float = 20
    speed_kmph: float = 25
    road_factor: float = 1.3
    service_min: float = 2
    capacity_items: int = 10
    time_limit_s: int = 10
    distance_method: str = OSRM      # "osrm" | "straight_line"
    osrm_cache_dir: str | None = None  # None = data/osrm_cache
    osrm_timeout_s: float = 10


@dataclass
class Instance:          # everything a solver needs
    order_ids: list[str]
    lats: list[float]    # index 0 = store
    lons: list[float]
    demand: list[int]    # index 0 = 0
    deadline_sec: list[int]   # index 0 = large value
    dist_km: np.ndarray
    time_sec: np.ndarray
    service_sec: int
    capacity: int
    distance_method: str = STRAIGHT_LINE   # method actually used
    distance_warning: str | None = None    # set when OSRM was requested but failed

    @property
    def n_orders(self) -> int:
        return len(self.order_ids)


@dataclass
class Stop:
    order_id: str
    sequence: int
    arrival_min: float
    deadline_min: float
    slack_min: float     # deadline - arrival
    items: int
    load_after: int      # cumulative items delivered so far on this route


@dataclass
class Route:
    rider_id: int
    stops: list[Stop]
    distance_km: float   # incl. return to store
    duration_min: float  # until back at store, incl. handovers
    items: int


@dataclass
class Solution:
    method: str          # "optimized" | "greedy_baseline" | "one_per_rider"
    routes: list[Route]
    riders_used: int
    total_distance_km: float
    total_travel_min: float
    avg_slack_min: float
    min_slack_min: float
    late_orders: int
    solve_time_s: float
    status: str


def build_instance(orders_df: pd.DataFrame, params: Params) -> Instance:
    lats = [params.store_lat] + orders_df["lat"].astype(float).tolist()
    lons = [params.store_lon] + orders_df["lon"].astype(float).tolist()
    dist_km, time_sec, method, warning = compute_matrices(lats, lons, params)
    deadlines = ((params.promise_min - orders_df["minutes_since_placed"].astype(float)) * 60).round().astype(int)
    return Instance(
        order_ids=orders_df["order_id"].astype(str).tolist(),
        lats=lats,
        lons=lons,
        demand=[0] + orders_df["items"].astype(int).tolist(),
        deadline_sec=[STORE_DEADLINE_SEC] + deadlines.tolist(),
        dist_km=dist_km,
        time_sec=time_sec,
        service_sec=int(round(params.service_min * 60)),
        capacity=int(params.capacity_items),
        distance_method=method,
        distance_warning=warning,
    )


def compute_matrices(lats, lons, params: Params):
    """Matrices by the requested method; falls back to straight line if OSRM fails.

    Returns (dist_km, time_sec, method_used, warning_or_None).
    """
    warning = None
    if params.distance_method == OSRM:
        try:
            dist_km, time_sec = build_matrices_osrm(lats, lons, params.speed_kmph,
                                                    cache_dir=params.osrm_cache_dir, timeout=params.osrm_timeout_s)
            return dist_km, time_sec, OSRM, None
        except OSRMError as e:
            warning = (f"Road distances (OSRM) unavailable — {e}. "
                       f"Using straight-line × {params.road_factor:g} estimate instead.")
    elif params.distance_method != STRAIGHT_LINE:
        raise ValueError(f"unknown distance_method {params.distance_method!r}")
    dist_km, time_sec = build_matrices(lats, lons, params.road_factor, params.speed_kmph)
    return dist_km, time_sec, STRAIGHT_LINE, warning


def check_feasibility(instance: Instance) -> list[str]:
    """IDs of orders that can never be served (direct travel > deadline, or items > capacity)."""
    bad = []
    for i, oid in enumerate(instance.order_ids, start=1):
        if instance.time_sec[0][i] > instance.deadline_sec[i] or instance.demand[i] > instance.capacity:
            bad.append(oid)
    return bad
