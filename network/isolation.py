from typing import Dict, List, Any, Optional
import networkx as nx
import geopandas as gpd
from shapely.geometry import Point, LineString


def intersect_hazard_with_roads(
    graph: nx.Graph,
    hazard_gdf: gpd.GeoDataFrame,
) -> nx.Graph:
    """
    Identifies edges intersecting the hazard footprint.
    Flags edges as failed and preserves original edge properties.
    """
    G = graph.copy()

    if hazard_gdf.empty or len(G.edges) == 0:
        return G

    if hazard_gdf.crs and hazard_gdf.crs.to_epsg() != 4326:
        hazard_gdf = hazard_gdf.to_crs(epsg=4326)

    hazard_union = hazard_gdf.unary_union

    for u, v, data in G.edges(data=True):
        edge_geom: LineString = data.get("geometry")
        if edge_geom and edge_geom.intersects(hazard_union):
            data["failed"] = True
            data["hazard_impact"] = 1.0
        else:
            data["failed"] = False
            data["hazard_impact"] = 0.0

    return G


def _get_active_subgraph(graph: nx.Graph) -> nx.Graph:
    """Returns a view/subgraph with failed edges excluded for path calculation."""
    active_edges = [(u, v) for u, v, d in graph.edges(data=True) if not d.get("failed", False)]
    return graph.edge_subgraph(active_edges)


def _find_critical_bottleneck_edge(
    baseline_graph: nx.Graph,
    hazard_graph: nx.Graph,
    source_node: tuple,
    target_nodes: set,
) -> Optional[str]:
    """
    Identifies the primary failed edge (bridge or bottleneck road segment)
    along the pre-event shortest path that caused access severance.
    """
    valid_targets = [t for t in target_nodes if t in baseline_graph and nx.has_path(baseline_graph, source_node, t)]
    if not valid_targets:
        return None

    best_path = None
    min_dist = float("inf")
    for t in valid_targets:
        try:
            length = nx.shortest_path_length(baseline_graph, source_node, t, weight="length_m")
            if length < min_dist:
                min_dist = length
                best_path = nx.shortest_path(baseline_graph, source_node, t, weight="length_m")
        except nx.NetworkXNoPath:
            continue

    if not best_path:
        return None

    for i in range(len(best_path) - 1):
        u, v = best_path[i], best_path[i + 1]
        edge_data = hazard_graph.get_edge_data(u, v) or baseline_graph.get_edge_data(u, v) or {}
        if edge_data.get("failed", False):
            name = edge_data.get("name")
            bridge = edge_data.get("bridge")
            highway = edge_data.get("highway", "road segment")
            if bridge and bridge not in ["no", "0"]:
                return f"Severed Bridge ({name or highway})"
            return f"Flooded {name or highway}"

    return "Regional Arterial Inundation"


def compute_settlement_isolation(
    baseline_road_graph: nx.Graph,
    hazard_road_graph: nx.Graph,
    baseline_walk_graph: nx.Graph,
    hazard_walk_graph: nx.Graph,
    settlements_gdf: gpd.GeoDataFrame,
    hospitals_gdf: gpd.GeoDataFrame,
    settlement_road_nodes: Dict[str, tuple],
    settlement_walk_nodes: Dict[str, tuple],
    hospital_road_nodes: Dict[str, tuple],
    hospital_walk_nodes: Dict[str, tuple],
) -> List[Dict[str, Any]]:
    results = []

    # Active operational subgraphs
    active_road_graph = _get_active_subgraph(hazard_road_graph)
    active_walk_graph = _get_active_subgraph(hazard_walk_graph)

    road_safe_targets = set(hospital_road_nodes.values())
    walk_safe_targets = set(hospital_walk_nodes.values())

    for idx, row in settlements_gdf.iterrows():
        osm_id = str(row.get("osm_id") or f"settlement_{idx}")
        s_name = row.get("name") or f"Settlement #{osm_id}"
        place_type = row.get("place", "settlement")

        # 1. Vehicular Road Check
        s_road_node = settlement_road_nodes.get(osm_id)
        baseline_road_conn = False
        post_road_conn = False

        if s_road_node and s_road_node in baseline_road_graph:
            baseline_road_conn = any(
                nx.has_path(baseline_road_graph, s_road_node, t)
                for t in road_safe_targets if t in baseline_road_graph
            )
        if s_road_node and s_road_node in active_road_graph:
            post_road_conn = any(
                nx.has_path(active_road_graph, s_road_node, t)
                for t in road_safe_targets if t in active_road_graph
            )

        road_status = (
            "accessible" if post_road_conn 
            else ("cut_off" if baseline_road_conn else "baseline_disconnected")
        )

        # 2. Foot / Trail Check
        s_walk_node = settlement_walk_nodes.get(osm_id)
        baseline_walk_conn = False
        post_walk_conn = False

        if s_walk_node and s_walk_node in baseline_walk_graph:
            baseline_walk_conn = any(
                nx.has_path(baseline_walk_graph, s_walk_node, t)
                for t in walk_safe_targets if t in baseline_walk_graph
            )
        if s_walk_node and s_walk_node in active_walk_graph:
            post_walk_conn = any(
                nx.has_path(active_walk_graph, s_walk_node, t)
                for t in walk_safe_targets if t in active_walk_graph
            )

        foot_status = (
            "accessible" if post_walk_conn 
            else ("cut_off" if baseline_walk_conn else "baseline_disconnected")
        )

        # 3. Critical-Edge Bottleneck Identification
        critical_cause = None
        if road_status == "cut_off" and s_road_node:
            critical_cause = _find_critical_bottleneck_edge(
                baseline_road_graph, hazard_road_graph, s_road_node, road_safe_targets
            )

        results.append({
            "osm_id": osm_id,
            "id": osm_id,
            "name": s_name,
            "place": place_type,
            "status": road_status,
            "road_status": road_status,
            "foot_status": foot_status,
            "baseline_connected": baseline_road_conn or baseline_walk_conn,
            "pedestrian_only": (road_status == "cut_off" and foot_status == "accessible"),
            "critical_bottleneck": critical_cause or "None identified",
        })

    return results


def format_impact_geojson(
    hazard_graph: nx.Graph,
    settlement_results: List[Dict[str, Any]],
    settlements_gdf: gpd.GeoDataFrame,
) -> Dict[str, Any]:
    """
    Compiles damaged road edges and settlement isolation statuses into
    GeoJSON layers ready for MapLibre rendering.
    """
    road_features = []
    for _, _, d in hazard_graph.edges(data=True):
        if d.get("failed", False) and "geometry" in d:
            road_features.append({
                "type": "Feature",
                "geometry": d["geometry"].__geo_interface__,
                "properties": {
                    "edge_id": d.get("edge_id"),
                    "name": d.get("name"),
                    "highway": d.get("highway"),
                    "bridge": d.get("bridge"),
                    "status": "impassable",
                },
            })

    status_map = {item["osm_id"]: item for item in settlement_results}
    settlement_features = []
    for idx, row in settlements_gdf.iterrows():
        osm_id = str(row.get("osm_id") or f"settlement_{idx}")
        info = status_map.get(osm_id, {})
        if row.geometry:
            settlement_features.append({
                "type": "Feature",
                "geometry": row.geometry.__geo_interface__,
                "properties": {
                    **info,
                    "name": row.get("name") or info.get("name") or "Unnamed Settlement",
                },
            })

    return {
        "damaged_roads": {
            "type": "FeatureCollection",
            "features": road_features,
        },
        "settlements": {
            "type": "FeatureCollection",
            "features": settlement_features,
        },
    }

def simulate_edge_restoration(
    baseline_road_graph: nx.Graph,
    hazard_road_graph: nx.Graph,
    settlement_road_nodes: Dict[str, tuple],
    hospital_road_nodes: Dict[str, tuple],
    currently_isolated_ids: List[str],
    edge_to_restore_id: str,
) -> Dict[str, Any]:
    """
    Simulates restoring a damaged road/bridge edge and calculates
    which previously severed settlements regain access.
    """
    # Clone the post-event graph
    sim_graph = hazard_road_graph.copy()
    restored_found = False

    # Locate the edge by its ID and restore it
    for u, v, data in sim_graph.edges(data=True):
        if str(data.get("edge_id")) == str(edge_to_restore_id):
            data["failed"] = False
            data["hazard_impact"] = 0.0
            restored_found = True
            break

    if not restored_found:
        return {
            "edge_id": edge_to_restore_id,
            "status": "not_found",
            "restored_settlements": [],
            "count_reconnected": 0,
        }

    # Extract active operational edges after simulated repair
    active_edges = [(u, v) for u, v, d in sim_graph.edges(data=True) if not d.get("failed", False)]
    active_graph = sim_graph.edge_subgraph(active_edges)

    road_safe_targets = set(hospital_road_nodes.values())
    reconnected = []

    for s_id in currently_isolated_ids:
        s_node = settlement_road_nodes.get(s_id)
        if s_node and s_node in active_graph:
            if any(nx.has_path(active_graph, s_node, t) for t in road_safe_targets if t in active_graph):
                reconnected.append(s_id)

    return {
        "edge_id": edge_to_restore_id,
        "status": "success",
        "restored_settlements": reconnected,
        "count_reconnected": len(reconnected),
    }