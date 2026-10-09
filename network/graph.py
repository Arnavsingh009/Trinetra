from typing import Dict, Tuple, Any
import numpy as np
import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, LineString, MultiLineString
from scipy.spatial import cKDTree


def build_road_graph(roads_gdf: gpd.GeoDataFrame) -> nx.Graph:
    """
    Construct an undirected NetworkX graph from a normalized road GeoDataFrame.
    Nodes are rounded (lon, lat) tuples; edges store distance in meters and road attributes.
    """
    G = nx.Graph()

    if roads_gdf.empty:
        return G

    # Reproject to Web Mercator (EPSG:3857) to compute accurate segment lengths in meters
    gdf_metric = roads_gdf.to_crs(epsg=3857)

    for idx, row in roads_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        lines = [geom] if geom.geom_type == "LineString" else list(geom.geoms)

        for line in lines:
            coords = list(line.coords)
            if len(coords) < 2:
                continue

            line_metric = gdf_metric.geometry.iloc[idx]
            total_length_m = float(line_metric.length) if line_metric is not None else 0.0
            avg_seg_length = max(1.0, total_length_m / max(1, len(coords) - 1))

            for i in range(len(coords) - 1):
                u = (round(coords[i][0], 6), round(coords[i][1], 6))
                v = (round(coords[i + 1][0], 6), round(coords[i + 1][1], 6))

                sub_geom = LineString([Point(coords[i]), Point(coords[i + 1])])

                if u not in G:
                    G.add_node(u, pos=u, x=u[0], y=u[1])
                if v not in G:
                    G.add_node(v, pos=v, x=v[0], y=v[1])

                edge_data = {
                    "edge_id": f"{row.get('osm_id', idx)}_{i}",
                    "osm_id": row.get("osm_id"),
                    "name": row.get("name"),
                    "highway": row.get("highway"),
                    "bridge": row.get("bridge"),
                    "geometry": sub_geom,
                    "length_m": avg_seg_length,
                    "hazard_impact": 0.0,
                    "failed": False,
                }
                G.add_edge(u, v, **edge_data)

    return G


def build_walking_graph(roads_gdf: gpd.GeoDataFrame) -> nx.Graph:
    """
    Builds an undirected walking/footway graph.
    Includes walkable highways: footway, path, pedestrian, track, steps, living_street, residential.
    """
    G = nx.Graph()
    if roads_gdf.empty:
        return G

    walkable_tags = {
        "footway", "path", "pedestrian", "track", "steps",
        "living_street", "residential", "unclassified", "service"
    }

    gdf_metric = roads_gdf.to_crs(epsg=3857)

    for idx, row in roads_gdf.iterrows():
        highway_type = str(row.get("highway", "")).lower()
        if highway_type not in walkable_tags and row.get("foot") not in ["yes", "designated"]:
            continue

        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        lines = [geom] if geom.geom_type == "LineString" else list(geom.geoms)

        for line in lines:
            coords = list(line.coords)
            if len(coords) < 2:
                continue

            line_metric = gdf_metric.geometry.iloc[idx]
            total_length_m = float(line_metric.length) if line_metric is not None else 0.0
            avg_seg_length = max(1.0, total_length_m / max(1, len(coords) - 1))

            for i in range(len(coords) - 1):
                u = (round(coords[i][0], 6), round(coords[i][1], 6))
                v = (round(coords[i + 1][0], 6), round(coords[i + 1][1], 6))

                sub_geom = LineString([Point(coords[i]), Point(coords[i + 1])])

                if u not in G:
                    G.add_node(u, pos=u, x=u[0], y=u[1])
                if v not in G:
                    G.add_node(v, pos=v, x=v[0], y=v[1])

                edge_data = {
                    "edge_id": f"walk_{row.get('osm_id', idx)}_{i}",
                    "osm_id": row.get("osm_id"),
                    "name": row.get("name"),
                    "highway": highway_type,
                    "bridge": row.get("bridge"),
                    "geometry": sub_geom,
                    "length_m": avg_seg_length,
                    "hazard_impact": 0.0,
                    "failed": False,
                }
                G.add_edge(u, v, **edge_data)

    return G


def snap_points_to_graph(
    points_gdf: gpd.GeoDataFrame, graph: nx.Graph, max_dist_deg: float = 0.01
) -> Dict[str, Tuple[float, float]]:
    """
    Snap point features (settlements, hospitals) to their nearest network nodes using a KDTree.
    Returns mapping: { osm_id or index: (node_lon, node_lat) }
    """
    snapped = {}
    if points_gdf.empty or len(graph.nodes) == 0:
        return snapped

    nodes = list(graph.nodes)
    node_coords = np.array(nodes)
    tree = cKDTree(node_coords)

    for idx, row in points_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        pt = geom.centroid if geom.geom_type != "Point" else geom
        point_coord = np.array([pt.x, pt.y])
        dist, nearest_idx = tree.query(point_coord)

        if dist <= max_dist_deg:
            target_id = str(row.get("osm_id") or f"pt_{idx}")
            snapped[target_id] = nodes[nearest_idx]

    return snapped