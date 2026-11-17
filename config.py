"""Default parameters (spec Section 1). Edit here to change defaults."""

STORE_LAT = 28.5319608          # D1: Blinkit, K5, Block K, Malviya Nagar
STORE_LON = 77.2131596
RADIUS_KM = 2.5                 # D2
MIN_RADIUS_KM = 0.2
PROMISE_MIN = 20                # D3 (spec default was 15)
MAX_AGE_MIN = 5                 # D4
SPEED_KMPH = 25                 # D5
ROAD_FACTOR = 1.3               # D6
SERVICE_MIN = 2                 # D7
CAPACITY_ITEMS = 10             # D8
# D9: (probability, low, high) bands for items, uniform within each band
ITEM_BANDS = [(0.50, 1, 3), (0.35, 4, 6), (0.15, 7, 10)]
N_ORDERS = 45                   # D10
SEED = 42                       # D11
TIME_LIMIT_S = 10               # D12
DISTANCE_METHOD = "osrm"        # "osrm" (road network, cached in data/osrm_cache) | "straight_line"
