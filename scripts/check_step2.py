import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np
import config
from data.generate_orders import generate_orders
from src.distance import haversine_km

d5 = generate_orders(n=5)
d5["dist_km"] = haversine_km(config.STORE_LAT, config.STORE_LON, d5.lat, d5.lon).round(3)
print(d5.to_string(index=False))
print("same seed identical:", d5.drop(columns="dist_km").equals(generate_orders(n=5)))
print("different seed differs:", not generate_orders(n=5, seed=7).equals(generate_orders(n=5)))

df = generate_orders()
df["dist_km"] = haversine_km(config.STORE_LAT, config.STORE_LON, df.lat, df.lon)
print("\n45-order summary:\n", df.describe().loc[["min", "max", "mean"]].round(3).to_string())
print("\nitems counts:", df["items"].value_counts().sort_index().to_dict())
print("\nstraight-line distance histogram:")
counts, edges = np.histogram(df.dist_km, bins=np.arange(0, 2.75, 0.25))
for c, lo, hi in zip(counts, edges, edges[1:]):
    print(f"  {lo:4.2f}-{hi:4.2f} km | {'#' * c} {c}")
