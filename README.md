# Dark-Store Route Optimizer

University optimization project. A quick-commerce dark store (modelled on the Blinkit store at K5, Block K,
Malviya Nagar, New Delhi) receives a wave of orders. The tool decides **how many riders are needed** and
**which orders each rider delivers, in what order**, so every order arrives before its deadline and no bag is
overloaded.

The problem is a **Capacitated Vehicle Routing Problem with Time Windows (CVRPTW) in fleet-sizing mode**,
solved with the Google OR-Tools routing library. The objective is lexicographic: minimize riders first, then
total travel time. A large fixed cost per rider enforces the ordering.

The full build spec is in [`docs/spec.md`](docs/spec.md).

## Setup

```bash
uv venv --python 3.12 .venv          # or: python -m venv .venv
uv pip install --python .venv/bin/python -r requirements.txt
source .venv/bin/activate
```

## Running each step

| Step | Command | What it does |
|---|---|---|
| 1 Environment | `python scripts/check_env.py` | Prints library versions and solves a 3-node OR-Tools example |
| 2 Data | `python data/generate_orders.py` | Writes `data/sample_orders.csv` (45 orders, seed 42) |
|   | `python scripts/check_step2.py` | 5-order sample, summary stats and a distance histogram |
| 3 Matrix | `python scripts/check_step3.py` | Prints fixture matrices and full 46×46 matrix stats |
| 4 Solver | `python scripts/check_step4.py` | Solves every tiny fixture and the full data; runs the independent checker |
| 5 Baselines | `python scripts/check_step5.py` | Baselines on the fixtures plus the 3-method comparison |
| Demo | `python scripts/run_demo.py` | Comparison table, routes, `outputs/optimized_plan.csv`, `outputs/debug_map.html` |
| 6 App | `streamlit run app.py` | Web UI: sample / upload / generate orders, tune parameters, compare methods, route map, CSV download |
| OSRM | `python scripts/check_osrm.py` | Straight-line vs road matrices side by side on tiny fixtures; street-path maps in `outputs/` |
|   | `python scripts/compare_distance_methods.py` | 45-order wave under both distance methods |
| Tests | `pytest` | 44 tests (~25 s), fully offline, incl. app smoke tests |

Tiny hand-checkable fixtures are in `tests/fixtures/` (regenerate with `python tests/fixtures/make_fixtures.py`).

## Deploying (Streamlit Community Cloud)

1. Push this repo to GitHub.
2. On [share.streamlit.io](https://share.streamlit.io) → **Create app** → *Deploy a public app from GitHub*.
3. Repository: this repo, branch `main`, main file `app.py`. Under **Advanced settings** pick Python **3.12**.
4. Deploy. Dependencies come from `requirements.txt`; no secrets are needed.

The committed `data/osrm_cache/` lets the sample wave load instantly. New coordinates call the public OSRM server
from the cloud machine, and fall back to straight line if it is unreachable.

## Layout

```
config.py              default parameters
data/generate_orders.py  synthetic order generator -> data/sample_orders.csv
src/models.py          Params, Instance, Stop, Route, Solution; build_instance, check_feasibility
src/distance.py        haversine + travel-time matrices
src/solver.py          OR-Tools CVRPTW solver
src/baseline.py        greedy urgent-first nearest-neighbour; one order per rider
src/kpis.py            shared route/KPI computation (all methods measured identically)
src/checker.py         independent re-verification of any Solution
src/orders.py          validation of uploaded order tables
src/report.py          comparison / route / stop tables
src/mapping.py         Folium route map
app.py                 Streamlit UI
scripts/               step checkpoints and the end-to-end demo
tests/                 pytest suite
```

`src/` has no Streamlit imports and all functions take their parameters explicitly, so the future UI can import
it directly.

## Input CSV format

| column | type | description |
|---|---|---|
| `order_id` | str | e.g. `O01` |
| `lat`, `lon` | float | customer location |
| `items` | int | 1–10 |
| `minutes_since_placed` | float | age of the order at dispatch; deadline = promise − age |

## Assumptions (edit `config.py`)

| Parameter | Default |
|---|---|
| Store | 28.5319608, 77.2131596 |
| Delivery radius | 2.5 km (min 0.2 km) |
| Delivery promise | 20 min from order placement (spec default was 15) |
| Order age at dispatch | uniform 0–5 min |
| Rider speed | 25 km/h |
| Distance method | `osrm` (road network) or `straight_line` |
| Road factor | 1.3 × straight-line distance (straight-line mode and OSRM fallback) |
| Handover per drop | 2 min |
| Bag capacity | 10 items |
| Order size | 50% 1–3, 35% 4–6, 15% 7–10 items (uniform within band) |
| Orders | 45, seed 42 |
| Solver time limit | 10 s |

"Total travel" counts riding time only. Route duration (back-at-store time) also includes handovers.

## Distance methods

- **Road network (default)**: one request to the public OSRM table service (`annotations=distance`) gives the
  full road-distance matrix; travel time = distance / our rider speed (OSRM's car durations are ignored). The matrix
  can be asymmetric (one-way streets). Street paths for the map come from the OSRM route service, one request per rider.
- **Straight line**: haversine × road factor; symmetric; no network.
- Responses are cached as JSON in `data/osrm_cache/`, keyed by a hash of the coordinates, so repeated runs and
  the demo work offline. Tiny-fixture responses are recorded in `tests/fixtures/osrm_cache/` for the tests.
- If OSRM fails, times out, or a pair is unroutable, the run falls back to straight line and the UI/demo shows a
  warning. Requests are throttled to ~1/s (public server policy); the first uncached map of a large plan can take
  ~20–45 s.
- OSRM snaps each point to the nearest road before measuring, so very short pairs can come out slightly *shorter*
  than straight line.
- On this sample, road distances average ~1.6× straight line (vs the 1.3 road factor). With a 15-min promise that
  makes **O05 and O23 undeliverable**; with the 20-min default every order is reachable. The app and demo skip
  undeliverable orders with a warning.

## Model notes

- Time dimension: transit = travel + handover at the node being left, so the cumul at a node equals the
  arrival time. Each order's cumul is capped at its deadline; the return to the store is not constrained.
- Rider fixed cost F = Σ over orders of (longest arc out of that order) + n × (longest arc out of the store) + 1.
  This bounds any solution's total travel from above, so saving one rider always outweighs any travel saving.
  (The spec's original formula counted the store's outgoing arc only once, although each rider leaves the store.)
- The fleet is effectively unlimited: one potential rider per order.

## Known limitations

- **Synthetic data**: locations are uniform over a disk and can land in parks or non-residential land.
- **Distances**: OSRM uses the public demo server (car profile, no traffic); rider speed is a flat average.
  The sample generator still guarantees feasibility with the straight-line estimate, not road distances.
- **Single wave**: all orders are ready at time 0; no rolling arrivals and no riders returning for a second trip.
- **Heuristic solver**: OR-Tools guided local search gives good solutions within the time limit but no
  optimality proof. A PuLP MILP for validating small instances is planned.
