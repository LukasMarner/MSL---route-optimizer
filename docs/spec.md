# Dark-Store Route Optimizer — Build Spec (Steps 1–5)

## 0. Context for Claude Code

This is a university optimization project. A quick-commerce dark store (modelled on a Blinkit store in Malviya Nagar, New Delhi) receives a wave of orders. The tool must decide **how many riders are needed** and **which orders each rider delivers, in what sequence**, so that every order arrives before its deadline and no rider's bag is overloaded.

The problem is a **Capacitated Vehicle Routing Problem with Time Windows (CVRPTW)** in **fleet-sizing mode**: the number of riders is not fixed; it is an output. The objective is lexicographic: first minimize riders used, then minimize total travel time.

The final product will be a Streamlit web app (step 6, **not part of this spec**). This spec covers:

1. Environment setup
2. Synthetic sample data (45 orders)
3. Travel-time matrix
4. Solver (Google OR-Tools routing library)
5. Baseline heuristic for comparison

Build everything so the Streamlit app can later import it directly: **no Streamlit imports inside `src/`**, all functions pure (inputs in, results out), all parameters passed in rather than read from globals.

---

## 0.1 Working method: validate every step before moving on

**Do not build the steps in one go.** Build one step, then debug and validate it on very small, hand-checkable data, and only move to the next step once its checkpoint passes. If a checkpoint fails, fix it before continuing; never carry a known bug forward.

For each step:

1. Implement the step.
2. Run it on the **tiny fixtures** below (not the 45-order data first).
3. Print intermediate values (matrices, routes, arrival times, loads) and compare them against the hand-calculated expected results written in the checkpoint.
4. Write the step's pytest tests and make them pass.
5. Only then run it on the full 45-order data and sanity-check the output looks reasonable.
6. Report to the user, in a short summary: what was built, what was checked, the actual vs expected values, and any surprises. Then move to the next step.

### Tiny fixtures (create in `tests/fixtures/`)

Use simple offsets from the store so distances can be worked out by hand. Use **road_factor = 1.0, speed = 30 km/h (= 2 min per km), service = 2 min, capacity = 10, promise = 15** for these fixtures unless stated, so the arithmetic stays easy. 0.009° latitude ≈ 1.0 km.

- **`tiny_1_order.csv`** — one order, 1 km due north of the store, 3 items, age 0.
  Expected: 1 rider; arrival at 2.0 min; back at store at 2 + 2 + 2 = 6.0 min; distance 2.0 km.
- **`tiny_2_close.csv`** — two orders ~100 m apart, both ~1 km north, 2 items each, age 0.
  Expected: 1 rider serving both; load 4; both on time.
- **`tiny_2_opposite.csv`** — one order 2 km north, one 2 km south, 2 items each, age 9 (deadline 6 min).
  Expected: 2 riders (direct trip = 4 min ≤ 6, but going via the other side cannot meet the deadline).
- **`tiny_2_capacity.csv`** — two orders ~100 m apart, 6 items each, age 0.
  Expected: 2 riders, because 12 items > bag of 10, even though they are close.
- **`tiny_infeasible.csv`** — one order 5 km away, age 10 (deadline 5 min, direct travel 10 min).
  Expected: feasibility check flags it; solver raises a `ValueError` naming it.
- **`tiny_6_orders.csv`** — six orders in two clusters (three ~1 km north, three ~1 km east), 2–3 items each, age 0.
  Expected: 2 riders, one per cluster; small enough to also brute-force check by hand or by enumerating.

### Checkpoints per step

- **Step 1 (environment):** all imports succeed; print library versions; a 3-node OR-Tools "hello world" routing example solves.
- **Step 2 (data):** generate a **5-order** sample first, print it, and verify by hand that distances from the store are ≤ 2.5 km, items are 1–10, ages are 0–5, and the same seed gives identical output. Then generate the 45-order file and print summary stats (min/max/mean of each column, distance-from-store histogram in text).
- **Step 3 (matrix):** on `tiny_1_order` and `tiny_2_opposite`, print the full matrices and confirm values match hand calculations (e.g. 1 km → 1.0 km and 120 s with the fixture settings). Confirm diagonal 0 and symmetry. Then build the 46×46 matrix for the full data and print its max and min off-diagonal values.
- **Step 4 (solver):** run every tiny fixture and confirm each expected result above, printing each route with arrival time, deadline, slack and load at every stop. Then run the full 45-order data and independently re-verify the solution with a separate checker function (every order exactly once, load ≤ capacity, arrival ≤ deadline, arrival times recomputed from the matrix match the solver's).
- **Step 5 (baseline):** run the baselines on the tiny fixtures and confirm they are feasible and that the optimizer never uses more riders than the greedy baseline. Then run all three methods on the 45-order data and print the comparison table.

---

## 1. Decisions (defaults chosen — edit `config.py` to change)

| # | Decision | Default | Notes |
|---|---|---|---|
| D1 | Store location | **lat 28.5319608, lon 77.2131596** | Blinkit store, K5, Block K, Malviya Nagar (confirmed by user). |
| D2 | Delivery radius | 2.5 km | Typical dark-store catchment. |
| D3 | Delivery promise | 15 min from order placement | 10 min is marketing; 15 min keeps all orders feasible with batching possible. |
| D4 | Order age at dispatch | 0–5 min (uniform) | Time already elapsed (incl. packing) when the wave is planned. Deadline = promise − age. |
| D5 | Rider speed | 25 km/h | Two-wheeler average speed (user's choice). |
| D6 | Road factor | 1.3 | Road distance = straight-line (haversine) × 1.3. No external routing API. |
| D7 | Handover time per drop | 2 min | |
| D8 | Bag capacity | 10 items | User's choice. |
| D9 | Order size | 1–10 items, skewed small | 50% 1–3 items, 35% 4–6, 15% 7–10. Max must not exceed bag capacity, or the order can never be delivered. |
| D10 | Number of orders | 45 | One evening-peak wave; all orders ready at time 0. |
| D11 | Random seed | 42 | Data must be reproducible. |
| D12 | Solver time limit | 10 s | |
| D13 | Baseline | Greedy urgent-first nearest-neighbour batching | Plus a "one order per rider" figure for reference. |

Feasibility check on the defaults: the farthest order is 2.5 km away → 2.5 × 1.3 / 25 × 60 = 7.8 min direct travel; the tightest deadline is 15 − 5 = 10 min. Every order (max 10 items) fits in one bag (10 items). So every order is individually deliverable, and the small bag makes batching the binding trade-off, which makes the problem interesting.

---

## 2. Mathematical model (for reference; implement via OR-Tools routing, not as a MILP)

**Sets:** orders N = {1..n}, store 0, V = N ∪ {0}.
**Parameters:** τ_ij travel time, s handover time, q_i order size, Q bag capacity, l_i deadline, F fixed cost per rider.
**Variables:** x_ij ∈ {0,1} (arc used), t_i arrival time at i, u_i cumulative load at i.

- Objective: min F·Σ_j x_0j + Σ_ij τ_ij·x_ij
- Each order entered once and left once
- Riders out of store = riders back
- t_j ≥ τ_0j
- t_j ≥ t_i + s + τ_ij − M_ij(1 − x_ij)
- t_i ≤ l_i
- u_j ≥ u_i + q_j − Q(1 − x_ij), q_i ≤ u_i ≤ Q
- x binary, t ≥ 0

F is chosen larger than any possible total travel time so that saving one rider always beats any travel-time saving.

The OR-Tools model in Section 6 must be equivalent to this. (A PuLP MILP validation on small instances is a later step; structure the code so the same `Instance` object can be passed to a future `src/milp.py`.)

---

## 3. Step 1 — Environment

- Python 3.10+
- `requirements.txt`:
  ```
  ortools>=9.8
  pandas>=2.0
  numpy>=1.24
  folium>=0.15
  streamlit>=1.30
  streamlit-folium>=0.15
  pulp>=2.7
  pytest>=7.0
  ```
  (streamlit, streamlit-folium and pulp are for later steps but install them now.)

### Project structure

```
blinkit-route-optimizer/
├── README.md
├── requirements.txt
├── config.py                # all default parameters (Section 1)
├── data/
│   ├── generate_orders.py   # Step 2
│   └── sample_orders.csv    # generated output, committed
├── src/
│   ├── __init__.py
│   ├── models.py            # dataclasses
│   ├── distance.py          # Step 3
│   ├── solver.py            # Step 4
│   ├── baseline.py          # Step 5
│   └── kpis.py              # shared KPI computation
├── scripts/
│   └── run_demo.py          # end-to-end CLI run
└── tests/
    ├── test_distance.py
    ├── test_generator.py
    ├── test_solver.py
    └── test_baseline.py
```

---

## 4. Step 2 — Sample data (`data/generate_orders.py`)

Generate **45 orders** around the store and save `data/sample_orders.csv`.

### CSV schema (this is also the upload format for the future UI)

| column | type | description |
|---|---|---|
| `order_id` | str | `O01` … `O45` |
| `lat` | float, 6 dp | customer latitude |
| `lon` | float, 6 dp | customer longitude |
| `items` | int | number of items (1–10) |
| `minutes_since_placed` | float, 1 dp | age of the order at dispatch time (0–5) |

### Generation rules

- Seeded with `numpy.random.default_rng(SEED)`.
- Location: uniform over a disk of radius R = 2.5 km around the store, with a minimum distance of 0.2 km (sample r = R·√U, angle uniform, resample if r < 0.2). Convert km offsets to lat/lon (1° lat ≈ 111.32 km; 1° lon ≈ 111.32·cos(lat) km).
- `items`: draw from the skewed distribution in D9.
- `minutes_since_placed`: uniform 0–5, rounded to 1 dp.
- **Feasibility guarantee:** after generating, verify every order satisfies direct travel time ≤ deadline and `items` ≤ capacity; resample any order that fails.
- The script exposes `generate_orders(n, store_lat, store_lon, radius_km, seed, ...) -> pd.DataFrame` and, when run as `__main__`, writes the CSV with defaults from `config.py`.
- Known limitation (mention in README): uniform sampling can place points in parks or on non-residential land; acceptable for synthetic data.

---

## 5. Step 3 — Travel-time matrix (`src/distance.py`)

- `haversine_km(lat1, lon1, lat2, lon2) -> float`
- `build_matrices(lats, lons, road_factor, speed_kmph) -> (dist_km: np.ndarray, time_sec: np.ndarray)`
  - Index 0 is the store; indices 1..n are orders in CSV order.
  - `dist_km[i][j]` = haversine × road_factor
  - `time_sec[i][j]` = round(dist_km / speed × 3600) as **int** (OR-Tools needs integers)
  - Diagonal = 0; symmetric.
- Keep the interface generic so a future version can swap in real road distances (OSRM) without changing the solver.

### `src/models.py`

```python
@dataclass
class Params:
    store_lat: float
    store_lon: float
    promise_min: float = 15
    speed_kmph: float = 25
    road_factor: float = 1.3
    service_min: float = 2
    capacity_items: int = 10
    time_limit_s: int = 10

@dataclass
class Instance:          # everything a solver needs
    order_ids: list[str]
    lats: list[float]    # index 0 = store
    lons: list[float]
    demand: list[int]    # index 0 = 0
    deadline_sec: list[int]   # index 0 = large value
    dist_km: np.ndarray
    time_sec: np.ndarray
    service_sec: int
    capacity: int

@dataclass
class Stop:
    order_id: str
    sequence: int
    arrival_min: float
    deadline_min: float
    slack_min: float     # deadline - arrival
    items: int
    load_after: int      # cumulative items delivered so far on this route

@dataclass
class Route:
    rider_id: int
    stops: list[Stop]
    distance_km: float   # incl. return to store
    duration_min: float  # until back at store, incl. handovers
    items: int

@dataclass
class Solution:
    method: str          # "optimized" | "greedy_baseline" | "one_per_rider"
    routes: list[Route]
    riders_used: int
    total_distance_km: float
    total_travel_min: float
    avg_slack_min: float
    min_slack_min: float
    late_orders: int
    solve_time_s: float
    status: str
```

Also provide `build_instance(orders_df: pd.DataFrame, params: Params) -> Instance`, which computes deadlines (deadline = (promise − minutes_since_placed) in seconds) and the matrices, and `check_feasibility(instance) -> list[str]`, which returns IDs of orders that can never be served (direct travel > deadline, or items > capacity).

---

## 6. Step 4 — Solver (`src/solver.py`)

`solve(instance: Instance, params: Params) -> Solution` using `ortools.constraint_solver.pywrapcp`.

1. Run `check_feasibility`; if any order is infeasible, raise a clear `ValueError` listing them.
2. `RoutingIndexManager(n_nodes, num_vehicles=n_orders, depot=0)`: one potential rider per order = effectively unlimited fleet.
3. **Arc cost callback:** `time_sec[i][j]` (travel only). `SetArcCostEvaluatorOfAllVehicles`.
4. **Time dimension:** a separate transit callback = `time_sec[i][j] + (service_sec if i != 0 else 0)`, so the cumul at a node equals the arrival time (handover is added when leaving it, matching the MILP). `AddDimension(callback, slack_max=0, capacity=<horizon>, fix_start_cumul_to_zero=True, "Time")`, horizon e.g. 4 hours in seconds. For each order node, `time_dim.CumulVar(index).SetMax(deadline_sec[i])`. Do not constrain the return-to-store time.
5. **Capacity dimension:** demand callback; `AddDimensionWithVehicleCapacity(cb, 0, [capacity]*num_vehicles, True, "Capacity")`.
6. **Fixed cost per rider:** `SetFixedCostOfAllVehicles(F)` with `F = sum over i of max_j time_sec[i][j] + 1`, which guarantees riders are minimized first.
7. **Search parameters:** first solution `PARALLEL_CHEAPEST_INSERTION`; local search metaheuristic `GUIDED_LOCAL_SEARCH`; time limit `params.time_limit_s`.
8. Extract routes (skip empty vehicles), renumber riders 1..k, fill `Stop`/`Route`, compute KPIs via `src/kpis.py`. Record wall-clock solve time and solver status.

---

## 7. Step 5 — Baselines (`src/baseline.py`)

### 7a. `greedy_baseline(instance) -> Solution`

Simulates a store manager batching by hand:

1. Sort unassigned orders by deadline (most urgent first).
2. Start a new rider with the most urgent unassigned order.
3. Repeatedly look at the **nearest** unassigned order to the rider's last stop; append it if capacity still holds **and** its arrival time ≤ its deadline (appending at the end never changes earlier arrivals). If it does not fit, try the next nearest; stop when nothing fits.
4. Close the route (return to store); repeat from step 2 until all orders are assigned.

This never produces late orders (every order is individually feasible), so the comparison against the optimizer is on riders used and distance.

### 7b. `one_per_rider(instance) -> Solution`

Each order gets its own rider (store → customer → store). Reference figure only.

### `src/kpis.py`

One shared function that takes routes and the instance and returns all `Solution` KPI fields, so all three methods are measured identically.

---

## 8. `scripts/run_demo.py`

Loads `data/sample_orders.csv` with default params, runs all three methods, and prints:

- a comparison table: method, riders used, total distance (km), total travel (min), avg slack, min slack, late orders, solve time;
- the optimized routes, one line per rider: `Rider 3: O12 → O07 → O31 | 9 items | 6.4 km | back at 21.5 min`.

Also writes:

- `outputs/optimized_plan.csv` (one row per stop: rider_id, sequence, order_id, arrival_min, deadline_min, slack_min, items, load_after);
- `outputs/debug_map.html`: a quick Folium map (store marker, customer markers, one coloured polyline per rider) for visual sanity checking only. The polished map is part of step 6.

---

## 9. Tests (`pytest`)

- **distance:** zero diagonal, symmetric, a known pair of points within 1% of the expected haversine distance.
- **generator:** exactly 45 rows; same seed gives identical output; all orders within 2.5 km; all orders individually feasible.
- **solver:**
  - every order appears in exactly one route;
  - every route's items ≤ capacity;
  - every arrival ≤ deadline;
  - riders used ≤ greedy baseline riders;
  - tiny hand case: two orders 100 m apart, both small, generous deadlines → 1 rider;
  - tiny hand case: two orders on opposite sides with tight deadlines → 2 riders;
  - infeasible order (deadline shorter than direct travel) → `ValueError` naming it.
- **baseline:** every order assigned once; no late orders; capacity respected.

---

## 10. Definition of done (for this spec)

- `pip install -r requirements.txt` works on a clean environment.
- `python data/generate_orders.py` produces the 45-order CSV.
- `python scripts/run_demo.py` runs in under ~20 s and prints the comparison table and routes.
- `pytest` passes.
- README explains how to run each step, the assumptions in Section 1, and the known limitations (synthetic data, straight-line × road factor distances, single wave, all orders ready at time 0, heuristic solver without an optimality proof).
