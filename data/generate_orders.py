"""Step 2: synthetic order wave around the dark store."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from src.distance import haversine_km  # noqa: E402

KM_PER_DEG_LAT = 111.32


def _draw_items(rng, bands):
    probs = np.array([b[0] for b in bands], dtype=float)
    probs /= probs.sum()
    lo, hi = bands[rng.choice(len(bands), p=probs)][1:]
    return int(rng.integers(lo, hi + 1))


def _draw_location(rng, store_lat, store_lon, radius_km, min_radius_km):
    while True:
        r = radius_km * np.sqrt(rng.random())
        if r >= min_radius_km:
            break
    theta = rng.uniform(0, 2 * np.pi)
    dlat = r * np.sin(theta) / KM_PER_DEG_LAT
    dlon = r * np.cos(theta) / (KM_PER_DEG_LAT * np.cos(np.radians(store_lat)))
    return store_lat + dlat, store_lon + dlon


def generate_orders(
    n=config.N_ORDERS,
    store_lat=config.STORE_LAT,
    store_lon=config.STORE_LON,
    radius_km=config.RADIUS_KM,
    seed=config.SEED,
    min_radius_km=config.MIN_RADIUS_KM,
    max_age_min=config.MAX_AGE_MIN,
    item_bands=config.ITEM_BANDS,
    promise_min=config.PROMISE_MIN,
    speed_kmph=config.SPEED_KMPH,
    road_factor=config.ROAD_FACTOR,
    capacity_items=config.CAPACITY_ITEMS,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    while len(rows) < n:
        lat, lon = _draw_location(rng, store_lat, store_lon, radius_km, min_radius_km)
        items = _draw_items(rng, item_bands)
        age = round(float(rng.uniform(0, max_age_min)), 1)
        # Feasibility guarantee: resample any order that could never be served alone.
        direct_min = haversine_km(store_lat, store_lon, lat, lon) * road_factor / speed_kmph * 60
        if direct_min > promise_min - age or items > capacity_items:
            continue
        rows.append((f"O{len(rows) + 1:02d}", round(lat, 6), round(lon, 6), items, age))
    return pd.DataFrame(rows, columns=["order_id", "lat", "lon", "items", "minutes_since_placed"])


if __name__ == "__main__":
    df = generate_orders()
    out = ROOT / "data" / "sample_orders.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {len(df)} orders to {out}")
