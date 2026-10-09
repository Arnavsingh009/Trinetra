import argparse
import json
from evaluation.emsr927 import evaluate_against_emsr927
from evaluation.metrics import compute_hazard_metrics, create_disagreement_map

def main():
    parser = argparse.ArgumentParser(description="EMSR927 Hazard Layer Verification")
    parser.add_argument("--pred", required=True, help="Path to frozen predicted hazard raster (.tif)")
    parser.add_argument("--emsr", required=True, help="Path to EMSR927 vector file (.geojson or .shp)")
    parser.add_argument("--obs", default=None, help="Optional observable mask raster (.tif)")
    parser.add_argument("--out", default="data/runs/evaluation", help="Output directory")

    args = parser.parse_args()

    print("=================================================================")
    print("RUNNING HAZARD LAYER EVALUATION AGAINST EMSR927 (CHECK-ONLY)")
    print("=================================================================")

    results = evaluate_against_emsr927(
        predicted_raster_path=args.pred,
        emsr_vector_path=args.emsr,
        observable_raster_path=args.obs,
        output_dir=args.out
    )

    print("\n--- Quantitative Verification Results ---")
    for k, v in results["metrics"].items():
        print(f"  {k:25s}: {v}")

    print(f"\nDisagreement Map saved to: {results['disagreement_raster']}")
    print(f"Metrics JSON saved to   : {args.out}/emsr927_metrics.json")
    print("\nDefensible Q&A Statement:")
    print(f'"{results["defense_note"]}"')
    print("=================================================================")

if __name__ == "__main__":
    main()