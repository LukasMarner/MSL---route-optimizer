import sys; from pathlib import Path; ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
import pandas as pd
import config
from src.baseline import greedy_baseline, one_per_rider
from src.checker import verify_solution
from src.models import Params, build_instance
from src.solver import solve
from tests.helpers import FIXTURE_PARAMS, fixture_instance

for name in ["tiny_1_order", "tiny_2_close", "tiny_2_opposite", "tiny_2_capacity", "tiny_6_orders"]:
    inst = fixture_instance(name)
    g, o, opt = greedy_baseline(inst), one_per_rider(inst), solve(inst, FIXTURE_PARAMS)
    routes = " | ".join("→".join(s.order_id for s in r.stops) for r in g.routes)
    print(f"{name:16s} greedy={g.riders_used} [{routes}] ok={not verify_solution(g, inst)}  "
          f"one_per={o.riders_used} ok={not verify_solution(o, inst)}  opt={opt.riders_used}  opt<=greedy={opt.riders_used <= g.riders_used}")

params = Params(config.STORE_LAT, config.STORE_LON)
inst = build_instance(pd.read_csv(ROOT / "data/sample_orders.csv"), params)
rows = []
for sol in [solve(inst, params), greedy_baseline(inst), one_per_rider(inst)]:
    assert not verify_solution(sol, inst), verify_solution(sol, inst)
    rows.append([sol.method, sol.riders_used, sol.total_distance_km, sol.total_travel_min, sol.avg_slack_min,
                 sol.min_slack_min, sol.late_orders, sol.solve_time_s])
print(pd.DataFrame(rows, columns=["method", "riders", "dist_km", "travel_min", "avg_slack", "min_slack", "late", "solve_s"]).round(2).to_string(index=False))
