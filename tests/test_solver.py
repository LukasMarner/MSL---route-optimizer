from itertools import permutations
from pathlib import Path

import pandas as pd
import pytest

import config
from src.checker import verify_solution
from src.kpis import simulate_arrivals, travel_sec
from src.models import Params, build_instance
from src.solver import solve
from tests.helpers import FIXTURE_PARAMS, fixture_instance

ROOT = Path(__file__).resolve().parent.parent
FULL_PARAMS = Params(config.STORE_LAT, config.STORE_LON, time_limit_s=3, distance_method="straight_line")


@pytest.fixture(scope="module")
def full():
    inst = build_instance(pd.read_csv(ROOT / "data" / "sample_orders.csv"), FULL_PARAMS)
    return inst, solve(inst, FULL_PARAMS)


def test_full_every_order_once(full):
    inst, sol = full
    ids = [s.order_id for r in sol.routes for s in r.stops]
    assert sorted(ids) == sorted(inst.order_ids)


def test_full_capacity_and_deadlines(full):
    inst, sol = full
    assert all(r.items <= inst.capacity for r in sol.routes)
    assert all(s.arrival_min <= s.deadline_min for r in sol.routes for s in r.stops)
    assert sol.late_orders == 0


def test_full_independent_checker(full):
    inst, sol = full
    assert verify_solution(sol, inst) == []


def test_tiny_one_order_hand_values():
    sol = solve(fixture_instance("tiny_1_order"), FIXTURE_PARAMS)
    (r,) = sol.routes
    assert r.stops[0].arrival_min == pytest.approx(2.0)
    assert r.duration_min == pytest.approx(6.0)
    assert r.distance_km == pytest.approx(2.0, rel=0.01)


@pytest.mark.parametrize("name, riders", [
    ("tiny_2_close", 1), ("tiny_2_opposite", 2), ("tiny_2_capacity", 2), ("tiny_6_orders", 2),
])
def test_tiny_rider_counts(name, riders):
    inst = fixture_instance(name)
    sol = solve(inst, FIXTURE_PARAMS)
    assert sol.riders_used == riders
    assert verify_solution(sol, inst) == []


def test_tiny_6_one_rider_per_cluster():
    sol = solve(fixture_instance("tiny_6_orders"), FIXTURE_PARAMS)
    clusters = sorted("".join(sorted({s.order_id[0] for s in r.stops})) for r in sol.routes)
    assert clusters == ["E", "N"]


def _partitions(items):
    if not items:
        yield []
        return
    first, rest = items[0], items[1:]
    for part in _partitions(rest):
        for i in range(len(part)):
            yield part[:i] + [[first] + part[i]] + part[i + 1:]
        yield [[first]] + part


def _best_route_sec(group, inst):
    """Shortest feasible travel for one rider serving `group`, or None."""
    if sum(inst.demand[n] for n in group) > inst.capacity:
        return None
    best = None
    for perm in permutations(group):
        perm = list(perm)
        if all(a <= inst.deadline_sec[n] for n, a in zip(perm, simulate_arrivals(perm, inst))):
            cost = travel_sec(perm, inst)
            best = cost if best is None else min(best, cost)
    return best


def test_tiny_6_matches_brute_force():
    inst = fixture_instance("tiny_6_orders")
    best = None
    for part in _partitions(list(range(1, inst.n_orders + 1))):
        costs = [_best_route_sec(g, inst) for g in part]
        if None not in costs:
            key = (len(part), sum(costs))
            best = key if best is None else min(best, key)
    sol = solve(inst, FIXTURE_PARAMS)
    got = (sol.riders_used, round(sol.total_travel_min * 60))
    assert got == best


def test_infeasible_raises_naming_order():
    with pytest.raises(ValueError, match="FAR"):
        solve(fixture_instance("tiny_infeasible"), FIXTURE_PARAMS)
