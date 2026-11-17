import sys; from pathlib import Path; ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
import pandas as pd
import config
from src.checker import verify_solution
from src.models import Params, build_instance
from src.solver import solve
from tests.helpers import FIXTURE_PARAMS, fixture_instance

def show(sol):
    print(f"  riders={sol.riders_used} dist={sol.total_distance_km:.3f} km travel={sol.total_travel_min:.2f} min status={sol.status}")
    for r in sol.routes:
        print(f"  Rider {r.rider_id}: {r.items} items, {r.distance_km:.3f} km, back at {r.duration_min:.2f} min")
        for s in r.stops:
            print(f"    #{s.sequence} {s.order_id:4s} arr {s.arrival_min:6.2f}  dl {s.deadline_min:6.2f}  slack {s.slack_min:6.2f}  load {s.load_after}")

for name in ["tiny_1_order", "tiny_2_close", "tiny_2_opposite", "tiny_2_capacity", "tiny_6_orders", "tiny_infeasible"]:
    print(f"== {name}")
    inst = fixture_instance(name)
    try:
        sol = solve(inst, FIXTURE_PARAMS)
    except ValueError as e:
        print("  ValueError:", e); continue
    show(sol); print("  checker:", verify_solution(sol, inst) or "OK")

print("== full 45 orders")
inst = build_instance(pd.read_csv(ROOT / "data/sample_orders.csv"), Params(config.STORE_LAT, config.STORE_LON))
sol = solve(inst, Params(config.STORE_LAT, config.STORE_LON))
print(f"  riders={sol.riders_used} dist={sol.total_distance_km:.2f} km travel={sol.total_travel_min:.1f} min "
      f"avg slack={sol.avg_slack_min:.2f} min slack={sol.min_slack_min:.2f} late={sol.late_orders} time={sol.solve_time_s:.1f}s {sol.status}")
print("  total items:", sum(inst.demand), "-> lower bound riders by capacity:", -(-sum(inst.demand) // 10))
print("  route loads:", sorted(r.items for r in sol.routes))
print("  checker:", verify_solution(sol, inst) or "OK")
