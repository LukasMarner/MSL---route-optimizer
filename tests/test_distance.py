import numpy as np
import pytest

from src.distance import build_matrices, haversine_km
from src.models import check_feasibility
from tests.helpers import fixture_instance


def test_known_pair_within_1pct():
    # Paris -> London, ~343.5 km great-circle
    d = haversine_km(48.8566, 2.3522, 51.5074, -0.1278)
    assert d == pytest.approx(343.5, rel=0.01)


def test_one_degree_latitude():
    assert haversine_km(28.0, 77.0, 29.0, 77.0) == pytest.approx(111.19, rel=0.001)


def test_straight_line_diagonal_zero_and_symmetric():
    # symmetry holds for the straight-line method only; OSRM road matrices may be asymmetric
    rng = np.random.default_rng(0)
    lats, lons = 28.53 + rng.random(10) * 0.04, 77.21 + rng.random(10) * 0.04
    dist, t = build_matrices(lats, lons, road_factor=1.3, speed_kmph=25)
    assert np.all(np.diag(dist) == 0) and np.all(np.diag(t) == 0)
    assert np.array_equal(dist, dist.T) and np.array_equal(t, t.T)
    assert t.dtype.kind == "i"


def test_fixture_hand_values():
    inst = fixture_instance("tiny_1_order")
    assert inst.dist_km[0][1] == pytest.approx(1.0, rel=0.01)
    assert inst.time_sec[0][1] == 120
    opp = fixture_instance("tiny_2_opposite")
    assert opp.time_sec[0][1] == 240 and opp.time_sec[1][2] == 480
    assert opp.deadline_sec[1:] == [360, 360]


def test_feasibility_check():
    assert check_feasibility(fixture_instance("tiny_infeasible")) == ["FAR"]
    assert check_feasibility(fixture_instance("tiny_6_orders")) == []
