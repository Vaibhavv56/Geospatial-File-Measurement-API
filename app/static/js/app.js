let map = null;
let geojsonLayer = null;
let currentFeatures = [];

document.addEventListener("DOMContentLoaded", () => {
  initMap();
  initUploadHandlers();
  initTabs();
  initFilter();
  initSampleButtons();
});

function initMap() {
  map = L.map("map", {
    zoomControl: true,
    attributionControl: true
  }).setView([20.5937, 78.9629], 5);

  // CartoDB Dark Matter tile layer for cohesive dark theme
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: "abcd",
    maxZoom: 19
  }).addTo(map);
}

function initUploadHandlers() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("fileInput");
  const browseBtn = document.getElementById("browseBtn");

  browseBtn.addEventListener("click", () => fileInput.click());
  dropzone.addEventListener("click", (e) => {
    if (e.target !== browseBtn) fileInput.click();
  });

  ["dragenter", "dragover"].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(name => {
    dropzone.addEventListener(name, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      uploadFile(files[0]);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files.length > 0) {
      uploadFile(e.target.files[0]);
    }
  });
}

function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(tc => tc.classList.remove("active"));
      btn.classList.add("active");
      const targetId = `tab-${btn.dataset.tab}`;
      const target = document.getElementById(targetId);
      if (target) target.classList.add("active");
    });
  });
}

function initFilter() {
  const filterInput = document.getElementById("tableFilter");
  filterInput.addEventListener("input", (e) => {
    const term = e.target.value.toLowerCase().trim();
    const rows = document.querySelectorAll("#featuresTableBody tr");
    rows.forEach(row => {
      const text = row.innerText.toLowerCase();
      row.style.display = text.includes(term) ? "" : "none";
    });
  });
}

function initSampleButtons() {
  document.getElementById("loadSampleKmlBtn").addEventListener("click", () => loadSampleFile("/samples/survey_parcels.kml", "survey_parcels.kml"));
  document.getElementById("loadSampleShpBtn").addEventListener("click", () => loadSampleFile("/samples/cadastral_parcels.zip", "cadastral_parcels.zip"));
  document.getElementById("loadSampleRoadsBtn").addEventListener("click", () => loadSampleFile("/samples/road_network.kml", "road_network.kml"));
}

async function loadSampleFile(url, filename) {
  try {
    showProgress(`Fetching sample '${filename}'...`);
    const res = await fetch(url);
    if (!res.ok) throw new Error(`Could not fetch sample file: ${res.statusText}`);
    const blob = await res.blob();
    const file = new File([blob], filename);
    await uploadFile(file);
  } catch (err) {
    showError(err.message);
  }
}

async function uploadFile(file) {
  const ext = file.name.split('.').pop().toLowerCase();
  if (ext !== 'kml' && ext !== 'zip') {
    showError("Please upload a .kml file or a .zip archive containing an ESRI Shapefile.");
    return;
  }

  showProgress(`Uploading and processing ${file.name}...`);
  hideError();

  const formData = new FormData();
  formData.append("file", file);

  try {
    // 1. POST /api/files/
    const uploadRes = await fetch("/api/files/", {
      method: "POST",
      body: formData,
    });

    if (!uploadRes.ok) {
      const errData = await uploadRes.json().catch(() => ({}));
      throw new Error(errData.detail || `Upload failed (${uploadRes.status})`);
    }

    const fileMeta = await uploadRes.json();

    // 2. GET /api/files/{id}/measurements/
    const measRes = await fetch(`/api/files/${fileMeta.id}/measurements/`);
    if (!measRes.ok) {
      throw new Error("Failed to fetch feature measurements.");
    }
    const measurementsData = await measRes.json();

    hideProgress();
    displayResults(fileMeta, measurementsData);
  } catch (err) {
    hideProgress();
    showError(err.message);
  }
}

function displayResults(fileMeta, measurementsData) {
  document.getElementById("resultsSection").classList.remove("hidden");

  // Populate Stats
  document.getElementById("statFilename").innerText = fileMeta.filename;
  document.getElementById("statFileId").innerText = `ID: ${fileMeta.id}`;
  document.getElementById("statFeatureCount").innerText = fileMeta.feature_count;
  
  const sum = fileMeta.summary || measurementsData.summary || {};
  document.getElementById("statFeatureTypes").innerText = 
    `${sum.polygon_count || 0} Polygons • ${sum.linestring_count || 0} Lines • ${sum.point_count || 0} Points`;

  document.getElementById("statCrs").innerText = fileMeta.crs || "EPSG:4326";
  
  // Find projected CRS used from features
  const firstProjected = measurementsData.features.find(f => f.measurement && f.measurement.projected_crs);
  document.getElementById("statProjectedCrs").innerText = firstProjected 
    ? `Projected: ${firstProjected.measurement.projected_crs}` 
    : "Metric Projection";

  const totalAreaM2 = sum.total_area_sq_meters || 0;
  const totalAreaHa = sum.total_area_hectares || (totalAreaM2 / 10000);
  document.getElementById("statTotalArea").innerText = `${totalAreaM2.toLocaleString()} m²`;
  document.getElementById("statTotalAreaHectares").innerText = `${totalAreaHa.toFixed(2)} hectares`;

  const totalLenM = sum.total_length_meters || 0;
  const totalLenKm = sum.total_length_km || (totalLenM / 1000);
  document.getElementById("statTotalLength").innerText = `${totalLenM.toLocaleString()} m`;
  document.getElementById("statTotalLengthKm").innerText = `${totalLenKm.toFixed(3)} km`;

  // Populate Inspector JSON
  document.getElementById("jsonFileInfoCode").innerText = JSON.stringify(fileMeta, null, 2);
  document.getElementById("jsonMeasurementsCode").innerText = JSON.stringify(measurementsData, null, 2);

  // Render Map & Table
  currentFeatures = measurementsData.features;
  renderMap(measurementsData.features);
  renderTable(measurementsData.features);
}

function renderMap(features) {
  if (geojsonLayer) {
    map.removeLayer(geojsonLayer);
  }

  const geojsonFeatures = features
    .filter(f => f.geometry)
    .map(f => ({
      type: "Feature",
      id: f.feature_id,
      geometry: f.geometry,
      properties: {
        ...f.properties,
        _id: f.feature_id,
        _type: f.geometry_type,
        _meas: f.measurement
      }
    }));

  document.getElementById("mapLayerCount").innerText = `${geojsonFeatures.length} features rendered`;

  if (geojsonFeatures.length === 0) return;

  const geojsonCollection = {
    type: "FeatureCollection",
    features: geojsonFeatures
  };

  geojsonLayer = L.geoJSON(geojsonCollection, {
    style: (feature) => {
      const type = (feature.properties._type || "").toLowerCase();
      if (type.includes("polygon")) {
        return {
          color: "#818cf8",
          weight: 2,
          opacity: 0.9,
          fillColor: "#6366f1",
          fillOpacity: 0.35
        };
      } else if (type.includes("linestring") || type.includes("ring")) {
        return {
          color: "#f59e0b",
          weight: 3.5,
          opacity: 0.9
        };
      }
      return { color: "#38bdf8", weight: 2 };
    },
    pointToLayer: (feature, latlng) => {
      return L.circleMarker(latlng, {
        radius: 6,
        fillColor: "#38bdf8",
        color: "#ffffff",
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.85
      });
    },
    onEachFeature: (feature, layer) => {
      const p = feature.properties;
      const m = p._meas || {};
      
      let measHtml = '';
      if (m.type === 'area') {
        measHtml = `
          <div style="margin-top:6px; padding:6px; background:#1e293b; border-radius:4px; font-size:12px;">
            <strong>Area:</strong> ${m.area_sq_meters.toLocaleString()} m² (${m.area_hectares} ha)<br/>
            <strong>Perimeter:</strong> ${m.perimeter_meters ? m.perimeter_meters.toLocaleString() + ' m' : 'N/A'}<br/>
            <span style="color:#94a3b8; font-size:11px;">CRS: ${m.projected_crs}</span>
          </div>`;
      } else if (m.type === 'length') {
        measHtml = `
          <div style="margin-top:6px; padding:6px; background:#1e293b; border-radius:4px; font-size:12px;">
            <strong>Length:</strong> ${m.length_meters.toLocaleString()} m (${m.length_km} km)<br/>
            <span style="color:#94a3b8; font-size:11px;">CRS: ${m.projected_crs}</span>
          </div>`;
      } else {
        measHtml = `
          <div style="margin-top:6px; padding:6px; background:#1e293b; border-radius:4px; font-size:11px; color:#cbd5e1;">
            ${m.message || 'No measurement required'}
          </div>`;
      }

      const popupContent = `
        <div style="font-family:'Plus Jakarta Sans',sans-serif; min-width:180px;">
          <h4 style="margin:0 0 4px 0; font-size:13px; color:#38bdf8;">Feature ID: ${p._id}</h4>
          <span style="font-size:11px; font-weight:600; color:#cbd5e1;">Type: ${p._type}</span>
          ${measHtml}
        </div>
      `;
      layer.bindPopup(popupContent);
    }
  }).addTo(map);

  try {
    const bounds = geojsonLayer.getBounds();
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  } catch (e) {
    console.warn("Could not fit map bounds:", e);
  }
}

function renderTable(features) {
  const tbody = document.getElementById("featuresTableBody");
  tbody.innerHTML = "";

  features.forEach(f => {
    const tr = document.createElement("tr");
    const m = f.measurement || {};
    const typeLower = f.geometry_type.toLowerCase();

    // Type Badge
    let typeBadge = `<span class="badge badge-point">${f.geometry_type}</span>`;
    if (typeLower.includes("polygon")) {
      typeBadge = `<span class="badge badge-polygon">${f.geometry_type}</span>`;
    } else if (typeLower.includes("linestring") || typeLower.includes("ring")) {
      typeBadge = `<span class="badge badge-linestring">${f.geometry_type}</span>`;
    }

    // Measurement column
    let measTypeStr = m.type || "none";
    let primaryVal = "-";
    let secondaryVal = "-";
    let crsVal = m.projected_crs || "-";

    if (m.type === "area") {
      measTypeStr = '<span style="color:#a5b4fc; font-weight:600;">Area</span>';
      primaryVal = `<strong>${m.area_sq_meters.toLocaleString()}</strong> m²`;
      secondaryVal = `${m.area_hectares} ha • ${m.area_acres || 0} acres`;
    } else if (m.type === "length") {
      measTypeStr = '<span style="color:#fbbf24; font-weight:600;">Length</span>';
      primaryVal = `<strong>${m.length_meters.toLocaleString()}</strong> m`;
      secondaryVal = `${m.length_km} km`;
    } else {
      measTypeStr = '<span style="color:#94a3b8;">None</span>';
      primaryVal = `<span class="text-dim">${m.message || "No measurement"}</span>`;
    }

    // Properties formatting
    const propKeys = Object.keys(f.properties || {});
    let propsSnippet = "-";
    if (propKeys.length > 0) {
      propsSnippet = propKeys.slice(0, 3).map(k => `<strong>${k}:</strong> ${f.properties[k]}`).join(", ");
      if (propKeys.length > 3) propsSnippet += ` <span class="text-dim">(+${propKeys.length - 3} more)</span>`;
    }

    tr.innerHTML = `
      <td class="font-mono text-sm">${f.feature_id}</td>
      <td>${typeBadge}</td>
      <td>${measTypeStr}</td>
      <td>${primaryVal}</td>
      <td class="text-sm">${secondaryVal}</td>
      <td class="font-mono text-sm">${crsVal}</td>
      <td class="text-sm">${propsSnippet}</td>
    `;
    tbody.appendChild(tr);
  });
}

function showProgress(msg) {
  const p = document.getElementById("uploadProgress");
  document.getElementById("uploadStatusText").innerText = msg;
  p.classList.remove("hidden");
}

function hideProgress() {
  document.getElementById("uploadProgress").classList.add("hidden");
}

function showError(msg) {
  const a = document.getElementById("alertBox");
  a.className = "alert alert-error";
  a.innerText = msg;
  a.classList.remove("hidden");
}

function hideError() {
  document.getElementById("alertBox").classList.add("hidden");
}
