import httpx

BASE = "http://127.0.0.1:8000"

r = httpx.get(f"{BASE}/health")
r.raise_for_status()
print("HEALTH:", r.json())

payload = {
    "aoi": {
        "type": "Polygon",
        "coordinates": [[[85.30,27.68],[85.35,27.68],[85.35,27.72],[85.30,27.72],[85.30,27.68]]]
    },
    "flood_date": "2026-08-26",
    "config": "default",
}
r = httpx.post(f"{BASE}/api/v1/jobs", json=payload)
r.raise_for_status()
print("JOB:", r.json())
print("Smoke test passed.")
