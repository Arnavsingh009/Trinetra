import numpy as np
from typing import Dict, Any

def compute_hazard_metrics(
    pred_mask: np.ndarray,
    ref_mask: np.ndarray,
    observable_mask: np.ndarray = None
) -> Dict[str, float]:
    """
    Computes standard segmentation metrics.
    Ensures unobservable pixels are excluded from scoring so they aren't labeled dry.
    
    Inputs:
      pred_mask: binary array (1 = flood/hazard, 0 = unaffected)
      ref_mask: binary array (1 = EMS hazard, 0 = non-hazard)
      observable_mask: binary array (1 = observable, 0 = radar shadow/unobservable)
    """
    pred = pred_mask.astype(bool)
    ref = ref_mask.astype(bool)

    if observable_mask is not None:
        valid = observable_mask.astype(bool)
        pred = pred & valid
        ref = ref & valid

    tp = np.logical_and(pred, ref).sum()
    fp = np.logical_and(pred, np.logical_not(ref)).sum()
    fn = np.logical_and(np.logical_not(pred), ref).sum()
    tn = np.logical_and(np.logical_not(pred), np.logical_not(ref)).sum()

    intersection = tp
    union = tp + fp + fn

    iou = float(intersection / union) if union > 0 else 0.0
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = float(2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    return {
        "true_positive_pixels": int(tp),
        "false_positive_pixels": int(fp),
        "false_negative_pixels": int(fn),
        "true_negative_pixels": int(tn),
        "iou": round(iou, 4),
        "f1": round(f1, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
    }

def create_disagreement_map(
    pred_mask: np.ndarray,
    ref_mask: np.ndarray,
    observable_mask: np.ndarray = None
) -> np.ndarray:
    """
    Generates a 4-class evaluation raster:
      0: Agreement (Non-Flood)
      1: Agreement (Flood)
      2: System Only (Potential FP / Different sensor/time)
      3: EMSR927 Only (Potential FN / Missed or debris)
      255: Unobservable / Masked
    """
    out = np.zeros(pred_mask.shape, dtype=np.uint8)
    
    pred = pred_mask.astype(bool)
    ref = ref_mask.astype(bool)

    out[~pred & ~ref] = 0
    out[pred & ref] = 1
    out[pred & ~ref] = 2
    out[~pred & ref] = 3

    if observable_mask is not None:
        out[observable_mask == 0] = 255

    return out