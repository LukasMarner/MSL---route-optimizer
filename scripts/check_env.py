"""Step 1 checkpoint: imports, versions, and a 3-node OR-Tools routing example."""
import importlib.metadata as md

import folium, numpy, pandas, pulp, pytest, streamlit, streamlit_folium  # noqa: F401
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

for pkg in ["ortools", "pandas", "numpy", "folium", "streamlit", "streamlit-folium", "pulp", "pytest"]:
    print(f"{pkg:18s} {md.version(pkg)}")

# 3 nodes (depot + 2), 1 vehicle
dist = [[0, 2, 9], [2, 0, 6], [9, 6, 0]]
manager = pywrapcp.RoutingIndexManager(3, 1, 0)
routing = pywrapcp.RoutingModel(manager)
cb = routing.RegisterTransitCallback(lambda i, j: dist[manager.IndexToNode(i)][manager.IndexToNode(j)])
routing.SetArcCostEvaluatorOfAllVehicles(cb)
sp = pywrapcp.DefaultRoutingSearchParameters()
sp.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
sol = routing.SolveWithParameters(sp)
idx, route = routing.Start(0), []
while not routing.IsEnd(idx):
    route.append(manager.IndexToNode(idx))
    idx = sol.Value(routing.NextVar(idx))
route.append(manager.IndexToNode(idx))
print("hello-world route:", route, "cost:", sol.ObjectiveValue(), "(expected 17)")
assert sol.ObjectiveValue() == 17
