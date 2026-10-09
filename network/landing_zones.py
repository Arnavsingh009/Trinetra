from typing import Dict, Any
import geopandas as gpd
from shapely.geometry import Point
from scipy.spatial import cKDTree


def extract_viable_landing_zones(
    buildings_gdf: gpd.GeoDataFrame,
    hazard_gdf: gpd.GeoDataFrame,
) -> gpd.GeoDataFrame:
    """
    Identifies dry, unflooded open grounds or flat public facilities
    suitable for helicopter landing or UAV supply drops.
    """
    if buildings_gdf.empty:
        return gpd.GeoDataFrame(columns=["name", "type", "geometry"], crs="EPSG:4326")

    hazard_union = hazard_gdf.unary_union if not hazard_gdf.empty else None

    # Legitimate open-space tags suitable for landing operations
    valid_lz_types = {
        "pitch", "stadium", "sports_centre", "school", "hospital",
        "helipad", "aerodrome", "grass", "recreation_ground"
    }

    viable_records = []
    for idx, row in buildings_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        # Submerged exclusion
        if hazard_union and geom.intersects(hazard_union):
            continue

        amenity = str(row.get("amenity", "")).lower()
        leisure = str(row.get("leisure", "")).lower()
        aeroway = str(row.get("aeroway", "")).lower()
        landuse = str(row.get("landuse", "")).lower()

        matched_type = None
        for tag in [amenity, leisure, aeroway, landuse]:
            if tag in valid_lz_types:
                matched_type = tag
                break

        # Only retain identified open/public infrastructure
        if not matched_type:
            continue

        center = geom.centroid if geom.geom_type != "Point" else geom
        viable_records.append({
            "lz_id": f"lz_{row.get('osm_id', idx)}",
            "name": row.get("name") or f"Designated LZ ({matched_type.capitalize()})",
            "type": matched_type,
            "geometry": center,
        })

    # Fallback: if no dedicated facilities were tagged, take up to 8 largest unflooded footprints
    if not viable_records:
        unflooded_candidates = [
            row for _, row in buildings_gdf.iterrows()
            if row.geometry and not row.geometry.is_empty and not (hazard_union and row.geometry.intersects(hazard_union))
        ]
        
        # Sort by footprint area if polygons exist
        unflooded_candidates.sort(
            key=lambda r: r.geometry.area if hasattr(r.geometry, "area") else 0,
            reverse=True,
        )

        for idx, row in enumerate(unflooded_candidates[:8]):
            center = row.geometry.centroid if row.geometry.geom_type != "Point" else row.geometry
            viable_records.append({
                "lz_id": f"lz_open_{idx}",
                "name": row.get("name") or f"Open Clear Ground #{idx + 1}",
                "type": "open_ground",
                "geometry": center,
            })

    if not viable_records:
        return gpd.GeoDataFrame(columns=["name", "type", "geometry"], crs="EPSG:4326")

    return gpd.GeoDataFrame(viable_records, crs="EPSG:4326")


def match_settlements_to_landing_zones(
    settlements_gdf: gpd.GeoDataFrame,
    landing_zones_gdf: gpd.GeoDataFrame,
) -> Dict[str, Dict[str, Any]]:
    """
    Finds the nearest dry landing zone and straight-line distance (in km)
    for every settlement.
    """
    if settlements_gdf.empty or landing_zones_gdf.empty:
        return {}

    lz_points = [[geom.x, geom.y] for geom in landing_zones_gdf.geometry]
    tree = cKDTree(lz_points)

    matched = {}
    for idx, row in settlements_gdf.iterrows():
        s_id = str(row.get("osm_id") or f"settlement_{idx}")
        pt = row.geometry.centroid if row.geometry.geom_type != "Point" else row.geometry

        dist_deg, nearest_idx = tree.query([pt.x, pt.y])
        dist_km = round(dist_deg * 111.0, 2)  # ~111 km per degree latitude
        target_lz = landing_zones_gdf.iloc[nearest_idx]

        matched[s_id] = {
            "nearest_lz_name": target_lz["name"],
            "distance_km": dist_km,
            "lz_type": target_lz["type"],
            "lz_coords": [target_lz.geometry.x, target_lz.geometry.y],
        }

    return matched