import argparse
import json
import os
import sys
from pathlib import Path
import geopandas as gpd
from shapely.geometry import shape

# Ensure parent directory is in sys.path so internal imports resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from network.ohsome import fetch_all_infrastructure
from network.normalize import (
    normalize_roads,
    normalize_buildings,
    normalize_targets,
)
from network.graph import build_road_graph, snap_points_to_graph
from network.isolation import (
    intersect_hazard_with_roads,
    compute_settlement_isolation,
    format_impact_geojson,
)


def load_aoi_geometry(aoi_path: Path) -> dict:
    if not aoi_path.exists():
        raise FileNotFoundError(f"AOI file not found at: {aoi_path}")
    
    # Use utf-8-sig to automatically strip any Windows PowerShell UTF-8 BOM
    with open(aoi_path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if data.get("type") == "FeatureCollection":
        features = data.get("features", [])
        if not features:
            raise ValueError("FeatureCollection has no features.")
        return features[0]["geometry"]
    elif data.get("type") == "Feature":
        return data["geometry"]
    elif data.get("type") == "Polygon":
        return data
    else:
        raise ValueError(f"Unsupported GeoJSON format: {data.get('type')}")


def main():
    parser = argparse.ArgumentParser(
        description="FloodScope: End-to-end disaster network isolation runner."
    )
    parser.add_argument(
        "--aoi",
        type=str,
        required=True,
        help="Path to GeoJSON file defining the Area of Interest (AOI).",
    )
    parser.add_argument(
        "--date",
        type=str,
        required=True,
        help="Flood reference date in YYYY-MM-DD format (e.g. 2026-08-26).",
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="baseline",
        choices=["baseline", "ml", "full"],
        help="Execution mode (baseline, ml, full).",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/runs",
        help="Directory to save output layers and metrics.",
    )

    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=======================================================")
    print(f" FloodScope Pipeline Execution")
    print(f" AOI:    {args.aoi}")
    print(f" Date:   {args.date}")
    print(f" Mode:   {args.mode}")
    print(f" Output: {out_dir}")
    print(f"=======================================================\n")

    # 1. Load AOI Geometry
    print("[1/5] Loading AOI boundary...")
    aoi_geom = load_aoi_geometry(Path(args.aoi))

    # 2. Fetch Historical OSM Data (using snapshot constraint)
    print("[2/5] Fetching pre-event infrastructure via ohsome...")
    raw_infra = fetch_all_infrastructure(aoi_geom)

    roads_gdf = normalize_roads(raw_infra.get("roads", gpd.GeoDataFrame()))
    buildings_gdf = normalize_buildings(raw_infra.get("buildings", gpd.GeoDataFrame()))
    settlements_gdf = normalize_targets(raw_infra.get("settlements", gpd.GeoDataFrame()))
    hospitals_gdf = normalize_targets(raw_infra.get("hospitals", gpd.GeoDataFrame()))

    print(f"      - Roads normalized:       {len(roads_gdf)} segments")
    print(f"      - Buildings normalized:   {len(buildings_gdf)} footprints")
    print(f"      - Settlements identified: {len(settlements_gdf)} locations")
    print(f"      - Hospitals / Targets:    {len(hospitals_gdf)} facilities")

    # 3. Ingest Hazard Extent (Anvi's export or baseline fallback)
    print("[3/5] Resolving flood hazard layer...")
    hazard_file = out_dir / "latest_flood.geojson"
    if hazard_file.exists():
        print(f"      -> Found satellite flood mask: {hazard_file}")
        hazard_gdf = gpd.read_file(hazard_file)
    else:
        print("      -> Generating baseline fallback hazard polygon (center envelope)...")
        poly = shape(aoi_geom)
        centroid = poly.centroid
        delta = 0.01
        hazard_poly = {
            "type": "Polygon",
            "coordinates": [[
                [centroid.x - delta, centroid.y - delta],
                [centroid.x + delta, centroid.y - delta],
                [centroid.x + delta, centroid.y + delta],
                [centroid.x - delta, centroid.y + delta],
                [centroid.x - delta, centroid.y - delta],
            ]],
        }
        hazard_gdf = gpd.GeoDataFrame(
            [{"geometry": shape(hazard_poly), "hazard": 1}],
            crs="EPSG:4326",
        )

    # 4. Graph Construction and Reachability Analysis
    print("[4/5] Building topological graph and computing network reachability...")
    baseline_graph = build_road_graph(roads_gdf)
    hazard_graph = intersect_hazard_with_roads(baseline_graph, hazard_gdf)

    settlement_nodes = snap_points_to_graph(settlements_gdf, baseline_graph)
    target_nodes = snap_points_to_graph(hospitals_gdf, baseline_graph)

    settlement_results = compute_settlement_isolation(
        baseline_graph=baseline_graph,
        hazard_graph=hazard_graph,
        settlements_gdf=settlements_gdf,
        targets_gdf=hospitals_gdf,
        settlement_nodes=settlement_nodes,
        target_nodes=target_nodes,
    )

    impact_geojson = format_impact_geojson(hazard_graph, settlement_results, settlements_gdf)

    # 5. Output Results and Summary
    print("[5/5] Serializing outputs and metrics...")
    cut_off_count = sum(1 for s in settlement_results if s["status"] == "cut_off")
    damaged_roads_count = len(impact_geojson["damaged_roads"]["features"])

    summary = {
        "aoi": args.aoi,
        "flood_date": args.date,
        "mode": args.mode,
        "osm_snapshot": "2026-07-27T00:00:00Z",
        "total_settlements": len(settlements_gdf),
        "cut_off_settlements": cut_off_count,
        "damaged_road_segments": damaged_roads_count,
        "total_buildings": len(buildings_gdf),
    }

    # Save summary and geojson layers
    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with open(out_dir / "damaged_roads.geojson", "w", encoding="utf-8") as f:
        json.dump(impact_geojson["damaged_roads"], f)

    with open(out_dir / "settlement_impacts.geojson", "w", encoding="utf-8") as f:
        json.dump(impact_geojson["settlements"], f)

    print("\n-------------------------------------------------------")
    print(" Execution Completed Successfully!")
    print(f" - Isolated Settlements:    {cut_off_count} / {len(settlements_gdf)}")
    print(f" - Damaged Road Segments:   {damaged_roads_count}")
    print(f" - Building Footprints:     {len(buildings_gdf)}")
    print(f" Summary written to: {out_dir / 'summary.json'}")
    print("-------------------------------------------------------\n")


if __name__ == "__main__":
    main()