import { useEffect, useRef, useState, useCallback } from "react";
import maplibregl, { GeoJSONSource, Popup } from "maplibre-gl";
import MapboxDraw from "@mapbox/mapbox-gl-draw";

import "@mapbox/mapbox-gl-draw/dist/mapbox-gl-draw.css";

const API = "http://127.0.0.1:8000";

type AOI = {
  type: "Polygon";
  coordinates: number[][][];
};

type Job = {
  id?: string;
  job_id?: string;
  state: string;
  flood_date: string;
  message: string;
};

type SummaryData = {
  total_settlements?: number;
  settlements_cut_off?: number;
  damaged_road_segments?: number;
  total_buildings?: number;
  hospitals_monitored?: number;
  foot_cut_off?: number;
  pedestrian_accessible_only?: number;
  viable_landing_zones?: number;
  s2_optical_available?: boolean;
  s2_optical_date?: string;
  s2_cloud_cover?: string;
};

type ProvenanceData = {
  osm_snapshot?: string;
  cache_hit?: boolean;
  note?: string;
};

export default function App() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const drawRef = useRef<MapboxDraw | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const popupRef = useRef<Popup | null>(null);

  const [date, setDate] = useState("2026-08-26");
  const [aoi, setAoi] = useState<AOI | null>(null);
  const [status, setStatus] = useState("READY");
  const [message, setMessage] = useState("Draw an analysis area on the map.");
  const [jobId, setJobId] = useState<string | null>(null);

  // Summary & Provenance state
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [provenance, setProvenance] = useState<ProvenanceData | null>(null);

  // Layer Visibility States
  const [hazardVisible, setHazardVisible] = useState(true);
  const [roadsVisible, setRoadsVisible] = useState(true);
  const [settlementsVisible, setSettlementsVisible] = useState(true);
  const [unobservableVisible, setUnobservableVisible] = useState(true);
  const [hasResults, setHasResults] = useState(false);

  // Keep a ref to jobId so map click listeners always have the latest value
  const jobIdRef = useRef<string | null>(null);
  useEffect(() => {
    jobIdRef.current = jobId;
  }, [jobId]);

  // ---------------------------------------------------------
  // INITIALIZE MAP
  // ---------------------------------------------------------
  useEffect(() => {
    if (!mapContainer.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
          },
        },
        layers: [
          {
            id: "osm",
            type: "raster",
            source: "osm",
          },
        ],
      },
      center: [85.325, 27.7],
      zoom: 12,
    });

    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), "top-right");

    const draw = new MapboxDraw({
      displayControlsDefault: false,
      controls: {
        polygon: false,
        trash: false,
      },
      defaultMode: "simple_select",
    });

    drawRef.current = draw;
    map.addControl(draw as unknown as maplibregl.IControl, "top-left");

    map.on("draw.create", (event: { features?: any[] }) => {
      const feature = event.features?.[0];
      if (!feature || feature.geometry.type !== "Polygon") {
        setStatus("ERROR");
        setMessage("Please draw a valid closed polygon.");
        return;
      }

      setAoi({
        type: "Polygon",
        coordinates: feature.geometry.coordinates,
      });

      setTimeout(() => {
        try {
          draw.changeMode("simple_select", { featureIds: [] });
        } catch {
          // Fallback if mode switch fails
        }
      }, 50);

      setStatus("AOI READY");
      setMessage("AOI captured successfully. You can now run the analysis.");
    });

    map.on("draw.update", (event: { features?: any[] }) => {
      const feature = event.features?.[0];
      if (!feature || feature.geometry.type !== "Polygon") return;

      setAoi({
        type: "Polygon",
        coordinates: feature.geometry.coordinates,
      });
      setStatus("AOI UPDATED");
      setMessage("Analysis area updated.");
    });

    map.on("draw.delete", () => {
      setAoi(null);
      setStatus("READY");
      setMessage("Draw an analysis area on the map.");
    });

    // Settlement click interaction
    map.on("click", "settlements-layer", (e) => {
      if (!e.features || !e.features[0]) return;
      const feat = e.features[0];
      const props = feat.properties || {};
      const coords = (feat.geometry as any).coordinates.slice();

      const isCutOff = props.road_status === "cut_off" || props.status === "cut_off";
      const badgeColor = isCutOff ? "#ef4444" : "#10b981";
      const statusText = isCutOff ? "ROAD CUT OFF" : props.status === "accessible" ? "ACCESSIBLE" : "BASELINE DISCONNECTED";
      const footStat = props.foot_status === "accessible" ? "OPEN 🟢" : "BLOCKED 🔴";
      const pMC = props.cutoff_probability !== undefined ? `${Math.round(props.cutoff_probability * 100)}%` : "N/A";
      const lzInfo = props.landing_zone ? (typeof props.landing_zone === "string" ? JSON.parse(props.landing_zone) : props.landing_zone) : null;

      const html = `
        <div style="font-family: inherit; color: #0b1020; min-width: 210px;">
          <h4 style="margin: 0 0 6px; font-size: 14px; font-weight: 700;">${props.name || "Settlement"}</h4>
          <div style="margin-bottom: 6px;">
            <span style="background:${badgeColor}; color:#fff; font-size: 10px; font-weight: 700; padding: 2px 6px; border-radius: 4px; text-transform: uppercase;">
              ${statusText}
            </span>
          </div>
          <div style="font-size: 11px; color: #475569; line-height: 1.5;">
            <div><strong>Foot Trail:</strong> ${footStat}</div>
            <div><strong>Monte Carlo Cutoff:</strong> ${pMC}</div>
            <div><strong>Critical Bottleneck:</strong> ${props.critical_bottleneck || "None"}</div>
            ${lzInfo ? `<div><strong>Nearest LZ:</strong> ${lzInfo.nearest_lz_name} (${lzInfo.distance_km} km)</div>` : ""}
            <div><strong>Baseline Access:</strong> ${props.baseline_connected ? "Yes" : "No"}</div>
            <div><strong>Type:</strong> ${props.place || "settlement"}</div>
          </div>
        </div>
      `;

      if (popupRef.current) popupRef.current.remove();
      popupRef.current = new maplibregl.Popup({ offset: 12 })
        .setLngLat(coords)
        .setHTML(html)
        .addTo(map);
    });

    map.on("mouseenter", "settlements-layer", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "settlements-layer", () => {
      map.getCanvas().style.cursor = "";
    });

    // Damaged Road click interaction ("Restore this edge" counterfactual)[cite: 3]
    map.on("click", "damaged-roads-layer", async (e) => {
      const currentJob = jobIdRef.current;
      if (!e.features || !e.features[0] || !currentJob) return;
      const feat = e.features[0];
      const props = feat.properties || {};
      const edgeId = props.edge_id;
      const coords = e.lngLat;

      if (!edgeId) return;

      const loadingHtml = `
        <div style="font-family: inherit; color: #0b1020; min-width: 180px;">
          <h4 style="margin: 0 0 4px; font-size: 13px;">Simulating Edge Repair...</h4>
          <span style="font-size: 11px; color: #64748b;">Evaluating topological reconnection...</span>
        </div>
      `;

      if (popupRef.current) popupRef.current.remove();
      popupRef.current = new maplibregl.Popup({ offset: 10 })
        .setLngLat(coords)
        .setHTML(loadingHtml)
        .addTo(map);

      try {
        const res = await fetch(`${API}/api/v1/jobs/${currentJob}/simulate-restoration`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ edge_id: edgeId }),
        });

        if (!res.ok) throw new Error("Simulation failed");
        const simData = await res.json();

        const count = simData.count_reconnected ?? 0;
        const resultColor = count > 0 ? "#10b981" : "#64748b";

        const simHtml = `
          <div style="font-family: inherit; color: #0b1020; min-width: 200px;">
            <h4 style="margin: 0 0 6px; font-size: 14px; font-weight: 700;">${props.name || "Road Segment"}</h4>
            <div style="font-size: 11px; color: #475569; margin-bottom: 6px;">
              <div><strong>Highway:</strong> ${props.highway || "road"}</div>
              <div><strong>Bridge:</strong> ${props.bridge ? "Yes" : "No"}</div>
            </div>
            <div style="border-top: 1px solid #e2e8f0; padding-top: 6px;">
              <span style="font-size: 11px; font-weight: 600;">Counterfactual Impact:</span>
              <div style="font-size: 13px; font-weight: 700; color: ${resultColor}; margin-top: 2px;">
                ${count > 0 ? `+${count} Settlements Reconnected` : "0 Reconnected (Upstream severed)"}
              </div>
            </div>
          </div>
        `;

        popupRef.current?.setHTML(simHtml);
      } catch (err) {
        popupRef.current?.setHTML(`
          <div style="color: #ef4444; font-size: 11px;">Simulation failed for this edge.</div>
        `);
      }
    });

    map.on("mouseenter", "damaged-roads-layer", () => {
      map.getCanvas().style.cursor = "pointer";
    });
    map.on("mouseleave", "damaged-roads-layer", () => {
      map.getCanvas().style.cursor = "";
    });

    return () => {
      if (pollTimerRef.current) window.clearTimeout(pollTimerRef.current);
      if (popupRef.current) popupRef.current.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // ---------------------------------------------------------
  // LAYER MANAGEMENT
  // ---------------------------------------------------------
  const removeAllLayers = useCallback(() => {
    const map = mapRef.current;
    if (!map) return;

    if (popupRef.current) popupRef.current.remove();

    [
      "hazard-outline", "hazard-fill", 
      "unobservable-outline", "unobservable-fill", 
      "damaged-roads-layer", "settlements-layer"
    ].forEach((layerId) => {
      if (map.getLayer(layerId)) map.removeLayer(layerId);
    });

    ["hazard", "unobservable", "damaged_roads", "settlements"].forEach((sourceId) => {
      if (map.getSource(sourceId)) map.removeSource(sourceId);
    });

    setHasResults(false);
    setSummary(null);
    setProvenance(null);
  }, []);

  const loadLayersAndMetadata = useCallback(async (id: string) => {
    try {
      const map = mapRef.current;
      if (!map) return;

      const layersRes = await fetch(`${API}/api/v1/jobs/${id}/layers`);
      if (layersRes.ok) {
        const rawLayers = await layersRes.json();

        const floodData = Array.isArray(rawLayers)
          ? rawLayers.find((l: any) => l.name === "flood_extent")?.data
          : rawLayers.flood_extent;

        const unobsData = Array.isArray(rawLayers)
          ? rawLayers.find((l: any) => l.name === "unobservable")?.data
          : rawLayers.unobservable;

        const roadsData = Array.isArray(rawLayers)
          ? rawLayers.find((l: any) => l.name === "damaged_roads")?.data
          : rawLayers.damaged_roads;

        const settlementsData = Array.isArray(rawLayers)
          ? rawLayers.find((l: any) => l.name === "settlements")?.data
          : rawLayers.settlements;

        // Flood Extent Layer
        if (floodData) {
          if (map.getSource("hazard")) {
            (map.getSource("hazard") as GeoJSONSource).setData(floodData);
          } else {
            map.addSource("hazard", { type: "geojson", data: floodData });
            map.addLayer({
              id: "hazard-fill",
              type: "fill",
              source: "hazard",
              paint: { "fill-color": "#ef4444", "fill-opacity": 0.45 },
            });
            map.addLayer({
              id: "hazard-outline",
              type: "line",
              source: "hazard",
              paint: { "line-color": "#dc2626", "line-width": 2 },
            });
          }
        }

        // Unobservable Radar Shadow Layer[cite: 3]
        if (unobsData) {
          if (map.getSource("unobservable")) {
            (map.getSource("unobservable") as GeoJSONSource).setData(unobsData);
          } else {
            map.addSource("unobservable", { type: "geojson", data: unobsData });
            map.addLayer({
              id: "unobservable-fill",
              type: "fill",
              source: "unobservable",
              paint: { "fill-color": "#64748b", "fill-opacity": 0.4 },
            });
            map.addLayer({
              id: "unobservable-outline",
              type: "line",
              source: "unobservable",
              paint: { "line-color": "#475569", "line-width": 1.5, "line-dasharray": [2, 2] },
            });
          }
        }

        // Damaged Roads Layer
        if (roadsData) {
          if (map.getSource("damaged_roads")) {
            (map.getSource("damaged_roads") as GeoJSONSource).setData(roadsData);
          } else {
            map.addSource("damaged_roads", { type: "geojson", data: roadsData });
            map.addLayer({
              id: "damaged-roads-layer",
              type: "line",
              source: "damaged_roads",
              paint: { "line-color": "#f97316", "line-width": 3.5 },
            });
          }
        }

        // Settlements Layer
        if (settlementsData) {
          if (map.getSource("settlements")) {
            (map.getSource("settlements") as GeoJSONSource).setData(settlementsData);
          } else {
            map.addSource("settlements", { type: "geojson", data: settlementsData });
            map.addLayer({
              id: "settlements-layer",
              type: "circle",
              source: "settlements",
              paint: {
                "circle-radius": 7,
                "circle-color": [
                  "match",
                  ["get", "status"],
                  "cut_off",
                  "#ef4444",
                  "accessible",
                  "#10b981",
                  "#64748b",
                ],
                "circle-stroke-width": 2,
                "circle-stroke-color": "#ffffff",
              },
            });
          }
        }
      }

      const [sumRes, provRes] = await Promise.all([
        fetch(`${API}/api/v1/jobs/${id}/summary`),
        fetch(`${API}/api/v1/jobs/${id}/provenance`),
      ]);

      if (sumRes.ok) {
        const sumData = await sumRes.json();
        setSummary(sumData.summary || sumData);
      }
      if (provRes.ok) {
        const provData = await provRes.json();
        setProvenance(provData);
      }

      setHasResults(true);
      setHazardVisible(true);
      setRoadsVisible(true);
      setSettlementsVisible(true);
      setUnobservableVisible(true);
    } catch (error) {
      console.error("Failed to load layers or summary:", error);
    }
  }, []);

  // ---------------------------------------------------------
  // POLLING
  // ---------------------------------------------------------
  const monitorJob = useCallback(
    (id: string) => {
      if (pollTimerRef.current) window.clearTimeout(pollTimerRef.current);

      const poll = async () => {
        try {
          const response = await fetch(`${API}/api/v1/jobs/${id}`);
          if (!response.ok) throw new Error("Unable to read job status.");

          const job: Job = await response.json();
          setStatus(job.state);
          setMessage(job.message);

          if (job.state === "COMPLETE") {
            await loadLayersAndMetadata(id);
            return;
          }

          if (job.state === "FAILED") return;

          pollTimerRef.current = window.setTimeout(poll, 700);
        } catch (error) {
          console.error(error);
          setStatus("FAILED");
          setMessage(error instanceof Error ? error.message : "Job failed.");
        }
      };

      poll();
    },
    [loadLayersAndMetadata]
  );

  // ---------------------------------------------------------
  // ACTIONS
  // ---------------------------------------------------------
  function startDrawPolygon() {
    if (!drawRef.current) return;
    drawRef.current.deleteAll();
    setAoi(null);
    drawRef.current.changeMode("draw_polygon");
    setStatus("DRAWING");
    setMessage("Click on map to place polygon vertices. Click the initial vertex to close.");
  }

  function clearAOI() {
    if (pollTimerRef.current) window.clearTimeout(pollTimerRef.current);
    drawRef.current?.deleteAll();
    setAoi(null);
    setJobId(null);
    setStatus("READY");
    setMessage("Draw an analysis area on the map.");
    removeAllLayers();
  }

  async function analyze() {
    if (!aoi) {
      setStatus("ERROR");
      setMessage("Draw an AOI before clicking Analyze.");
      return;
    }

    try {
      setStatus("SUBMITTING");
      setMessage("Submitting job parameters to FloodScope API...");
      removeAllLayers();

      const response = await fetch(`${API}/api/v1/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          aoi,
          flood_date: date,
          config: "default",
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`API request failed: ${errorText}`);
      }

      const job: Job = await response.json();
      const actualId = job.id || job.job_id;
      if (!actualId) throw new Error("No job id returned from server");

      setJobId(actualId);
      setStatus(job.state);
      setMessage(job.message);

      monitorJob(actualId);
    } catch (error) {
      console.error(error);
      setStatus("FAILED");
      setMessage(error instanceof Error ? error.message : "Unable to reach backend.");
    }
  }

  function toggleLayer(layerIds: string[], visible: boolean, setVisible: (v: boolean) => void) {
    const map = mapRef.current;
    if (!map) return;
    const next = !visible;
    const vis = next ? "visible" : "none";
    layerIds.forEach((id) => {
      if (map.getLayer(id)) map.setLayoutProperty(id, "visibility", vis);
    });
    setVisible(next);
  }

  return (
    <div className="app">
      <header>
        <div>
          <div className="eyebrow">Multimodal AI Hackathon 2026 · Track B</div>
          <h1>FloodScope</h1>
          <p>Mapping Flood Damage from Space</p>
        </div>
        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          {provenance?.cache_hit && (
            <span className="badge-cache">CACHE HIT</span>
          )}
          <div className={`status-badge ${status.toLowerCase()}`}>{status}</div>
        </div>
      </header>

      <main>
        <aside>
          <h2>Analyze Area</h2>

          {/* DATE SELECTOR */}
          <div>
            <label htmlFor="flood-date">Flood date</label>
            <input
              id="flood-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
          </div>

          {/* AOI TRIGGER & DELETE */}
          <div className="aoi-box">
            <strong>Analysis Area</strong>
            <div style={{ display: "flex", gap: "8px", marginTop: "4px" }}>
              <button
                type="button"
                className="btn-secondary"
                style={{ flex: 1 }}
                onClick={startDrawPolygon}
              >
                ✏️ Draw Area
              </button>

              {aoi && (
                <button
                  type="button"
                  className="btn-secondary"
                  style={{
                    padding: "8px 12px",
                    borderColor: "#ef4444",
                    color: "#f87171",
                  }}
                  onClick={clearAOI}
                  title="Delete Polygon"
                >
                  🗑️
                </button>
              )}
            </div>

            {aoi ? (
              <>
                <span style={{ color: "#38bdf8", marginTop: "4px" }}>Polygon Locked</span>
                <small>Valid GeoJSON AOI ready for processing.</small>
              </>
            ) : (
              <small>Click "Draw Area" to sketch the boundary on the map.</small>
            )}
          </div>

          {/* ACTIONS */}
          <button
            className="btn-primary"
            onClick={analyze}
            disabled={
              !aoi ||
              ["SUBMITTING", "DISCOVERING", "PROCESSING", "INFERENCE", "NETWORK_ANALYSIS", "REPORTING"].includes(status)
            }
          >
            {["SUBMITTING", "DISCOVERING", "PROCESSING", "INFERENCE", "NETWORK_ANALYSIS", "REPORTING"].includes(status)
              ? "Analyzing..."
              : "Analyze"}
          </button>

          <button className="btn-secondary" onClick={clearAOI}>
            Reset All
          </button>

          {/* METRIC OVERVIEW CARDS */}
          {summary && (
            <div className="summary-grid">
              <div className="stat-card">
                <span className="stat-value" style={{ color: "#ef4444" }}>
                  {summary.settlements_cut_off ?? 0}
                </span>
                <span className="stat-label">Isolated Settlements</span>
              </div>
              <div className="stat-card">
                <span className="stat-value" style={{ color: "#f97316" }}>
                  {summary.damaged_road_segments ?? 0}
                </span>
                <span className="stat-label">Impacted Road Segments</span>
              </div>
              <div className="stat-card">
                <span className="stat-value">
                  {summary.total_settlements ?? 0}
                </span>
                <span className="stat-label">Total Settlements</span>
              </div>
              <div className="stat-card">
                <span className="stat-value">
                  {summary.total_buildings ?? 0}
                </span>
                <span className="stat-label">Pre-event Buildings</span>
              </div>
              <div className="stat-card">
                <span className="stat-value" style={{ color: "#38bdf8" }}>
                  {summary.viable_landing_zones ?? 0}
                </span>
                <span className="stat-label">Viable Landing Zones</span>
              </div>
              <div className="stat-card" style={{ gridColumn: "span 2" }}>
                <span
                  className="stat-value"
                  style={{
                    fontSize: "14px",
                    color: summary.s2_optical_available ? "#10b981" : "#f43f5e",
                  }}
                >
                  {summary.s2_optical_available ? "🛰️ Optical S2 Available" : "No Cloud-Free S2"}
                </span>
                <span className="stat-label">
                  Scene: {summary.s2_optical_date} · Cloud: {summary.s2_cloud_cover}
                </span>
              </div>
            </div>
          )}

          {/* SITUATION REPORT & GIS EXPORT BUTTONS */}
          {jobId && hasResults && (
            <>
              <a
                href={`${API}/api/v1/jobs/${jobId}/report`}
                target="_blank"
                rel="noopener noreferrer"
                className="btn-secondary"
                style={{
                  display: "block",
                  textAlign: "center",
                  textDecoration: "none",
                  marginTop: "12px",
                  borderColor: "#38bdf8",
                  color: "#38bdf8",
                  fontWeight: 600,
                  background: "rgba(56, 189, 248, 0.1)",
                }}
              >
                📄 View Situation Report
              </a>

              <a
                href={`${API}/api/v1/jobs/${jobId}/export`}
                download={`floodscope_export_${jobId}.zip`}
                className="btn-secondary"
                style={{
                  display: "block",
                  textAlign: "center",
                  textDecoration: "none",
                  marginTop: "8px",
                  borderColor: "#10b981",
                  color: "#10b981",
                  fontWeight: 600,
                  background: "rgba(16, 185, 129, 0.1)",
                }}
              >
                📦 Export GIS Data (.zip)
              </a>
            </>
          )}

          {/* STATUS MESSAGE */}
          <div className="message">
            <strong>Status Info</strong>
            <span>{message}</span>
          </div>

          {/* PROVENANCE DRAWER */}
          {provenance && (
            <div className="provenance-box">
              <strong>Provenance</strong>
              <div className="prov-row">
                <span>OSM Snapshot:</span>
                <code>{provenance.osm_snapshot}</code>
              </div>
              <div className="prov-row">
                <span>Data Source:</span>
                <span>ohsome v2 API</span>
              </div>
            </div>
          )}

          {/* LAYERS */}
          <div className="legend">
            <strong>Layers</strong>
            <div className="legend-list">
              <div className="legend-item">
                <span>☑</span> OpenStreetMap
              </div>
              <div className="legend-item">
                <span>{aoi ? "☑" : "□"}</span> Analysis AOI
              </div>

              {/* Hazard Fill Toggle */}
              <button
                type="button"
                className="layer-toggle"
                onClick={() =>
                  toggleLayer(
                    ["hazard-fill", "hazard-outline"],
                    hazardVisible,
                    setHazardVisible
                  )
                }
                disabled={!hasResults}
              >
                <span>{hazardVisible && hasResults ? "☑" : "□"}</span>
                <span className="hazard-swatch"></span>
                Flood Hazard Extent
              </button>

              {/* Unobservable Layer Toggle[cite: 3] */}
              <button
                type="button"
                className="layer-toggle"
                onClick={() =>
                  toggleLayer(
                    ["unobservable-fill", "unobservable-outline"],
                    unobservableVisible,
                    setUnobservableVisible
                  )
                }
                disabled={!hasResults}
              >
                <span>{unobservableVisible && hasResults ? "☑" : "□"}</span>
                <span
                  style={{
                    width: 12,
                    height: 12,
                    background: "#64748b",
                    opacity: 0.7,
                    display: "inline-block",
                    border: "1px dashed #94a3b8",
                  }}
                ></span>
                Unobservable (Radar Shadow)
              </button>

              {/* Damaged Roads Toggle */}
              <button
                type="button"
                className="layer-toggle"
                onClick={() =>
                  toggleLayer(
                    ["damaged-roads-layer"],
                    roadsVisible,
                    setRoadsVisible
                  )
                }
                disabled={!hasResults}
              >
                <span>{roadsVisible && hasResults ? "☑" : "□"}</span>
                <span
                  style={{
                    width: 12,
                    height: 4,
                    background: "#f97316",
                    display: "inline-block",
                  }}
                ></span>
                Impacted Roads
              </button>

              {/* Settlements Toggle */}
              <button
                type="button"
                className="layer-toggle"
                onClick={() =>
                  toggleLayer(
                    ["settlements-layer"],
                    settlementsVisible,
                    setSettlementsVisible
                  )
                }
                disabled={!hasResults}
              >
                <span>{settlementsVisible && hasResults ? "☑" : "□"}</span>
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    background: "#ef4444",
                    display: "inline-block",
                  }}
                ></span>
                Settlements Status
              </button>
            </div>
          </div>
        </aside>

        <section className="map-wrap">
          <div ref={mapContainer} className="map" />
        </section>
      </main>
    </div>
  );
}