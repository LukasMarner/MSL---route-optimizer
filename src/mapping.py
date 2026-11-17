"""Folium route map, shared by the CLI demo and the UI."""
from __future__ import annotations

import folium

from src.distance import OSRMError, get_route_geometry
from src.models import Instance, Solution

# 20 distinguishable colours (Tableau 20); riders beyond 20 reuse them
PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
           "#bcbd22", "#17becf", "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5", "#c49c94",
           "#f7b6d2", "#c7c7c7", "#dbdb8d", "#9edae5"]


def rider_color(rider_id: int) -> str:
    return PALETTE[(rider_id - 1) % len(PALETTE)]


def route_geometries(solution: Solution, instance: Instance, cache_dir=None, timeout=10):
    """Street paths per rider from OSRM: ({rider_id: [(lat, lon), ...]}, [rider_ids that failed]).

    Riders whose request fails are left out, so the map draws them as straight lines.
    """
    index = {oid: i for i, oid in enumerate(instance.order_ids, start=1)}
    geoms, failed = {}, []
    for r in solution.routes:
        nodes = [0] + [index[s.order_id] for s in r.stops] + [0]
        try:
            geoms[r.rider_id] = get_route_geometry([(instance.lats[n], instance.lons[n]) for n in nodes],
                                                   cache_dir=cache_dir, timeout=timeout)
        except OSRMError:
            failed.append(r.rider_id)
    return geoms, failed


def route_map(solution: Solution, instance: Instance, highlight_rider: int | None = None,
              geometries: dict[int, list[tuple[float, float]]] | None = None) -> folium.Map:
    """Store, customers and one coloured line per rider. highlight_rider fades all other routes.

    geometries: optional street paths per rider (from route_geometries); others are drawn straight.
    """
    m = folium.Map(location=[instance.lats[0], instance.lons[0]], zoom_start=14, tiles="OpenStreetMap")
    index = {oid: i for i, oid in enumerate(instance.order_ids, start=1)}
    for r in solution.routes:
        color = rider_color(r.rider_id)
        faded = highlight_rider is not None and r.rider_id != highlight_rider
        opacity = 0.15 if faded else 0.9
        nodes = [0] + [index[s.order_id] for s in r.stops] + [0]
        layer = folium.FeatureGroup(name=f"Rider {r.rider_id}")
        path = (geometries or {}).get(r.rider_id) or [(instance.lats[n], instance.lons[n]) for n in nodes]
        folium.PolyLine(path, color=color,
                        weight=4, opacity=opacity, tooltip=f"Rider {r.rider_id}").add_to(layer)
        for s in r.stops:
            i = index[s.order_id]
            folium.CircleMarker(
                [instance.lats[i], instance.lons[i]], radius=7, color=color, weight=2,
                fill=True, fill_color=color, fill_opacity=opacity, opacity=opacity,
                tooltip=(f"<b>{s.order_id}</b> · rider {r.rider_id}, stop {s.sequence}<br>"
                         f"arrive {s.arrival_min:.1f} min · deadline {s.deadline_min:.1f} min<br>"
                         f"slack {s.slack_min:.1f} min · {s.items} items"),
            ).add_to(layer)
        layer.add_to(m)
    folium.Marker([instance.lats[0], instance.lons[0]], tooltip="Dark store",
                  icon=folium.Icon(color="black", icon="home")).add_to(m)
    m.fit_bounds([[min(instance.lats), min(instance.lons)], [max(instance.lats), max(instance.lons)]], padding=(20, 20))
    return m
