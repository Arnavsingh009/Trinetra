from typing import Dict, List, Any
import random
import networkx as nx
import geopandas as gpd


def assign_edge_failure_probabilities(
    graph: nx.Graph,
    hazard_gdf: gpd.GeoDataFrame,
    default_hazard_prob: float = 0.85,
) -> nx.Graph:
    """
    Assigns a continuous failure probability [0.0, 1.0] to each road edge.
    Edges intersecting the hazard footprint receive failure probability.
    """
    G = graph.copy()
    if hazard_gdf.empty or len(G.edges) == 0:
        for _, _, data in G.edges(data=True):
            data["p_fail"] = 0.0
        return G

    hazard_union = hazard_gdf.unary_union

    for _, _, data in G.edges(data=True):
        geom = data.get("geometry")
        if geom and geom.intersects(hazard_union):
            bridge = data.get("bridge")
            data["p_fail"] = 0.95 if bridge and bridge not in ["no", "0"] else default_hazard_prob
        else:
            data["p_fail"] = 0.0

    return G


def run_monte_carlo_simulation(
    prob_graph: nx.Graph,
    settlement_nodes: Dict[str, tuple],
    target_nodes: Dict[str, tuple],
    runs: int = 250,
) -> Dict[str, float]:
    """
    Performs an N-run Monte Carlo simulation to calculate settlement cutoff probabilities.
    Returns: { osm_id: cutoff_probability (between 0.0 and 1.0) }
    """
    valid_targets = set(target_nodes.values())
    if not valid_targets or len(prob_graph.nodes) == 0:
        return {s_id: 0.0 for s_id in settlement_nodes}

    cutoff_counts = {s_id: 0 for s_id in settlement_nodes}
    edges = list(prob_graph.edges(data=True))

    for _ in range(runs):
        surviving_edges = [
            (u, v) for u, v, data in edges
            if random.random() >= data.get("p_fail", 0.0)
        ]

        sample_graph = prob_graph.edge_subgraph(surviving_edges)

        for s_id, s_node in settlement_nodes.items():
            if s_node not in sample_graph:
                cutoff_counts[s_id] += 1
                continue

            reachable = any(
                nx.has_path(sample_graph, s_node, t)
                for t in valid_targets if t in sample_graph
            )
            if not reachable:
                cutoff_counts[s_id] += 1

    return {s_id: round(count / runs, 3) for s_id, count in cutoff_counts.items()}