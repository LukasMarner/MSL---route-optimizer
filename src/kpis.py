"""Shared route construction and KPI computation, so all methods are measured identically."""
from __future__ import annotations

from src.models import Instance, Route, Solution, Stop


def simulate_arrivals(nodes: list[int], instance: Instance) -> list[int]:
    """Arrival time (s) at each node of a route store -> nodes -> store, handover added on leaving."""
    t, prev, arrivals = 0, 0, []
    for node in nodes:
        t += instance.time_sec[prev][node] + (instance.service_sec if prev != 0 else 0)
        arrivals.append(t)
        prev = node
    return arrivals


def make_route(rider_id: int, nodes: list[int], instance: Instance, arrivals_sec: list[int] | None = None) -> Route:
    """nodes = order node indices (1..n) in visiting order. If arrivals_sec is None they are simulated."""
    if arrivals_sec is None:
        arrivals_sec = simulate_arrivals(nodes, instance)
    stops, load = [], 0
    for seq, (node, arr) in enumerate(zip(nodes, arrivals_sec), start=1):
        load += instance.demand[node]
        deadline = instance.deadline_sec[node]
        stops.append(Stop(
            order_id=instance.order_ids[node - 1],
            sequence=seq,
            arrival_min=arr / 60,
            deadline_min=deadline / 60,
            slack_min=(deadline - arr) / 60,
            items=instance.demand[node],
            load_after=load,
        ))
    path = [0] + nodes + [0]
    distance = sum(instance.dist_km[a][b] for a, b in zip(path, path[1:]))
    back = arrivals_sec[-1] + instance.service_sec + instance.time_sec[nodes[-1]][0] if nodes else 0
    return Route(rider_id=rider_id, stops=stops, distance_km=float(distance), duration_min=back / 60, items=load)


def route_nodes(route: Route, instance: Instance) -> list[int]:
    index = {oid: i for i, oid in enumerate(instance.order_ids, start=1)}
    return [index[s.order_id] for s in route.stops]


def travel_sec(nodes: list[int], instance: Instance) -> int:
    """Pure riding time (no handovers), store -> nodes -> store."""
    path = [0] + nodes + [0]
    return int(sum(instance.time_sec[a][b] for a, b in zip(path, path[1:])))


def make_solution(method: str, routes: list[Route], instance: Instance, solve_time_s: float, status: str) -> Solution:
    stops = [s for r in routes for s in r.stops]
    slacks = [s.slack_min for s in stops]
    return Solution(
        method=method,
        routes=routes,
        riders_used=len(routes),
        total_distance_km=sum(r.distance_km for r in routes),
        total_travel_min=sum(travel_sec(route_nodes(r, instance), instance) for r in routes) / 60,
        avg_slack_min=sum(slacks) / len(slacks) if slacks else 0.0,
        min_slack_min=min(slacks) if slacks else 0.0,
        late_orders=sum(1 for s in slacks if s < -1e-9),
        solve_time_s=solve_time_s,
        status=status,
    )
