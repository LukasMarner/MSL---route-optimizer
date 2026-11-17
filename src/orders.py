"""Validation of an uploaded / generated orders table (the CSV upload format)."""
from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ["order_id", "lat", "lon", "items", "minutes_since_placed"]


def validate_orders(df: pd.DataFrame) -> list[str]:
    """Returns human-readable problems; empty list means the table is usable."""
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return [f"Missing column(s): {', '.join(missing)}. Expected: {', '.join(REQUIRED_COLUMNS)}."]
    if df.empty:
        return ["The file has no orders."]
    errors = []
    for col in ["lat", "lon", "items", "minutes_since_placed"]:
        values = pd.to_numeric(df[col], errors="coerce")
        if values.isna().any():
            rows = (values.index[values.isna()] + 2).tolist()[:5]
            errors.append(f"Column '{col}' has missing or non-numeric values (CSV rows {rows}).")
    if errors:
        return errors
    if df["order_id"].isna().any():
        errors.append("Some orders have no order_id.")
    dupes = df["order_id"][df["order_id"].duplicated()].astype(str).unique().tolist()
    if dupes:
        errors.append(f"Duplicate order_id(s): {', '.join(dupes[:5])}.")
    items = pd.to_numeric(df["items"])
    if (items < 1).any() or (items != items.round()).any():
        errors.append("'items' must be whole numbers ≥ 1.")
    if (pd.to_numeric(df["minutes_since_placed"]) < 0).any():
        errors.append("'minutes_since_placed' must be ≥ 0.")
    if not pd.to_numeric(df["lat"]).between(-90, 90).all() or not pd.to_numeric(df["lon"]).between(-180, 180).all():
        errors.append("lat/lon out of range.")
    return errors
