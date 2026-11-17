import sys; from pathlib import Path; ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
import config
from src.models import Params, build_instance, check_feasibility

np.set_printoptions(precision=4, suppress=True)
FIX = Params(config.STORE_LAT, config.STORE_LON, promise_min=15, speed_kmph=30, road_factor=1.0, service_min=2, capacity_items=10)
for name in ["tiny_1_order", "tiny_2_opposite", "tiny_infeasible"]:
    inst = build_instance(pd.read_csv(ROOT / f"tests/fixtures/{name}.csv"), FIX)
    print(f"== {name}  nodes={['store'] + inst.order_ids}\ndist_km=\n{inst.dist_km}\ntime_sec=\n{inst.time_sec}")
    print("deadline_sec:", inst.deadline_sec[1:], "service_sec:", inst.service_sec, "infeasible:", check_feasibility(inst))
    print("diag 0:", np.all(np.diag(inst.time_sec) == 0), "symmetric:", np.array_equal(inst.time_sec, inst.time_sec.T), "\n")

inst = build_instance(pd.read_csv(ROOT / "data/sample_orders.csv"), Params(config.STORE_LAT, config.STORE_LON))
off = ~np.eye(len(inst.lats), dtype=bool)
print("full:", inst.time_sec.shape, f"dist off-diag min {inst.dist_km[off].min():.3f} max {inst.dist_km[off].max():.3f} km;",
      f"time min {inst.time_sec[off].min()} max {inst.time_sec[off].max()} s;",
      "symmetric:", np.array_equal(inst.time_sec, inst.time_sec.T), "infeasible:", check_feasibility(inst))
print("max store->order:", inst.time_sec[0].max() / 60, "min (expected <= 2.5*1.3/25*60 = 7.8)")
