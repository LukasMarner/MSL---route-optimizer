"""Writes the tiny hand-checkable fixtures. 0.009 deg lat ~= 1.0 km."""
from pathlib import Path

import numpy as np
import pandas as pd

STORE_LAT, STORE_LON = 28.5319608, 77.2131596
KM_LAT = 0.009
KM_LON = 0.009 / np.cos(np.radians(STORE_LAT))  # ~1 km east
HERE = Path(__file__).parent


def write(name, rows):
    df = pd.DataFrame(
        [(oid, round(STORE_LAT + n * KM_LAT, 6), round(STORE_LON + e * KM_LON, 6), items, age)
         for oid, n, e, items, age in rows],
        columns=["order_id", "lat", "lon", "items", "minutes_since_placed"],
    )
    df.to_csv(HERE / f"{name}.csv", index=False)


# rows: (order_id, km north, km east, items, age)
write("tiny_1_order", [("A", 1, 0, 3, 0)])
write("tiny_2_close", [("A", 1, 0, 2, 0), ("B", 1, 0.1, 2, 0)])
write("tiny_2_opposite", [("N", 2, 0, 2, 9), ("S", -2, 0, 2, 9)])
write("tiny_2_capacity", [("A", 1, 0, 6, 0), ("B", 1, 0.1, 6, 0)])
write("tiny_infeasible", [("FAR", 5, 0, 2, 10)])
write("tiny_6_orders", [
    ("N1", 1.0, 0.0, 2, 0), ("N2", 1.1, 0.1, 3, 0), ("N3", 0.9, -0.1, 2, 0),
    ("E1", 0.0, 1.0, 3, 0), ("E2", 0.1, 1.1, 2, 0), ("E3", -0.1, 0.9, 3, 0),
])
