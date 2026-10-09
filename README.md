# FloodScope

Track B — Mapping Flood Damage from Space.

## Today's Oct 7 foundation
- FastAPI backend
- Pydantic API contracts
- React + TypeScript + MapLibre frontend
- AOI drawing + flood date
- Analyze job creation
- Historical OSM/ohsome adapter
- OSM normalization
- Dummy hazard GeoJSON overlay

## Run backend
```bash
cd kamand-flood
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --reload
```

## Run frontend
```bash
cd web
npm install
npm run dev
```

Backend: http://127.0.0.1:8000
Swagger: http://127.0.0.1:8000/docs

## Important
The flood layer in this Oct 7 foundation is a DUMMY layer only. It is not a flood prediction.
