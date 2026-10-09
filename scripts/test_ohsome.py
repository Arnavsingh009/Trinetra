from network.ohsome import fetch_osm_snapshot
from network.normalize import normalize_roads


AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [85.25, 27.95],
            [85.35, 27.95],
            [85.35, 28.05],
            [85.25, 28.05],
            [85.25, 27.95],
        ]
    ],
}


def main():

    print()
    print("========================================")
    print("       OSM NORMALIZATION TEST")
    print("========================================")

    # ---------------------------------------
    # 1. Fetch historical OSM roads
    # ---------------------------------------

    print("Fetching OSM snapshot...")
    print("Date: 2026-08-26")
    print()

    roads_raw = fetch_osm_snapshot(
        aoi_geometry=AOI,
        snapshot_date="2026-08-26",
        osm_filter="highway=* and geometry:line",
    )

    print("Raw features:", len(roads_raw))

    # ---------------------------------------
    # 2. Normalize roads
    # ---------------------------------------

    roads = normalize_roads(roads_raw)

    print("Normalized roads:", len(roads))
    print()

    # ---------------------------------------
    # 3. Display information
    # ---------------------------------------

    print("Columns:")
    print(roads.columns.tolist())

    print()
    print("Geometry types:")
    print(roads.geometry.geom_type.value_counts())

    print()
    print("First 5 roads:")
    print(roads.head())

    print()
    print("========================================")
    print("       NORMALIZATION SUCCESS")
    print("========================================")


if __name__ == "__main__":
    main()