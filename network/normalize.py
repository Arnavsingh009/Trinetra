import pandas as pd
import geopandas as gpd
from shapely.geometry import Point


def _get_geometry_column(gdf: gpd.GeoDataFrame) -> str | None:
    """Safely identify the geometry column name."""
    if isinstance(gdf, gpd.GeoDataFrame) and hasattr(gdf, "geometry"):
        try:
            return gdf.geometry.name
        except AttributeError:
            pass
    if "geometry" in gdf.columns:
        return "geometry"
    return None


def _build_empty_gdf(target_columns: list[str]) -> gpd.GeoDataFrame:
    """Safely build an empty GeoDataFrame guaranteed to have an active geometry column."""
    df = pd.DataFrame({col: [] for col in target_columns})
    df["geometry"] = gpd.GeoSeries([], dtype="geometry")
    return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")


def _standardize_gdf(
    gdf: gpd.GeoDataFrame, allowed_geom_types: list[str], target_columns: list[str]
) -> gpd.GeoDataFrame:
    """Safely sanitize GeoDataFrame geometries and columns."""
    if gdf is None or len(gdf) == 0:
        return _build_empty_gdf(target_columns)

    geom_col = _get_geometry_column(gdf)
    if not geom_col or geom_col not in gdf.columns:
        return _build_empty_gdf(target_columns)

    res = gdf.copy()
    if geom_col != "geometry":
        res = res.rename(columns={geom_col: "geometry"})

    for col in target_columns:
        if col not in res.columns:
            res[col] = None

    # Keep target columns and valid geometries
    res = res[target_columns + ["geometry"]].dropna(subset=["geometry"])
    res = res[
        res["geometry"].apply(
            lambda g: hasattr(g, "geom_type") and g.geom_type in allowed_geom_types and not g.is_empty
        )
    ]

    if len(res) == 0:
        return _build_empty_gdf(target_columns)

    res["osm_id"] = [
        str(val) if val is not None and str(val).strip() != "" else f"feat_{i}"
        for i, val in enumerate(res["osm_id"])
    ]

    pure_df = pd.DataFrame(res.drop(columns=["geometry"]))
    geo_series = gpd.GeoSeries(res["geometry"], crs=gdf.crs if gdf.crs else "EPSG:4326")
    
    final_gdf = gpd.GeoDataFrame(pure_df, geometry=geo_series)
    if final_gdf.crs and final_gdf.crs.to_epsg() != 4326:
        final_gdf = final_gdf.to_crs("EPSG:4326")

    return final_gdf.reset_index(drop=True)


def normalize_roads(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Normalize line networks (roads, paths, and bridges)."""
    target_cols = ["osm_id", "highway", "name", "bridge", "foot"]
    return _standardize_gdf(
        gdf, ["LineString", "MultiLineString"], target_cols
    )


def normalize_buildings(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Normalize building footprints and public open grounds."""
    target_cols = [
        "osm_id", "building", "name",
        "amenity", "leisure", "aeroway", "landuse"
    ]
    return _standardize_gdf(
        gdf, ["Polygon", "MultiPolygon", "Point"], target_cols
    )


def normalize_targets(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Normalize settlements and critical destinations into Point geometries."""
    target_cols = ["osm_id", "name", "place", "amenity"]
    if gdf is None or len(gdf) == 0:
        return _build_empty_gdf(target_cols)

    geom_col = _get_geometry_column(gdf)
    if not geom_col or geom_col not in gdf.columns:
        return _build_empty_gdf(target_cols)

    norm = gdf.copy()
    if geom_col != "geometry":
        norm = norm.rename(columns={geom_col: "geometry"})

    for col in target_cols:
        if col not in norm.columns:
            norm[col] = None

    norm = norm[target_cols + ["geometry"]].dropna(subset=["geometry"])
    if len(norm) == 0:
        return _build_empty_gdf(target_cols)

    # Convert polygons or lines to centroid Points
    norm["geometry"] = norm["geometry"].apply(
        lambda g: g.centroid if hasattr(g, "geom_type") and g.geom_type != "Point" else g
    )
    norm = norm[
        norm["geometry"].apply(
            lambda g: hasattr(g, "geom_type") and g.geom_type == "Point" and not g.is_empty
        )
    ]

    if len(norm) == 0:
        return _build_empty_gdf(target_cols)

    norm["osm_id"] = [
        str(val) if val is not None and str(val).strip() != "" else f"target_{i}"
        for i, val in enumerate(norm["osm_id"])
    ]

    pure_df = pd.DataFrame(norm.drop(columns=["geometry"]))
    geo_series = gpd.GeoSeries(norm["geometry"], crs=gdf.crs if gdf.crs else "EPSG:4326")

    final_gdf = gpd.GeoDataFrame(pure_df, geometry=geo_series)
    if final_gdf.crs and final_gdf.crs.to_epsg() != 4326:
        final_gdf = final_gdf.to_crs("EPSG:4326")

    return final_gdf.reset_index(drop=True)