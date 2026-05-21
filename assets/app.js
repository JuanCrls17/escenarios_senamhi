/* =========================================================
   app.js — SENAMHI PERÚ · Escenarios Climáticos
   Leaflet standalone, sin Streamlit
   ========================================================= */
"use strict";

// ─── Paletas de colores ────────────────────────────────────
const PREC_BINS   = [-999,-90,-75,-60,-45,-30,-15,0,15,30,45,60,75,90,999];
const PREC_COLORS = [
  "#663300","#7b4d1b","#916836","#a68351","#bc9d6d","#d2b888","#e7d3a3",
  "#c1f4db","#a1d4bf","#80b3a3","#609387","#40736b","#20534f","#003333"
];
const TEMP_BINS   = [-999,0.2,0.4,0.6,0.8,1.0,1.2,1.4,1.6,1.8,2.0,2.2,
                     2.4,2.6,2.8,3.0,3.2,3.4,3.6,3.8,999];
const TEMP_COLORS = [
  "#ffffcc","#fff7b9","#fff0a7","#ffe895","#fee983","#fed572","#fec460",
  "#feb44e","#fea446","#fd953f","#fd8038","#fc6531","#fb4b29","#f03523",
  "#e61f1d","#d7121f","#c70723","#b30026","#9a0026","#800026"
];

const IMC_COLORS = {
  "Muy Alto": "#d7191c",
  "Alto":     "#f7941d",
  "Medio":    "#f1dd00",
  "Bajo":     "#9bc68b",
};

// ─── Estado de la aplicación ──────────────────────────────
const state = {
  variable:  "pr",     // "pr" | "tasmax" | "tasmin" | "imc"
  estacion:  "anual",
  imcActive: false,
  imcTipo:   "agricola",
  refLayer:  "departamentos",
};

// ─── Capas Leaflet activas ────────────────────────────────
let climateLayer    = null;
let imcLayer        = null;
let refGeoLayer     = null;
let searchMarker    = null;
let selectedFeature = null;  // capa actualmente seleccionada (resaltada)

// ─── Inicializar mapa ─────────────────────────────────────
const map = L.map("map", {
  center: [-9, -75],
  zoom: 5,
  zoomControl: false,
  attributionControl: false,
});

L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
}).addTo(map);

// ─── Zoom personalizado ───────────────────────────────────
document.getElementById("zoomIn").addEventListener("click",  () => map.zoomIn());
document.getElementById("zoomOut").addEventListener("click", () => map.zoomOut());

// ─── Loader ───────────────────────────────────────────────
const loader = document.getElementById("mapLoader");
function showLoader() { loader.style.display = "flex"; }
function hideLoader() { loader.style.display = "none"; }

// ─── Helpers de color ─────────────────────────────────────
function getClimateColor(value, variable) {
  if (value == null) return "#cccccc";
  const v = parseFloat(value);
  if (isNaN(v)) return "#cccccc";
  const bins   = variable === "pr" ? PREC_BINS   : TEMP_BINS;
  const colors = variable === "pr" ? PREC_COLORS : TEMP_COLORS;
  for (let i = 0; i < bins.length - 1; i++) {
    if (v > bins[i] && v <= bins[i + 1]) return colors[i];
  }
  return "#cccccc";
}

function getImcColor(value) {
  if (value == null) return "#cccccc";
  const v = parseFloat(value);
  if (isNaN(v)) return "#cccccc";
  if (v >= 0.75) return IMC_COLORS["Muy Alto"];
  if (v >= 0.50) return IMC_COLORS["Alto"];
  if (v >= 0.25) return IMC_COLORS["Medio"];
  return IMC_COLORS["Bajo"];
}

function imcLabel(value) {
  const v = parseFloat(value);
  if (isNaN(v)) return "Sin dato";
  if (v >= 0.75) return "Muy Alto";
  if (v >= 0.50) return "Alto";
  if (v >= 0.25) return "Medio";
  return "Bajo";
}

// ─── Nombre de archivo GeoJSON ────────────────────────────
function climateFilename(variable, estacion) {
  const est = estacion === "anual" ? "anual" : estacion.toUpperCase();
  return `data/distritos_cambio_${variable}_${est}_cmip6_2036_2065_5km.geojson`;
}

function imcFilename(tipo) {
  return `data/indice_multipeligro_${tipo}_2036_2065.geojson`;
}

function refFilename(layer) {
  return `data/${layer}.geojson`;
}

// ─── Carga de GeoJSON con fetch ───────────────────────────
async function fetchGeoJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`No se encontró: ${path}`);
  return res.json();
}

// ─── Tooltip / popup ─────────────────────────────────────
function buildTooltip(props, variable, isImc) {
  const distrito = props.DISTRITO || props.DEPARTAMEN || props.PROVINCIA || props.NOMBRE || "—";
  const valor    = props.valor != null ? props.valor : null;
  if (isImc) {
    const lbl = valor != null ? imcLabel(valor) : "Sin dato";
    const fmt = valor != null ? parseFloat(valor).toFixed(3) : "—";
    return `<b>${distrito}</b><br>IMC: ${fmt} <span style="font-weight:700;color:${getImcColor(valor)}">(${lbl})</span>`;
  }
  const unit = variable === "pr" ? "%" : "°C";
  const fmt  = valor != null ? `${parseFloat(valor).toFixed(1)} ${unit}` : "Sin dato";
  return `<b>${distrito}</b><br>Valor: <b>${fmt}</b>`;
}

// ─── Panel de información lateral ─────────────────────────
function showInfoPanel(props, variable, isImc) {
  const panel = document.getElementById("infoPanel");
  const body  = document.getElementById("infoPanelBody");

  const distrito = props.DISTRITO || props.DEPARTAMEN || props.PROVINCIA || props.NOMBRE || "—";
  const valor    = props.valor != null ? props.valor : null;

  const rows = [];

  rows.push({ k: "Distrito", v: distrito });

  if (isImc) {
    const lbl = valor != null ? imcLabel(valor) : "Sin dato";
    const fmt = valor != null ? parseFloat(valor).toFixed(3) : "—";
    rows.push({ k: "Tipo IMC",   v: state.imcTipo.charAt(0).toUpperCase() + state.imcTipo.slice(1) });
    rows.push({ k: "Valor IMC",  v: fmt, highlight: true });
    rows.push({ k: "Categoría",  v: lbl });
  } else {
    const varNames = { pr: "Precipitación", tasmax: "T° Máxima", tasmin: "T° Mínima" };
    const unit = variable === "pr" ? "%" : "°C";
    const fmt  = valor != null ? `${parseFloat(valor).toFixed(1)} ${unit}` : "Sin dato";
    rows.push({ k: "Variable",   v: varNames[variable] || variable });
    rows.push({ k: "Estación",   v: seasonLabel(state.estacion) });
    rows.push({ k: "Período",    v: "2036–2065" });
    rows.push({ k: "Valor",      v: fmt, highlight: true });
  }

  body.innerHTML = rows.map(r =>
    `<div class="info-row">
      <span class="info-key">${r.k}</span>
      <span class="info-val${r.highlight ? " highlight" : ""}">${r.v}</span>
    </div>`
  ).join("");

  // Posicionar el panel debajo del buscador flotante
  const floatBox = document.getElementById("mapSearchFloat");
  if (floatBox) {
    const floatRect    = floatBox.getBoundingClientRect();
    const containerRect = document.querySelector(".map-container").getBoundingClientRect();
    const topOffset    = floatRect.bottom - containerRect.top + 10;
    panel.style.top    = topOffset + "px";
  }
  panel.style.display = "block";
}

document.getElementById("closeInfoPanel").addEventListener("click", () => {
  document.getElementById("infoPanel").style.display = "none";
});

// ─── Leyenda ──────────────────────────────────────────────
function buildClimateLegend(variable) {
  const el = document.getElementById("mapLegend");
  const isPrec = variable === "pr";
  const bins   = isPrec ? PREC_BINS   : TEMP_BINS;
  const colors = isPrec ? PREC_COLORS : TEMP_COLORS;
  const unit   = isPrec ? "%" : "°C";
  const title  = isPrec ? "Δ Precipitación (%)" : `Δ Temperatura (°C)`;

  const items = colors.map((c, i) => {
    const lo = bins[i], hi = bins[i + 1];
    const label = lo <= -900 ? `≤ ${hi}` : hi >= 900 ? `≥ ${lo}` : `${lo} – ${hi}`;
    return `<div class="legend-item">
      <span class="legend-swatch" style="background:${c}"></span>
      <span class="legend-label">${label} ${unit}</span>
    </div>`;
  }).join("");

  el.innerHTML = `
    <div class="legend-title">${title}</div>
    <div class="legend-ref-note">Cambio respecto a 1981–2010</div>
    ${items}`;
}

function buildImcLegend() {
  const el = document.getElementById("mapLegend");
  const items = [
    ["Muy Alto", "≥ 0.75", "#d7191c", "Exposición crítica a múltiples peligros climáticos"],
    ["Alto",     "0.50–0.75", "#f7941d", "Alta concurrencia de amenazas climáticas"],
    ["Medio",    "0.25–0.50", "#f1dd00", "Exposición moderada a peligros climáticos"],
    ["Bajo",     "< 0.25",    "#9bc68b", "Baja exposición a peligros climáticos"],
  ].map(([cat, rng, c, desc]) =>
    `<div class="legend-item" style="align-items:flex-start; margin-bottom:8px;">
      <span class="legend-swatch" style="background:${c}; margin-top:3px; flex-shrink:0;"></span>
      <span style="display:flex; flex-direction:column; gap:1px;">
        <span class="legend-label" style="font-weight:700; color:#1a2236;">${cat} <span style="font-weight:400; color:#888;">(${rng})</span></span>
        <span style="font-size:0.62rem; color:#6b7a8d; line-height:1.3;">${desc}</span>
      </span>
    </div>`
  ).join("");

  el.innerHTML = `
    <div class="legend-title">Índice Multipeligro Climático</div>
    <div class="legend-ref-note">Cambio respecto a 1981–2010</div>
    ${items}`;
}

// ─── Cargar/refrescar capa climática ─────────────────────
async function loadClimateLayer() {
  if (climateLayer) { map.removeLayer(climateLayer); climateLayer = null; }
  selectedFeature = null;
  document.getElementById("infoPanel").style.display = "none";
  if (state.imcActive || state.variable === "imc") return;

  showLoader();
  try {
    const data = await fetchGeoJSON(climateFilename(state.variable, state.estacion));
    climateLayer = L.geoJSON(data, {
      style: feat => ({
        fillColor: getClimateColor(feat.properties.valor, state.variable),
        fillOpacity: 0.85,
        color: "#666",
        weight: 0.4,
      }),
      onEachFeature: (feat, layer) => {
        layer.on({
          mouseover(e) {
            if (e.target !== selectedFeature)
              e.target.setStyle({ weight: 1.8, color: "#3a6ea8", fillOpacity: 0.95 });
            layer.bindTooltip(buildTooltip(feat.properties, state.variable, false), { sticky: true }).openTooltip();
          },
          mouseout(e) {
            if (e.target !== selectedFeature) climateLayer.resetStyle(e.target);
          },
          click(e) {
            // Quitar resaltado anterior
            if (selectedFeature && climateLayer) climateLayer.resetStyle(selectedFeature);
            // Resaltar el nuevo
            selectedFeature = e.target;
            e.target.setStyle({ weight: 2.5, color: "#1e5bb5", fillOpacity: 0.97,
                                 dashArray: null });
            e.target.bringToFront();
            showInfoPanel(feat.properties, state.variable, false);
          },
        });
      },
    }).addTo(map);
    buildClimateLegend(state.variable);
  } catch (err) {
    console.warn("Capa climática no disponible:", err.message);
    document.getElementById("mapLegend").innerHTML = "";
  } finally {
    hideLoader();
  }
}

// ─── Cargar/refrescar capa IMC ────────────────────────────
async function loadImcLayer() {
  if (climateLayer) { map.removeLayer(climateLayer); climateLayer = null; }
  if (imcLayer)     { map.removeLayer(imcLayer);     imcLayer     = null; }
  selectedFeature = null;
  document.getElementById("infoPanel").style.display = "none";
  if (!state.imcActive) { loadClimateLayer(); return; }

  showLoader();
  try {
    const data = await fetchGeoJSON(imcFilename(state.imcTipo));
    imcLayer = L.geoJSON(data, {
      style: feat => ({
        fillColor: getImcColor(feat.properties.valor),
        fillOpacity: 0.82,
        color: "#5e005e",
        weight: 0.5,
      }),
      onEachFeature: (feat, layer) => {
        layer.on({
          mouseover(e) {
            if (e.target !== selectedFeature)
              e.target.setStyle({ weight: 1.8, color: "#3a6ea8", fillOpacity: 0.95 });
            layer.bindTooltip(buildTooltip(feat.properties, null, true), { sticky: true }).openTooltip();
          },
          mouseout(e) {
            if (e.target !== selectedFeature) imcLayer.resetStyle(e.target);
          },
          click(e) {
            if (selectedFeature && imcLayer) imcLayer.resetStyle(selectedFeature);
            selectedFeature = e.target;
            e.target.setStyle({ weight: 2.5, color: "#1e5bb5", fillOpacity: 0.97 });
            e.target.bringToFront();
            showInfoPanel(feat.properties, null, true);
          },
        });
      },
    }).addTo(map);
    buildImcLegend();
  } catch (err) {
    console.warn("Capa IMC no disponible:", err.message);
    document.getElementById("mapLegend").innerHTML = "";
  } finally {
    hideLoader();
  }
}

// ─── Cargar capa de referencia ────────────────────────────
async function loadRefLayer(key) {
  if (refGeoLayer) { map.removeLayer(refGeoLayer); refGeoLayer = null; }
  if (key === "ninguna") return;

  try {
    const data = await fetchGeoJSON(refFilename(key));
    refGeoLayer = L.geoJSON(data, {
      style: {
        color: "#000",
        weight: 0.9,
        fillOpacity: 0,
        interactive: false,
      },
    }).addTo(map);
  } catch (err) {
    console.warn("Capa de referencia no disponible:", err.message);
  }
}

// ─── Helpers de etiquetas ─────────────────────────────────
function seasonLabel(v) {
  return { anual:"Anual", DEF:"Verano (DJF)", MAM:"Otoño (MAM)", JJA:"Invierno (JJA)", SON:"Primavera (SON)" }[v] || v;
}

// ─── Radio group genérico ─────────────────────────────────
function setupRadioGroup(groupId, onSelect) {
  const group = document.getElementById(groupId);
  if (!group) return;
  group.querySelectorAll(".radio-card").forEach(card => {
    card.addEventListener("click", () => {
      group.querySelectorAll(".radio-card").forEach(c => c.classList.remove("active"));
      card.classList.add("active");
      onSelect(card.dataset.value);
    });
  });
}

// ─── Bloquear / desbloquear botones de estación ───────────
function setSeasonBlocked(blocked) {
  const btns = document.querySelectorAll(".btn-season");
  const msg  = document.getElementById("seasonBlockedMsg");
  btns.forEach(btn => {
    if (blocked && btn.dataset.value !== "anual") {
      btn.classList.add("blocked");
    } else {
      btn.classList.remove("blocked");
    }
  });
  if (msg) msg.style.display = blocked ? "block" : "none";

  // Si IMC se activa y la estación actual no es anual → forzar anual
  if (blocked && state.estacion !== "anual") {
    btns.forEach(b => b.classList.remove("active"));
    document.querySelector('.btn-season[data-value="anual"]').classList.add("active");
    state.estacion = "anual";
  }
}

// ─── Botones estación ─────────────────────────────────────
document.querySelectorAll(".btn-season").forEach(btn => {
  btn.addEventListener("click", () => {
    if (btn.classList.contains("blocked")) return;
    document.querySelectorAll(".btn-season").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.estacion = btn.dataset.value;
    loadClimateLayer();
  });
});

// ─── Variable climática (incluye IMC como opción) ─────────
setupRadioGroup("varGroup", value => {
  if (value === "imc") {
    state.imcActive = true;
    state.variable  = "imc";
    setSeasonBlocked(true);
    loadImcLayer();
  } else {
    state.imcActive = false;
    state.variable  = value;
    setSeasonBlocked(false);
    loadClimateLayer();
  }
});

// ─── Capa de referencia (radio exclusivo) ─────────────────
setupRadioGroup("refLayerGroup", value => {
  state.refLayer = value;
  loadRefLayer(value);
});

// ─── Marcador de búsqueda ─────────────────────────────────
function placeSearchMarker(lat, lon, label) {
  if (searchMarker) { map.removeLayer(searchMarker); searchMarker = null; }
  const icon = L.divIcon({
    className: "",
    html: '<div class="search-marker-icon"></div>',
    iconSize: [16, 16],
    iconAnchor: [8, 8],
  });
  searchMarker = L.marker([lat, lon], { icon })
    .addTo(map)
    .bindTooltip(label || `${lat.toFixed(5)}, ${lon.toFixed(5)}`, { permanent: false });
  map.setView([lat, lon], 11, { animate: true });
}

// ─── Buscador de lugares (Nominatim) ─────────────────────
const placeInput       = document.getElementById("placeInput");
const placeSuggestions = document.getElementById("placeSuggestions");
const placeClearBtn    = document.getElementById("placeClearBtn");
let   searchTimer      = null;

function hideSuggestions() {
  placeSuggestions.innerHTML = "";
}

function showSuggestions(html) {
  placeSuggestions.innerHTML = html;
}

placeInput.addEventListener("input", () => {
  const q = placeInput.value.trim();
  placeClearBtn.style.display = q ? "block" : "none";
  clearTimeout(searchTimer);
  if (q.length < 2) { hideSuggestions(); return; }

  showSuggestions(`<div class="place-searching">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4a7ec0" stroke-width="2.5" style="animation:spin 0.7s linear infinite;flex-shrink:0">
      <path d="M12 2a10 10 0 0 1 10 10" />
    </svg>
    Buscando resultados…
  </div>`);

  searchTimer = setTimeout(async () => {
    try {
      const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&countrycodes=pe&limit=6&addressdetails=1`;
      const res  = await fetch(url, { headers: { "Accept-Language": "es" } });
      const data = await res.json();

      if (!data.length) {
        showSuggestions(`<div class="place-suggestions-empty">
          <div class="place-suggestions-empty-icon">🔍</div>
          <div class="place-suggestions-empty-text">Sin resultados para "<strong>${q}</strong>"<br>Intenta con otro nombre</div>
        </div>`);
        return;
      }

      const items = data.map(item => {
        const parts  = item.display_name.split(",");
        const name   = parts[0].trim();
        const detail = parts.slice(1, 3).join(",").trim();
        return `<div class="place-suggestion-item"
                  data-lat="${item.lat}" data-lon="${item.lon}" data-name="${name}">
          <div class="place-suggestion-pin-wrap">📍</div>
          <div>
            <div class="place-suggestion-name">${name}</div>
            <div class="place-suggestion-detail">${detail}</div>
          </div>
        </div>`;
      }).join("");

      showSuggestions(items);

      placeSuggestions.querySelectorAll(".place-suggestion-item").forEach(el => {
        el.addEventListener("click", () => {
          const lat  = parseFloat(el.dataset.lat);
          const lon  = parseFloat(el.dataset.lon);
          const name = el.dataset.name;
          placeInput.value = name;
          placeClearBtn.style.display = "block";
          hideSuggestions();
          placeSearchMarker(lat, lon, name);
        });
      });
    } catch {
      showSuggestions(`<div class="place-suggestions-empty">
        <div class="place-suggestions-empty-icon">⚠️</div>
        <div class="place-suggestions-empty-text">Error de conexión. Inténtalo de nuevo.</div>
      </div>`);
    }
  }, 380);
});

placeClearBtn.addEventListener("click", () => {
  placeInput.value = "";
  placeClearBtn.style.display = "none";
  hideSuggestions();
  if (searchMarker) { map.removeLayer(searchMarker); searchMarker = null; }
});

document.addEventListener("click", e => {
  if (!e.target.closest(".map-search-float")) hideSuggestions();
});

// ─── Toggle panel coordenadas ─────────────────────────────
document.getElementById("coordToggle").addEventListener("click", () => {
  const panel = document.getElementById("coordPanel");
  panel.style.display = panel.style.display === "none" ? "block" : "none";
});

// ─── Búsqueda por coordenadas ─────────────────────────────
document.getElementById("btnBuscar").addEventListener("click", () => {
  const lat = parseFloat(document.getElementById("latInput").value.replace(",", "."));
  const lon = parseFloat(document.getElementById("lonInput").value.replace(",", "."));
  if (isNaN(lat) || isNaN(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    alert("Coordenadas no válidas. Latitud: −90 a 90 · Longitud: −180 a 180");
    return;
  }
  placeSearchMarker(lat, lon);
});

// ─── Carga inicial ────────────────────────────────────────
loadClimateLayer();
loadRefLayer("departamentos");
