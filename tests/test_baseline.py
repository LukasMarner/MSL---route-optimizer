from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

import config
from src.baseline import greedy_baseline, one_per_rider
from src.checker import verify_solution
from src.models import Params, build_instance
from src.solver import solve
from tests.helpers import FIXTURE_PARAMS, fixture_instance

ROOT = Path(__file__).resolve().parent.parent
TINY = ["tiny_1_order", "tiny_2_close", "tiny_2_opposite", "tiny_2_capacity", "tiny_6_orders"]


@pytest.fixture(scope="module")
def full_instance():
    return build_instance(pd.read_csv(ROOT / "data" / "sample_orders.csv"), Params(config.STORE_LAT, config.STORE_LON, distance_method="straight_line"))


@pytest.mark.parametrize("method", [greedy_baseline, one_per_rider])
def test_full_baselines_valid(full_instance, method):
    sol = method(full_instance)
    counts = Counter(s.order_id for r in sol.routes for s in r.stops)
    assert set(counts) == set(full_instance.order_ids) and set(counts.values()) == {1}
    assert sol.late_orders == 0
    assert all(r.items <= full_instance.capacity for r in sol.routes)
    assert verify_solution(sol, full_instance) == []


def test_one_per_rider_count(full_instance):
    assert one_per_rider(full_instance).riders_used == full_instance.n_orders


@pytest.mark.parametrize("name", TINY)
def test_tiny_baselines_feasible_and_optimizer_not_worse(name):
    inst = fixture_instance(name)
    greedy = greedy_baseline(inst)
    assert verify_solution(greedy, inst) == []
    assert verify_solution(one_per_rider(inst), inst) == []
    assert solve(inst, FIXTURE_PARAMS).riders_used <= greedy.riders_used


def test_full_optimizer_not_worse_than_greedy(full_instance):
    opt = solve(full_instance, Params(config.STORE_LAT, config.STORE_LON, time_limit_s=3, distance_method="straight_line"))
    assert opt.riders_used <= greedy_baseline(full_instance).riders_used
