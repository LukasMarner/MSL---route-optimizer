"""Independent re-verification of a Solution against its Instance."""
from __future__ import annotations

from collections import Counter

from src.kpis import route_nodes, simulate_arrivals
from src.models import Instance, Solution

TOL_MIN = 1e-6


def verify_solution(solution: Solution, instance: Instance) -> list[str]:
    """Returns a list of violations; empty means the solution is valid."""
    errors = []
    seen = Counter(s.order_id for r in solution.routes for s in r.stops)
    for oid in instance.order_ids:
        if seen[oid] != 1:
            errors.append(f"{oid} served {seen[oid]} times")
    for oid in set(seen) - set(instance.order_ids):
        errors.append(f"unknown order {oid}")

    for r in solution.routes:
        nodes = route_nodes(r, instance)
        load = sum(instance.demand[n] for n in nodes)
        if load > instance.capacity:
            errors.append(f"rider {r.rider_id}: load {load} > capacity {instance.capacity}")
        if load != r.items:
            errors.append(f"rider {r.rider_id}: reported items {r.items} != {load}")
        for stop, node, arr in zip(r.stops, nodes, simulate_arrivals(nodes, instance)):
            if abs(stop.arrival_min - arr / 60) > TOL_MIN:
                errors.append(f"{stop.order_id}: reported arrival {stop.arrival_min:.3f} != recomputed {arr / 60:.3f} min")
            if arr > instance.deadline_sec[node]:
                errors.append(f"{stop.order_id}: arrival {arr / 60:.2f} > deadline {instance.deadline_sec[node] / 60:.2f} min")
    if solution.riders_used != len(solution.routes):
        errors.append("riders_used does not match number of routes")
    return errors
