from pathlib import Path

import pandas as pd

import config
from src.models import Params, build_instance

FIXTURES = Path(__file__).parent / "fixtures"
# Fixture settings from the spec: easy arithmetic (2 min per km)
FIXTURE_PARAMS = Params(config.STORE_LAT, config.STORE_LON, promise_min=15, speed_kmph=30,
                        road_factor=1.0, service_min=2, capacity_items=10, time_limit_s=1,
                        distance_method="straight_line")


def fixture_instance(name):
    return build_instance(pd.read_csv(FIXTURES / f"{name}.csv"), FIXTURE_PARAMS)
