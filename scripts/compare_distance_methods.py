"""Run the 45-order wave with both distance methods and compare."""
import sys; from pathlib import Path; ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
from dataclasses import replace
import numpy as np, pandas as pd
import config
from src.baseline import greedy_baseline, one_per_rider
from src.checker import verify_solution
from src.models import Params, build_instance, check_feasibility
from src.report import comparison_table
from src.solver import solve

orders = pd.read_csv(ROOT / "data/sample_orders.csv")
base = Params(config.STORE_LAT, config.STORE_LON)
rows = []
for method in ["straight_line", "osrm"]:
    params = replace(base, distance_method=method)
    inst = build_instance(orders, params)
    print(f"== {method}: used {inst.distance_method}", inst.distance_warning or "")
    off = ~np.eye(len(inst.lats), dtype=bool)
    print(f"   off-diag dist {inst.dist_km[off].min():.3f}–{inst.dist_km[off].max():.3f} km, "
          f"store→order max {inst.time_sec[0].max() / 60:.1f} min, "
          f"asymmetric pairs {int((np.abs(inst.dist_km - inst.dist_km.T) > 1e-6).sum() // 2)}")
    bad = check_feasibility(inst)
    if bad:
        print(f"   INFEASIBLE under this method: {bad}")
        for oid in bad:
            i = inst.order_ids.index(oid) + 1
            print(f"     {oid}: direct {inst.time_sec[0][i] / 60:.1f} min vs deadline {inst.deadline_sec[i] / 60:.1f} min, {inst.demand[i]} items")
        keep = ~orders.order_id.isin(bad)
        inst = build_instance(orders[keep].reset_index(drop=True), params)
        print(f"   continuing with {inst.n_orders} orders")
    sols = [solve(inst, params), greedy_baseline(inst), one_per_rider(inst)]
    assert all(not verify_solution(s, inst) for s in sols)
    t = comparison_table(sols); t.insert(0, "distance", method); t.insert(1, "orders", inst.n_orders); rows.append(t)
print(pd.concat(rows).to_string(index=False))
