"""OSRM road distances: mocked responses + responses recorded in tests/fixtures/osrm_cache (all offline)."""
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import config
from src import distance
from src.checker import verify_solution
from src.distance import OSRMError, build_matrices_osrm, get_route_geometry, haversine_km
from src.models import Params, build_instance, check_feasibility
from src.solver import solve
from tests.helpers import FIXTURE_PARAMS, FIXTURES

ROOT = Path(__file__).resolve().parent.parent
RECORDED = FIXTURES / "osrm_cache"
LATS, LONS = [28.53, 28.54, 28.55], [77.21, 77.21, 77.22]


def _serve(monkeypatch, response):
    calls = []

    def fake(url, timeout):
        calls.append(url)
        return response
    monkeypatch.setattr(distance, "_fetch_json", fake)
    return calls


def test_table_converts_metres_and_uses_own_speed(monkeypatch, tmp_path):
    # asymmetric on purpose (one-way streets); OSRM durations are absent and must not be needed
    _serve(monkeypatch, {"code": "Ok", "distances": [[0, 1000, 2500], [1200, 0, 900], [2400, 950, 0]]})
    dist, t = build_matrices_osrm(LATS, LONS, speed_kmph=30, cache_dir=tmp_path)
    assert dist[0][1] == pytest.approx(1.0) and dist[1][0] == pytest.approx(1.2)
    assert t[0][1] == 120 and t[0][2] == 300 and t.dtype.kind == "i"
    assert not np.array_equal(dist, dist.T)  # asymmetry preserved


def test_table_is_cached_on_disk(monkeypatch, tmp_path):
    calls = _serve(monkeypatch, {"code": "Ok", "distances": [[0, 1000, 2000], [1000, 0, 900], [2000, 900, 0]]})
    first, _ = build_matrices_osrm(LATS, LONS, 25, cache_dir=tmp_path)
    assert len(calls) == 1 and len(list(tmp_path.glob("table_*.json"))) == 1
    monkeypatch.setattr(distance, "_fetch_json", lambda *a: pytest.fail("should be served from cache"))
    second, _ = build_matrices_osrm(LATS, LONS, 25, cache_dir=tmp_path)
    assert np.array_equal(first, second)


def test_unroutable_pair_raises(monkeypatch, tmp_path):
    _serve(monkeypatch, {"code": "Ok", "distances": [[0, None, 2000], [1000, 0, 900], [2000, 900, 0]]})
    with pytest.raises(OSRMError, match="not routable"):
        build_matrices_osrm(LATS, LONS, 25, cache_dir=tmp_path)


def test_timeout_becomes_osrm_error(monkeypatch):
    monkeypatch.undo()  # use the real _fetch_json, but a failing network
    monkeypatch.setattr(distance, "MIN_REQUEST_INTERVAL_S", 0)

    def timeout(*a, **k):
        raise TimeoutError("timed out")
    monkeypatch.setattr(distance.urllib.request, "urlopen", timeout)
    with pytest.raises(OSRMError, match="timed out"):
        distance._fetch_json("http://example.invalid", timeout=1)


def test_fallback_to_straight_line_with_warning(tmp_path):
    df = pd.read_csv(FIXTURES / "tiny_2_close.csv")
    params = replace(FIXTURE_PARAMS, distance_method="osrm", osrm_cache_dir=str(tmp_path))
    inst = build_instance(df, params)  # network disabled -> fallback
    assert inst.distance_method == "straight_line"
    assert "OSRM" in inst.distance_warning and "straight-line" in inst.distance_warning
    assert inst.time_sec[1][0] == 120  # same as the straight-line hand value


def test_geometry_swaps_to_lat_lon_and_caches(monkeypatch, tmp_path):
    calls = _serve(monkeypatch, {"code": "Ok", "routes": [{"distance": 123.0, "geometry": {
        "type": "LineString", "coordinates": [[77.21, 28.53], [77.215, 28.535], [77.21, 28.54]]}}]})
    path = get_route_geometry([(28.53, 77.21), (28.54, 77.21)], cache_dir=tmp_path)
    assert path == [(28.53, 77.21), (28.535, 77.215), (28.54, 77.21)]
    get_route_geometry([(28.53, 77.21), (28.54, 77.21)], cache_dir=tmp_path)
    assert len(calls) == 1


@pytest.fixture
def recorded_tiny6():
    df = pd.read_csv(FIXTURES / "tiny_6_orders.csv")
    return build_instance(df, replace(FIXTURE_PARAMS, distance_method="osrm", osrm_cache_dir=str(RECORDED)))


def test_recorded_road_distance_at_least_straight_line(recorded_tiny6):
    inst = recorded_tiny6
    assert inst.distance_method == "osrm"
    # store <-> order pairs (~1 km). Very short pairs can come out slightly below straight line,
    # because OSRM snaps each point to the nearest road before measuring.
    for i in range(1, inst.n_orders + 1):
        straight = haversine_km(inst.lats[0], inst.lons[0], inst.lats[i], inst.lons[i])
        assert inst.dist_km[0][i] >= straight
        assert inst.dist_km[i][0] >= straight


def test_recorded_matrix_is_asymmetric_and_solvable(recorded_tiny6):
    inst = recorded_tiny6
    assert np.all(np.diag(inst.dist_km) == 0)
    assert not np.array_equal(inst.dist_km, inst.dist_km.T)
    sol = solve(inst, FIXTURE_PARAMS)
    assert sol.riders_used == 2 and verify_solution(sol, inst) == []


def test_full_sample_runs_offline_from_committed_cache():
    params = Params(config.STORE_LAT, config.STORE_LON, time_limit_s=2, distance_method="osrm")
    orders = pd.read_csv(ROOT / "data" / "sample_orders.csv")
    inst = build_instance(orders, params)
    assert inst.distance_method == "osrm", inst.distance_warning
    bad = check_feasibility(inst)
    assert bad == ["O05", "O23"]  # too far by road for their deadlines
    inst = build_instance(orders[~orders.order_id.isin(bad)].reset_index(drop=True), params)
    assert inst.distance_method == "osrm"
    sol = solve(inst, params)
    assert verify_solution(sol, inst) == []
