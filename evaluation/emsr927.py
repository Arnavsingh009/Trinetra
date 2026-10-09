import os
import json
import rasterio
from rasterio.features import rasterize
import geopandas as gpd
import numpy as np
from typing import Dict, Any
from evaluation.metrics import compute_hazard_metrics, create_disagreement_map

def evaluate_against_emsr927(
    predicted_raster_path: str,
    emsr_vector_path: str,
    observable_raster_path: str = None,
    output_dir: str = "data/runs/evaluation"
) -> Dict[str, Any]:
    """
    Fulfills check-only evaluation against EMSR927.
    Loads frozen prediction, reprojects/rasterizes EMSR927, and computes metrics.
    """
    os.makedirs(output_dir, exist_ok=True)

    with rasterio.open(predicted_raster_path) as src:
        pred_meta = src.meta.copy()
        pred_data = src.read(1)
        transform = src.transform
        crs = src.crs
        shape = src.shape

    # Binarize prediction (1: flood/debris, 0: unaffected)
    pred_binary = (pred_data > 0) & (pred_data != 255)

    # Load observable mask if available
    observable_binary = None
    if observable_raster_path and os.path.exists(observable_raster_path):
        with rasterio.open(observable_raster_path) as obs_src:
            observable_binary = obs_src.read(1) == 1
    else:
        # Infer observable pixels if nodata (255) exists in prediction
        observable_binary = pred_data != 255

    # Load EMSR927 reference vectors and reproject to match prediction CRS
    ems_gdf = gpd.read_file(emsr_vector_path)
    if ems_gdf.crs != crs:
        ems_gdf = ems_gdf.to_crs(crs)

    # Rasterize EMS hazard shapes onto the exact grid
    shapes = [(geom, 1) for geom in ems_gdf.geometry if geom is not None and not geom.is_empty]
    if shapes:
        ems_binary = rasterize(
            shapes=shapes,
            out_shape=shape,
            transform=transform,
            fill=0,
            dtype=np.uint8
        )
    else:
        ems_binary = np.zeros(shape, dtype=np.uint8)

    # Compute quantitative scores
    metrics = compute_hazard_metrics(pred_binary, ems_binary, observable_binary)

    # Generate disagreement map
    disagreement = create_disagreement_map(pred_binary, ems_binary, observable_binary)

    disagreement_meta = pred_meta.copy()
    disagreement_meta.update({"dtype": "uint8", "count": 1, "nodata": 255})
    
    disagreement_path = os.path.join(output_dir, "emsr927_disagreement.tif")
    with rasterio.open(disagreement_path, "w", **disagreement_meta) as dst:
        dst.write(disagreement, 1)

    result_summary = {
        "metrics": metrics,
        "disagreement_raster": disagreement_path,
        "citation": "European Union, Copernicus Emergency Management Service data (EMSR927)",
        "disagreement_categories": {
            0: "Agreement Non-Flood",
            1: "Agreement Flood",
            2: "FloodScope Only",
            3: "EMSR927 Only",
            255: "Unobservable (Radar Shadow / Layover)"
        },
        "defense_note": (
            "Differences cannot automatically be interpreted as errors in either product "
            "because acquisition time, sensors, and mapping methodology differ."
        )
    }

    # Save summary JSON
    summary_path = os.path.join(output_dir, "emsr927_metrics.json")
    with open(summary_path, "w") as f:
        json.dump(result_summary, f, indent=2)

    return result_summary