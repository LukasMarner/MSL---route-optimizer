"""Step 6: Streamlit UI for the dark-store route optimizer.  Run: streamlit run app.py"""
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

import config
from data.generate_orders import generate_orders
from src.baseline import greedy_baseline, one_per_rider
from src.checker import verify_solution
from src.mapping import route_geometries, route_map
from src.models import OSRM, STRAIGHT_LINE, Params, build_instance, check_feasibility
from src.orders import REQUIRED_COLUMNS, validate_orders
from src.report import comparison_table, plan_table, route_table
from src.solver import solve

ROOT = Path(__file__).resolve().parent
DISTANCE_LABELS = {OSRM: "Road network (OSRM)", STRAIGHT_LINE: "Straight-line estimate"}
METHOD_LABELS = {"optimized": "Optimized (OR-Tools)", "greedy_baseline": "Greedy baseline", "one_per_rider": "One order per rider"}

st.set_page_config(page_title="Dark-Store Route Optimizer", page_icon="🛵", layout="wide")


# ---------- sidebar: inputs ----------
def sidebar_inputs():
    st.sidebar.header("Orders")
    source = st.sidebar.radio("Source", ["Sample wave (45 orders)", "Upload CSV", "Generate new wave"], label_visibility="collapsed")

    st.sidebar.header("Parameters")
    distance_method = st.sidebar.radio(
        "Distance method", list(DISTANCE_LABELS), format_func=DISTANCE_LABELS.get,
        help="Road network uses real street distances from the public OSRM server (cached on disk); "
             "straight-line uses haversine × road factor. Travel time always uses the rider speed below.")
    with st.sidebar.expander("Store", expanded=False):
        store_lat = st.number_input("Store latitude", value=config.STORE_LAT, format="%.7f")
        store_lon = st.number_input("Store longitude", value=config.STORE_LON, format="%.7f")
    promise = st.sidebar.slider("Delivery promise (min)", 5, 30, int(config.PROMISE_MIN))
    capacity = st.sidebar.slider("Bag capacity (items)", 4, 30, config.CAPACITY_ITEMS)
    speed = st.sidebar.slider("Rider speed (km/h)", 10, 40, int(config.SPEED_KMPH))
    road_factor = st.sidebar.slider("Road factor (× straight line)", 1.0, 2.0, float(config.ROAD_FACTOR), 0.05,
                                    help="Used by the straight-line method, and as the fallback if OSRM is unreachable.")
    service = st.sidebar.slider("Handover per drop (min)", 0.0, 5.0, float(config.SERVICE_MIN), 0.5)
    time_limit = st.sidebar.slider("Solver time limit (s)", 1, 60, config.TIME_LIMIT_S,
                                   help="Guided local search always uses the full limit.")
    params = Params(store_lat=store_lat, store_lon=store_lon, promise_min=promise, speed_kmph=speed,
                    road_factor=road_factor, service_min=service, capacity_items=capacity, time_limit_s=time_limit,
                    distance_method=distance_method)

    orders = None
    if source.startswith("Sample"):
        orders = pd.read_csv(ROOT / "data" / "sample_orders.csv")
    elif source == "Upload CSV":
        st.sidebar.caption(f"Columns: `{'`, `'.join(REQUIRED_COLUMNS)}`")
        file = st.sidebar.file_uploader("Orders CSV", type="csv")
        if file is not None:
            try:
                orders = pd.read_csv(file)
            except Exception as e:  # malformed CSV
                st.error(f"Could not read the CSV: {e}")
                st.stop()
    else:
        n = st.sidebar.slider("Number of orders", 5, 80, config.N_ORDERS)
        seed = st.sidebar.number_input("Random seed", value=config.SEED, step=1)
        radius = st.sidebar.slider("Delivery radius (km)", 1.0, 4.0, config.RADIUS_KM, 0.5)
        orders = generate_orders(
            n=n, store_lat=store_lat, store_lon=store_lon, radius_km=radius, seed=int(seed),
            promise_min=promise, speed_kmph=speed, road_factor=road_factor, capacity_items=capacity,
            item_bands=[(p, lo, min(hi, capacity)) for p, lo, hi in config.ITEM_BANDS if lo <= capacity],
        )
    return orders, params


def make_instance(orders: pd.DataFrame, params: Params):
    # not st-cached: a fallback after an OSRM outage must not stick; OSRM responses are disk-cached anyway
    return build_instance(orders, params)


@st.cache_data(show_spinner=False, ttl="10m")
def street_paths(_solution, _instance, key):
    """OSRM street geometry per rider (disk-cached; first fetch is rate-limited to ~1 request/s)."""
    return route_geometries(_solution, _instance)


@st.cache_data(show_spinner=False, ttl="10m")
def run_all(orders: pd.DataFrame, params: Params):
    instance = make_instance(orders, params)
    solutions = [solve(instance, params), greedy_baseline(instance), one_per_rider(instance)]
    problems = {s.method: verify_solution(s, instance) for s in solutions}
    return instance, solutions, problems


# ---------- main ----------
st.title("🛵 Dark-Store Route Optimizer")
st.caption("How many riders does this wave need, and who delivers what, in which order? "
           "Capacitated vehicle routing with time windows — fewest riders first, then least travel.")

orders, params = sidebar_inputs()
if orders is None:
    st.info("Upload an orders CSV in the sidebar to begin.")
    st.stop()

errors = validate_orders(orders)
if errors:
    st.error("The orders file has problems:\n\n" + "\n".join(f"- {e}" for e in errors))
    st.stop()
orders = orders[REQUIRED_COLUMNS].copy()
orders["order_id"] = orders["order_id"].astype(str)
orders["items"] = orders["items"].astype(int)

with st.spinner("Getting distances…"):
    precheck = make_instance(orders, params)
if precheck.distance_warning:
    st.warning(precheck.distance_warning, icon="⚠️")
infeasible = check_feasibility(precheck)
if infeasible:
    st.warning(f"**{len(infeasible)} order(s) can never be delivered on time or don't fit in one bag**, "
               f"even with a dedicated rider: {', '.join(infeasible)}.")
    if not st.checkbox("Plan the remaining orders without them"):
        st.stop()
    orders = orders[~orders["order_id"].isin(infeasible)].reset_index(drop=True)
    if orders.empty:
        st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Orders in wave", len(orders))
c2.metric("Total items", int(orders["items"].sum()))
c3.metric("Riders needed at least (bag capacity)", -(-int(orders["items"].sum()) // params.capacity_items))
with st.expander("View orders"):
    st.dataframe(orders, hide_index=True, width="stretch")

run_key = (pd.util.hash_pandas_object(orders).sum(), params)
if st.button("Optimize routes", type="primary"):
    with st.spinner(f"Solving (up to {params.time_limit_s} s)…"):
        st.session_state["result"] = run_all(orders, params)
        st.session_state["result_key"] = run_key

if "result" not in st.session_state:
    st.stop()
if st.session_state["result_key"] != run_key:
    st.info("Inputs changed since the last run — click **Optimize routes** to update.")
    st.stop()

instance, solutions, problems = st.session_state["result"]
by_method = {s.method: s for s in solutions}
opt, greedy = by_method["optimized"], by_method["greedy_baseline"]

for method, errs in problems.items():
    if errs:
        st.error(f"{METHOD_LABELS[method]} failed independent verification: " + "; ".join(errs[:5]))

st.subheader("Result")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Riders", opt.riders_used, delta=opt.riders_used - greedy.riders_used, delta_color="inverse",
          help="Change vs. greedy baseline")
m2.metric("Total distance", f"{opt.total_distance_km:.1f} km",
          delta=f"{opt.total_distance_km - greedy.total_distance_km:+.1f} km", delta_color="inverse",
          help="Change vs. greedy baseline")
m3.metric("Tightest slack", f"{opt.min_slack_min:.1f} min", help="Smallest margin between arrival and deadline")
m4.metric("Late orders", opt.late_orders)
st.caption(f"Distances: **{DISTANCE_LABELS[instance.distance_method]}** · solver status `{opt.status}` · "
           f"{opt.solve_time_s:.1f} s · heuristic, no optimality proof.")

comp = comparison_table(solutions)
comp["method"] = comp["method"].map(METHOD_LABELS)
st.dataframe(comp, hide_index=True, width="stretch", column_config={
    "method": "Method", "riders": "Riders", "distance_km": "Distance (km)", "travel_min": "Riding time (min)",
    "avg_slack_min": "Avg slack (min)", "min_slack_min": "Min slack (min)", "late": "Late", "solve_s": "Solve (s)",
})

st.subheader("Routes")
left, right = st.columns([2, 3])
with left:
    method = st.selectbox("Plan", list(METHOD_LABELS), format_func=METHOD_LABELS.get)
    shown = by_method[method]
    rider = st.selectbox("Highlight rider", ["All"] + [r.rider_id for r in shown.routes])
    st.dataframe(route_table(shown), hide_index=True, width="stretch", height=420)
    st.download_button("Download stop-by-stop plan (CSV)", plan_table(shown).to_csv(index=False),
                       file_name=f"{method}_plan.csv", mime="text/csv")
with right:
    geometries = None
    if instance.distance_method == OSRM:
        with st.spinner("Fetching street paths…"):
            geometries, failed = street_paths(shown, instance, (st.session_state["result_key"], method))
        if failed:
            st.warning(f"No street path for rider(s) {', '.join(map(str, failed))}; drawn as straight lines.")
    fmap = route_map(shown, instance, highlight_rider=None if rider == "All" else rider, geometries=geometries)
    st_folium(fmap, height=560, use_container_width=True, returned_objects=[], key="map")

if rider != "All":
    route = next(r for r in shown.routes if r.rider_id == rider)
    st.markdown(f"**Rider {rider}** — {route.items} items · {route.distance_km:.1f} km · back at store at {route.duration_min:.1f} min")
    st.dataframe(plan_table(shown).query("rider_id == @rider").drop(columns="rider_id"),
                 hide_index=True, width="stretch")
