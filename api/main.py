import asyncio
import io
import json
import zipfile
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response

from api.schemas import AnalyzeRequest, JobState, RestoreEdgeRequest
from network.isolation import simulate_edge_restoration
from api.schemas import AnalyzeRequest, JobState
from api.jobs import create_job, get_job, run_job
from reports.generator import generate_situation_report

app = FastAPI(title="FloodScope API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "floodscope-api"}


@app.post("/api/v1/jobs")
async def start_job(payload: AnalyzeRequest):
    job = create_job(
        flood_date=payload.flood_date,
        aoi=payload.aoi.model_dump(),
        config=payload.config,
    )
    asyncio.create_task(run_job(job["id"]))
    return job


@app.get("/api/v1/jobs/{job_id}")
def read_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/api/v1/jobs/{job_id}/summary")
def get_job_summary(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"summary": job.get("summary", {})}


@app.get("/api/v1/jobs/{job_id}/layers")
def get_job_layers(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.get("layers", {})


@app.get("/api/v1/jobs/{job_id}/provenance")
def get_job_provenance(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "osm_snapshot": "2026-07-27T00:00:00Z",
        "data_source": "ohsome v2 API",
        "cache_hit": job.get("cache_hit", False),
        "note": "Deterministic network topology pipeline",
    }


@app.get("/api/v1/jobs/{job_id}/export")
def export_job_bundle(job_id: str):
    """Packages all analysis outputs into a single downloadable .zip archive."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("state") != JobState.COMPLETE:
        raise HTTPException(status_code=400, detail="Job is not completed yet")

    layers = job.get("layers", {})
    summary = job.get("summary", {})

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("summary.json", json.dumps(summary, indent=2))
        
        for layer_name in ["flood_extent", "damaged_roads", "settlements", "unobservable"]:
            layer_data = layers.get(layer_name)
            if layer_data:
                zip_file.writestr(f"{layer_name}.geojson", json.dumps(layer_data, indent=2))

        sitrep_path = Path("data/runs/SITREP.md")
        if sitrep_path.exists():
            zip_file.write(sitrep_path, arcname="SITREP.md")

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=floodscope_export_{job_id}.zip"
        },
    )


@app.get("/api/v1/jobs/{job_id}/report", response_class=HTMLResponse)
def get_job_report(job_id: str, lang: str = "en"):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("state") != JobState.COMPLETE:
        raise HTTPException(status_code=400, detail="Job is not completed yet")

    runs_dir = Path("data/runs")
    sitrep_path = runs_dir / f"SITREP_{lang}.md"

    summary_data = job.get("summary", {})
    layers = job.get("layers", {})
    settlements_geojson = layers.get("settlements", {})
    features = [feat.get("properties", {}) for feat in settlements_geojson.get("features", [])]

    markdown_text = generate_situation_report(summary_data, features, sitrep_path, lang=lang)

    html_content = f"""
    <!DOCTYPE html>
    <html lang="{lang}">
    <head>
      <meta charset="utf-8"/>
      <title>FloodScope Situation Report - {job_id}</title>
      <meta name="viewport" content="width=device-width, initial-scale=1"/>
      <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
      <style>
        body {{
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          background: #0f172a;
          color: #e2e8f0;
          margin: 0;
          padding: 30px 15px;
          display: flex;
          justify-content: center;
        }}
        .container {{
          max-width: 900px;
          width: 100%;
          background: #1e293b;
          padding: 32px;
          border-radius: 12px;
          border: 1px solid #334155;
          line-height: 1.5;
        }}
        .top-bar {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 20px;
          border-bottom: 1px solid #334155;
          padding-bottom: 12px;
        }}
        .lang-switch a {{
          color: #38bdf8;
          text-decoration: none;
          margin-right: 12px;
          font-weight: 600;
          font-size: 14px;
        }}
        .lang-switch a.active {{
          color: #fff;
          border-bottom: 2px solid #38bdf8;
        }}
        h1 {{ color: #38bdf8; font-size: 24px; margin-top: 0; }}
        h2 {{ color: #94a3b8; font-size: 18px; margin-top: 24px; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin: 16px 0;
          font-size: 12px;
        }}
        th, td {{
          padding: 8px 10px;
          text-align: left;
          border-bottom: 1px solid #334155;
        }}
        th {{ background: #0f172a; color: #38bdf8; }}
        tr:hover {{ background: rgba(56, 189, 248, 0.05); }}
        .btn-print {{
          background: #0284c7;
          color: #fff;
          border: none;
          padding: 6px 14px;
          border-radius: 6px;
          cursor: pointer;
          font-weight: 600;
          font-size: 13px;
        }}

        /* One-page export print media styles[cite: 3] */
        @media print {{
          body {{
            background: #ffffff !important;
            color: #000000 !important;
            padding: 0 !important;
          }}
          .container {{
            max-width: 100% !important;
            border: none !important;
            box-shadow: none !important;
            padding: 0 !important;
            background: #ffffff !important;
          }}
          .top-bar {{ display: none !important; }}
          h1 {{ color: #000 !important; font-size: 18px !important; margin-bottom: 6px !important; }}
          h2 {{ color: #333 !important; font-size: 14px !important; margin-top: 14px !important; }}
          p, ul, li {{ font-size: 10px !important; line-height: 1.3 !important; margin: 3px 0 !important; }}
          table {{ font-size: 9px !important; margin: 8px 0 !important; }}
          th {{ background: #e2e8f0 !important; color: #000 !important; padding: 4px 6px !important; }}
          td {{ padding: 4px 6px !important; color: #000 !important; border-bottom: 1px solid #cbd5e1 !important; }}
          hr {{ display: none !important; }}
          @page {{
            size: A4 portrait;
            margin: 10mm;
          }}
        }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="top-bar">
          <div class="lang-switch">
            <a href="?lang=en" class="{ 'active' if lang == 'en' else '' }">English</a>
            <a href="?lang=ne" class="{ 'active' if lang == 'ne' else '' }">नेपाली (Nepali)</a>
          </div>
          <button class="btn-print" onclick="window.print()">Print / PDF (One-Page)</button>
        </div>
        <div id="content"></div>
      </div>
      <script>
        const md = {json.dumps(markdown_text)};
        document.getElementById('content').innerHTML = marked.parse(md);
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.post("/api/v1/jobs/{job_id}/simulate-restoration")
def simulate_restoration(job_id: str, payload: RestoreEdgeRequest):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.get("state") != JobState.COMPLETE:
        raise HTTPException(status_code=400, detail="Job analysis is not complete yet")

    layers = job.get("layers", {})
    settlements = layers.get("settlements", {}).get("features", [])
    
    # Find IDs of currently cut-off settlements
    currently_isolated = [
        str(feat.get("properties", {}).get("osm_id") or feat.get("properties", {}).get("id"))
        for feat in settlements
        if feat.get("properties", {}).get("road_status") == "cut_off"
        or feat.get("properties", {}).get("status") == "cut_off"
    ]

    # Pull cached graph and node maps stored during job execution
    baseline_road_graph = job.get("baseline_road_graph")
    hazard_road_graph = job.get("hazard_road_graph")
    settlement_road_nodes = job.get("settlement_road_nodes", {})
    hospital_road_nodes = job.get("hospital_road_nodes", {})

    if not baseline_road_graph or not hazard_road_graph:
        raise HTTPException(status_code=500, detail="Graph topology states not stored on job instance")

    result = simulate_edge_restoration(
        baseline_road_graph=baseline_road_graph,
        hazard_road_graph=hazard_road_graph,
        settlement_road_nodes=settlement_road_nodes,
        hospital_road_nodes=hospital_road_nodes,
        currently_isolated_ids=currently_isolated,
        edge_to_restore_id=payload.edge_id,
    )

    return result