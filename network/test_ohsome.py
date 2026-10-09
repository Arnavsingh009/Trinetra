from network.ohsome import fetch_osm_snapshot


# Small test AOI.
# Coordinates are longitude, latitude.
AOI = {
    "type": "Polygon",
    "coordinates": [
        [
            [85.28, 27.68],
            [85.32, 27.68],
            [85.32, 27.72],
            [85.28, 27.72],
            [85.28, 27.68],
        ]
    ],
}


def main():
    data = fetch_osm_snapshot(
        aoi_geometry=AOI,
        snapshot_date="latest",
        osm_filter="highway=* and geometry:line",
    )

    features = data.get("features", [])

    print("ohsome request successful")
    print(f"Road features returned: {len(features)}")

    if features:
        print("\nFirst feature:")
        print(features[0])


if __name__ == "__main__":
    main()