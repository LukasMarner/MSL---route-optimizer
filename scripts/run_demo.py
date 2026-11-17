"""End-to-end run: load sample orders, run all three methods, print and save results."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

import config  # noqa: E402
from src.baseline import greedy_baseline, one_per_rider  # noqa: E402
from src.checker import verify_solution  # noqa: E402
from src.mapping import route_geometries, route_map  # noqa: E402
from src.models import OSRM, Params, build_instance, check_feasibility  # noqa: E402
from src.report import comparison_table, plan_table  # noqa: E402
from src.solver import solve  # noqa: E402


def main():
    params = Params(
        store_lat=config.STORE_LAT, store_lon=config.STORE_LON, promise_min=config.PROMISE_MIN,
        speed_kmph=config.SPEED_KMPH, road_factor=config.ROAD_FACTOR, service_min=config.SERVICE_MIN,
        capacity_items=config.CAPACITY_ITEMS, time_limit_s=config.TIME_LIMIT_S,
        distance_method=config.DISTANCE_METHOD,
    )
    orders = pd.read_csv(ROOT / "data" / "sample_orders.csv")
    instance = build_instance(orders, params)
    print(f"Distance method: {instance.distance_method}")
    if instance.distance_warning:
        print(f"WARNING: {instance.distance_warning}")
    infeasible = check_feasibility(instance)
    if infeasible:
        print(f"WARNING: skipping {len(infeasible)} order(s) that cannot be delivered on time even alone: "
              f"{', '.join(infeasible)}")
        instance = build_instance(orders[~orders["order_id"].isin(infeasible)].reset_index(drop=True), params)
    print()
    solutions = [solve(instance, params), greedy_baseline(instance), one_per_rider(instance)]
    for s in solutions:
        errors = verify_solution(s, instance)
        if errors:
            raise RuntimeError(f"{s.method} failed verification: {errors}")

    print(comparison_table(solutions).to_string(index=False))
    opt = solutions[0]
    print(f"\nOptimized routes ({opt.status}):")
    for r in opt.routes:
        print(f"Rider {r.rider_id}: {' → '.join(s.order_id for s in r.stops)} | {r.items} items | "
              f"{r.distance_km:.1f} km | back at {r.duration_min:.1f} min")

    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    plan_table(opt).to_csv(out / "optimized_plan.csv", index=False)
    geometries = None
    if instance.distance_method == OSRM:
        geometries, failed = route_geometries(opt, instance)
        if failed:
            print(f"WARNING: no street path for rider(s) {failed}; drawn as straight lines")
    route_map(opt, instance, geometries=geometries).save(str(out / "debug_map.html"))
    print(f"\nWrote {out / 'optimized_plan.csv'} and {out / 'debug_map.html'}")


if __name__ == "__main__":
    main()
