import config
from data.generate_orders import generate_orders
from src.distance import haversine_km


def test_row_count_and_columns():
    df = generate_orders()
    assert len(df) == 45
    assert list(df.columns) == ["order_id", "lat", "lon", "items", "minutes_since_placed"]
    assert df.order_id.iloc[0] == "O01" and df.order_id.iloc[-1] == "O45"


def test_same_seed_identical():
    assert generate_orders(seed=42).equals(generate_orders(seed=42))


def test_within_radius():
    df = generate_orders()
    d = haversine_km(config.STORE_LAT, config.STORE_LON, df.lat, df.lon)
    assert (d <= config.RADIUS_KM + 1e-3).all()


def test_value_ranges():
    df = generate_orders()
    assert df["items"].between(1, 10).all()
    assert df.minutes_since_placed.between(0, 5).all()


def test_individually_feasible():
    df = generate_orders()
    d = haversine_km(config.STORE_LAT, config.STORE_LON, df.lat, df.lon)
    direct_min = d * config.ROAD_FACTOR / config.SPEED_KMPH * 60
    assert (direct_min <= config.PROMISE_MIN - df.minutes_since_placed).all()
    assert (df["items"] <= config.CAPACITY_ITEMS).all()
