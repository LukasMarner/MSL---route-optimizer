"""Step 3: distance and travel-time matrices.

Two methods share one interface (index 0 = store, returns dist_km float matrix + time_sec int matrix):
- straight line: haversine x road factor (symmetric, offline);
- road network: OSRM table service distances (may be asymmetric), cached to disk.
Travel time always comes from our own rider speed, never from OSRM's car durations.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
from pathlib import Path

import numpy as np

EARTH_RADIUS_KM = 6371.0088
OSRM_URL = "http://router.project-osrm.org"
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "osrm_cache"
MIN_REQUEST_INTERVAL_S = 1.0  # public demo server policy: max ~1 request/second

_last_request = 0.0


class OSRMError(RuntimeError):
    """OSRM could not provide a usable answer (network, HTTP, or routing failure)."""


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km. Works on scalars or numpy arrays."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def _time_matrix(dist_km, speed_kmph):
    return np.rint(dist_km / speed_kmph * 3600).astype(int)


def build_matrices(lats, lons, road_factor, speed_kmph):
    """Straight-line method. Index 0 = store. Returns (dist_km float matrix, time_sec int matrix)."""
    lats, lons = np.asarray(lats, dtype=float), np.asarray(lons, dtype=float)
    dist_km = haversine_km(lats[:, None], lons[:, None], lats[None, :], lons[None, :]) * road_factor
    dist_km = (dist_km + dist_km.T) / 2  # exact symmetry
    np.fill_diagonal(dist_km, 0.0)
    return dist_km, _time_matrix(dist_km, speed_kmph)


# ---------- OSRM ----------
def _coord_string(lats, lons):
    return ";".join(f"{float(lon):.6f},{float(lat):.6f}" for lat, lon in zip(lats, lons))


def _cache_path(kind, coords, cache_dir):
    key = hashlib.sha256(f"{kind}|{coords}".encode()).hexdigest()[:20]
    return Path(cache_dir) / f"{kind}_{key}.json"


def _fetch_json(url, timeout):
    """One HTTP GET to OSRM, throttled to the public server's rate limit."""
    global _last_request
    wait = MIN_REQUEST_INTERVAL_S - (time.monotonic() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.monotonic()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
    except (OSError, ValueError) as e:  # URLError/HTTPError/timeouts are OSError; bad JSON is ValueError
        raise OSRMError(f"request failed: {e}") from e
    if data.get("code") != "Ok":
        raise OSRMError(f"OSRM returned {data.get('code')}: {data.get('message', '')}")
    return data


def _cached_request(kind, coords, url, extract, cache_dir, timeout):
    """Returns extract(response), reading/writing a JSON cache keyed by the coordinates."""
    path = _cache_path(kind, coords, cache_dir or DEFAULT_CACHE_DIR)
    if path.exists():
        return json.loads(path.read_text())
    result = extract(_fetch_json(url, timeout))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result))
    return result


def osrm_distance_km(lats, lons, cache_dir=None, timeout=10, base_url=OSRM_URL):
    """Full road-distance matrix in km from one OSRM table request (rows = from, cols = to)."""
    coords = _coord_string(lats, lons)
    url = f"{base_url}/table/v1/driving/{coords}?annotations=distance"
    distances = _cached_request("table", coords, url, lambda d: {"distances": d["distances"]},
                                cache_dir, timeout)["distances"]
    dist = np.array([[np.nan if v is None else v for v in row] for row in distances], dtype=float) / 1000
    if dist.shape != (len(lats), len(lats)):
        raise OSRMError(f"unexpected matrix shape {dist.shape}")
    if np.isnan(dist).any():
        raise OSRMError(f"{int(np.isnan(dist).sum())} point pair(s) not routable")
    np.fill_diagonal(dist, 0.0)
    return dist


def build_matrices_osrm(lats, lons, speed_kmph, cache_dir=None, timeout=10):
    """Road-network method. Same interface as build_matrices; raises OSRMError on failure."""
    dist_km = osrm_distance_km(lats, lons, cache_dir=cache_dir, timeout=timeout)
    return dist_km, _time_matrix(dist_km, speed_kmph)


def get_route_geometry(points, cache_dir=None, timeout=10, base_url=OSRM_URL):
    """Street path through points [(lat, lon), ...] in order, as [(lat, lon), ...]. Raises OSRMError."""
    lats, lons = zip(*points)
    coords = _coord_string(lats, lons)
    url = f"{base_url}/route/v1/driving/{coords}?overview=full&geometries=geojson"

    def extract(d):
        route = d["routes"][0]
        return {"coordinates": route["geometry"]["coordinates"], "distance_m": route["distance"]}

    result = _cached_request("route", coords, url, extract, cache_dir, timeout)
    return [(lat, lon) for lon, lat in result["coordinates"]]
