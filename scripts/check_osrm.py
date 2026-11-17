"""OSRM checkpoint: compare straight-line vs road matrices and solutions on the tiny fixtures."""
import sys; from pathlib import Path; ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
from dataclasses import replace
import numpy as np, pandas as pd
from src.checker import verify_solution
from src.distance import get_route_geometry, haversine_km
from src.mapping import route_geometries, route_map
from src.models import build_instance
from src.solver import solve
from tests.helpers import FIXTURES, FIXTURE_PARAMS

CACHE = FIXTURES / "osrm_cache"
pd.set_option("display.width", 200)
for name in ["tiny_2_close", "tiny_6_orders"]:
    df = pd.read_csv(FIXTURES / f"{name}.csv")
    sl = build_instance(df, FIXTURE_PARAMS)
    rd = build_instance(df, replace(FIXTURE_PARAMS, distance_method="osrm", osrm_cache_dir=str(CACHE)))
    assert rd.distance_method == "osrm", rd.distance_warning
    labels = ["store"] + sl.order_ids
    hav = haversine_km(np.array(sl.lats)[:, None], np.array(sl.lons)[:, None], np.array(sl.lats)[None], np.array(sl.lons)[None])
    print(f"===== {name}: distance km   [straight-line (road factor 1.0) | OSRM road]")
    side = pd.concat({"straight": pd.DataFrame(sl.dist_km, labels, labels).round(3),
                      "osrm": pd.DataFrame(rd.dist_km, labels, labels).round(3)}, axis=1)
    print(side.to_string())
    off = ~np.eye(len(labels), dtype=bool)
    ratio = rd.dist_km[off] / hav[off]
    print(f"road/haversine ratio: min {ratio.min():.2f}  median {np.median(ratio):.2f}  max {ratio.max():.2f};"
          f" asymmetric pairs: {int((np.abs(rd.dist_km - rd.dist_km.T) > 1e-6).sum() // 2)};"
          f" max |d_ij - d_ji| {np.abs(rd.dist_km - rd.dist_km.T).max():.3f} km")
    for label, inst in [("straight", sl), ("osrm", rd)]:
        sol = solve(inst, FIXTURE_PARAMS)
        routes = " | ".join("→".join(s.order_id for s in r.stops) + f" (back {r.duration_min:.1f}m, {r.distance_km:.2f}km)" for r in sol.routes)
        print(f"  {label:8s} riders={sol.riders_used} dist={sol.total_distance_km:.2f} km  min slack={sol.min_slack_min:.2f}  {routes}  checker={verify_solution(sol, inst) or 'OK'}")
    geoms, failed = route_geometries(sol, rd, cache_dir=CACHE)
    for r in sol.routes:
        g = np.array(geoms[r.rider_id])
        glen = haversine_km(g[:-1, 0], g[:-1, 1], g[1:, 0], g[1:, 1]).sum()
        print(f"  rider {r.rider_id} geometry: {len(g)} vertices, polyline length {glen:.3f} km vs matrix route {r.distance_km:.3f} km")
    route_map(sol, rd, geometries=geoms).save(str(ROOT / f"outputs/osrm_{name}.html"))
