"""Step 4: CVRPTW in fleet-sizing mode with OR-Tools routing."""
from __future__ import annotations

import time

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from src.kpis import make_route, make_solution
from src.models import Instance, Params, Solution, check_feasibility

HORIZON_SEC = 4 * 3600


def rider_fixed_cost(instance: Instance) -> int:
    """Upper bound on any solution's total travel time + 1, so one rider always outweighs travel.

    Every order node is left exactly once (<= its longest outgoing arc), and each of at most
    n riders leaves the store once (<= the store's longest arc).
    """
    t = instance.time_sec
    n = instance.n_orders
    return int(t[1:].max(axis=1).sum() + n * t[0].max() + 1)


def solve(instance: Instance, params: Params) -> Solution:
    bad = check_feasibility(instance)
    if bad:
        raise ValueError(f"Orders that can never be served on time / in one bag: {', '.join(bad)}")

    n_nodes = instance.n_orders + 1
    n_vehicles = instance.n_orders
    manager = pywrapcp.RoutingIndexManager(n_nodes, n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)
    t, svc = instance.time_sec, instance.service_sec

    def travel_cb(i, j):
        return int(t[manager.IndexToNode(i)][manager.IndexToNode(j)])

    def time_cb(i, j):
        a, b = manager.IndexToNode(i), manager.IndexToNode(j)
        return int(t[a][b] + (svc if a != 0 else 0))

    def demand_cb(i):
        return int(instance.demand[manager.IndexToNode(i)])

    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(travel_cb))

    routing.AddDimension(routing.RegisterTransitCallback(time_cb), 0, HORIZON_SEC, True, "Time")
    time_dim = routing.GetDimensionOrDie("Time")
    for node in range(1, n_nodes):
        time_dim.CumulVar(manager.NodeToIndex(node)).SetMax(int(instance.deadline_sec[node]))

    routing.AddDimensionWithVehicleCapacity(
        routing.RegisterUnaryTransitCallback(demand_cb), 0, [instance.capacity] * n_vehicles, True, "Capacity")

    routing.SetFixedCostOfAllVehicles(rider_fixed_cost(instance))

    sp = pywrapcp.DefaultRoutingSearchParameters()
    sp.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    sp.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    sp.time_limit.seconds = int(params.time_limit_s)

    start = time.perf_counter()
    assignment = routing.SolveWithParameters(sp)
    elapsed = time.perf_counter() - start
    status = routing_enums_pb2.RoutingSearchStatus.Value.Name(routing.status())
    if assignment is None:
        raise RuntimeError(f"OR-Tools found no solution (status {status})")

    routes = []
    for v in range(n_vehicles):
        idx = assignment.Value(routing.NextVar(routing.Start(v)))
        nodes, arrivals = [], []
        while not routing.IsEnd(idx):
            nodes.append(manager.IndexToNode(idx))
            arrivals.append(assignment.Value(time_dim.CumulVar(idx)))
            idx = assignment.Value(routing.NextVar(idx))
        if nodes:
            routes.append(make_route(len(routes) + 1, nodes, instance, arrivals_sec=arrivals))
    return make_solution("optimized", routes, instance, elapsed, status)
