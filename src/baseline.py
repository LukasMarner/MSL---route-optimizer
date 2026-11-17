"""Step 5: baselines a store manager could do by hand."""
from __future__ import annotations

import time

from src.kpis import make_route, make_solution
from src.models import Instance, Solution


def greedy_baseline(instance: Instance) -> Solution:
    """Urgent-first, nearest-neighbour batching."""
    start = time.perf_counter()
    t, svc = instance.time_sec, instance.service_sec
    unassigned = sorted(range(1, instance.n_orders + 1), key=lambda i: (instance.deadline_sec[i], i))
    routes = []
    while unassigned:
        first = unassigned.pop(0)
        nodes, load, clock = [first], instance.demand[first], t[0][first]
        while True:
            last = nodes[-1]
            for cand in sorted(unassigned, key=lambda j: (t[last][j], j)):
                arrival = clock + svc + t[last][cand]
                if load + instance.demand[cand] <= instance.capacity and arrival <= instance.deadline_sec[cand]:
                    nodes.append(cand)
                    load += instance.demand[cand]
                    clock = arrival
                    unassigned.remove(cand)
                    break
            else:
                break
        routes.append(make_route(len(routes) + 1, nodes, instance))
    return make_solution("greedy_baseline", routes, instance, time.perf_counter() - start, "heuristic")


def one_per_rider(instance: Instance) -> Solution:
    """Each order gets its own rider: store -> customer -> store."""
    start = time.perf_counter()
    routes = [make_route(i, [i], instance) for i in range(1, instance.n_orders + 1)]
    return make_solution("one_per_rider", routes, instance, time.perf_counter() - start, "reference")
