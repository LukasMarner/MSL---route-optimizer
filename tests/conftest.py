import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import distance  # noqa: E402


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests run offline: any OSRM request that is not served from a cache fails like an outage."""
    def offline(url, timeout):
        raise distance.OSRMError("network disabled in tests")
    monkeypatch.setattr(distance, "_fetch_json", offline)
