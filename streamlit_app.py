import os
import io
import json
import base64
import streamlit as st
from PIL import Image

# =========================================================
# CONFIG
# =========================================================
st.set_page_config(
    page_title="SENAMHI PERÚ — Escenarios Climáticos",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# =========================================================
# HELPERS
# =========================================================
@st.cache_data(show_spinner=False)
def logo_b64(filename: str, fmt: str = "PNG", height: int = 80) -> str:
    path = os.path.join(ASSETS_DIR, filename)
    img  = Image.open(path)
    ratio = height / img.height
    img  = img.resize((int(img.width * ratio), height), Image.LANCZOS)
    buf  = io.BytesIO()
    if fmt == "PNG":
        img.save(buf, format="PNG", optimize=True)
    else:
        img.save(buf, format="JPEG", quality=82, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()

@st.cache_data(show_spinner=False)
def load_geojson_str(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def geojson_path(kind: str, variable: str = "", estacion: str = "",
                 periodo: str = "2036_2065", imc_tipo: str = "") -> str | None:
    if kind == "climate":
        est = "anual" if estacion == "anual" else estacion.upper()
        fname = f"distritos_cambio_{variable}_{est}_cmip6_{periodo}_5km.geojson"
    elif kind == "imc":
        fname = f"indice_multipeligro_{imc_tipo}_{periodo}.geojson"
    else:
        fname = f"{kind}.geojson"
    p = os.path.join(DATA_DIR, fname)
    return p if os.path.exists(p) else None

# =========================================================
# SIDEBAR — controles Streamlit (fuera del iframe)
# =========================================================
st.markdown(
    "<style>section[data-testid='stSidebar']{display:none!important}</style>",
    unsafe_allow_html=True,
)

# Estado en session_state
if "variable"  not in st.session_state: st.session_state.variable  = "pr"
if "estacion"  not in st.session_state: st.session_state.estacion  = "anual"
if "imc_on"    not in st.session_state: st.session_state.imc_on    = False
if "imc_tipo"  not in st.session_state: st.session_state.imc_tipo  = "agricola"
if "ref_layer" not in st.session_state: st.session_state.ref_layer = "ninguna"

# =========================================================
# CARGA DE DATOS (solo lo activo)
# =========================================================
periodo = "2036_2065"

if st.session_state.imc_on:
    p = geojson_path("imc", imc_tipo=st.session_state.imc_tipo, periodo=periodo)
    climate_json = "null"
    imc_json     = load_geojson_str(p) if p else "null"
else:
    p = geojson_path("climate",
                     variable=st.session_state.variable,
                     estacion=st.session_state.estacion,
                     periodo=periodo)
    climate_json = load_geojson_str(p) if p else "null"
    imc_json     = "null"

ref = st.session_state.ref_layer
ref_json = "null"
if ref != "ninguna":
    rp = geojson_path(ref)
    if rp:
        ref_json = load_geojson_str(rp)

# =========================================================
# LOGOS
# =========================================================
logo_senamhi = logo_b64("logo_senamhi.png", "PNG", height=80)
logo_minam   = logo_b64("logo_minam.jpg",   "JPEG", height=80)

# =========================================================
# CSS (standalone)
# =========================================================
css_path = os.path.join(ASSETS_DIR, "style_standalone.css")
with open(css_path, "r", encoding="utf-8") as f:
    CSS = f.read()

# Ajustes para que funcione dentro del iframe de Streamlit
CSS += """
html, body { height: 100% !important; overflow: hidden !important; }
.layout    { height: calc(100vh - var(--navbar-h) - var(--footer-h)) !important; }
"""

# =========================================================
# JS — app.js con rutas de data corregidas a datos inline
# =========================================================
# El app.js original usa fetch() a rutas relativas que no funcionan
# dentro del iframe de Streamlit.  Aquí lo reemplazamos por funciones
# que leen los datos que Python ya inyectó como variables JS globales.

APP_JS = """
"use strict";

// ─── Paletas ──────────────────────────────────────────────
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
  "Muy Alto": "#d7191c", "Alto": "#f7941d",
  "Medio":    "#f1dd00", "Bajo": "#9bc68b",
};

// ─── Estado ───────────────────────────────────────────────
const state = {
  variable:  INIT_VARIABLE,
  estacion:  INIT_ESTACION,
  imcActive: INIT_IMC_ON,
  imcTipo:   INIT_IMC_TIPO,
  refLayer:  INIT_REF_LAYER,
};

let climateLayer = null;
let imcLayer     = null;
let refGeoLayer  = null;
let searchMarker = null;

// ─── Mapa ─────────────────────────────────────────────────
const map = L.map("map", {
  center: [-9, -75], zoom: 5,
  zoomControl: false, attributionControl: false,
});
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18 }).addTo(map);

document.getElementById("zoomIn").addEventListener("click",  () => map.zoomIn());
document.getElementById("zoomOut").addEventListener("click", () => map.zoomOut());

const loader = document.getElementById("mapLoader");
function showLoader() { loader.style.display = "flex"; }
function hideLoader() { loader.style.display = "none"; }

// ─── Helpers color ────────────────────────────────────────
function getClimateColor(value, variable) {
  if (value == null) return "#cccccc";
  const v = parseFloat(value);
  if (isNaN(v)) return "#cccccc";
  const bins   = variable === "pr" ? PREC_BINS   : TEMP_BINS;
  const colors = variable === "pr" ? PREC_COLORS : TEMP_COLORS;
  for (let i = 0; i < bins.length - 1; i++)
    if (v > bins[i] && v <= bins[i+1]) return colors[i];
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
function seasonLabel(v) {
  return { anual:"Anual", DEF:"Verano (DJF)", MAM:"Otoño (MAM)",
           JJA:"Invierno (JJA)", SON:"Primavera (SON)" }[v] || v;
}

// ─── Tooltip / popup ──────────────────────────────────────
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

// ─── Panel de información ─────────────────────────────────
function showInfoPanel(props, variable, isImc) {
  const panel = document.getElementById("infoPanel");
  const body  = document.getElementById("infoPanelBody");
  const distrito = props.DISTRITO || props.DEPARTAMEN || props.PROVINCIA || props.NOMBRE || "—";
  const valor    = props.valor != null ? props.valor : null;
  const rows = [];
  rows.push({ k:"Distrito", v: distrito });
  if (isImc) {
    const lbl = valor != null ? imcLabel(valor) : "Sin dato";
    const fmt = valor != null ? parseFloat(valor).toFixed(3) : "—";
    rows.push({ k:"Tipo IMC",  v: state.imcTipo.charAt(0).toUpperCase()+state.imcTipo.slice(1) });
    rows.push({ k:"Valor IMC", v: fmt, highlight: true });
    rows.push({ k:"Categoría", v: lbl });
  } else {
    const varNames = { pr:"Precipitación", tasmax:"T° Máxima", tasmin:"T° Mínima" };
    const unit = variable === "pr" ? "%" : "°C";
    const fmt  = valor != null ? `${parseFloat(valor).toFixed(1)} ${unit}` : "Sin dato";
    rows.push({ k:"Variable", v: varNames[variable] || variable });
    rows.push({ k:"Estación", v: seasonLabel(state.estacion) });
    rows.push({ k:"Período",  v: "2036–2065" });
    rows.push({ k:"Valor",    v: fmt, highlight: true });
  }
  body.innerHTML = rows.map(r =>
    `<div class="info-row">
      <span class="info-key">${r.k}</span>
      <span class="info-val${r.highlight?" highlight":"}">${r.v}</span>
    </div>`
  ).join("");
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
  const title  = isPrec ? "Δ Precipitación (%)" : "Δ Temperatura (°C)";
  const items  = colors.map((c,i) => {
    const lo = bins[i], hi = bins[i+1];
    const label = lo <= -900 ? `≤ ${hi}` : hi >= 900 ? `≥ ${lo}` : `${lo} – ${hi}`;
    return `<div class="legend-item">
      <span class="legend-swatch" style="background:${c}"></span>
      <span class="legend-label">${label} ${unit}</span>
    </div>`;
  }).join("");
  el.innerHTML = `<div class="legend-title">${title}</div>${items}`;
}
function buildImcLegend() {
  const el = document.getElementById("mapLegend");
  const items = [
    ["Muy Alto (≥ 0.75)","#d7191c"],["Alto (0.50–0.75)","#f7941d"],
    ["Medio (0.25–0.50)","#f1dd00"],["Bajo (< 0.25)","#9bc68b"],
  ].map(([lbl,c]) =>
    `<div class="legend-item">
      <span class="legend-swatch" style="background:${c}"></span>
      <span class="legend-label">${lbl}</span>
    </div>`
  ).join("");
  el.innerHTML = `<div class="legend-title">Índice Multipeligro (IMC)</div>${items}`;
}

// ─── Renderizar capas desde datos inline ──────────────────
function renderClimateLayer() {
  if (climateLayer) { map.removeLayer(climateLayer); climateLayer = null; }
  if (CLIMATE_DATA === null) {
    document.getElementById("mapLegend").innerHTML = "";
    return;
  }
  climateLayer = L.geoJSON(CLIMATE_DATA, {
    style: feat => ({
      fillColor: getClimateColor(feat.properties.valor, state.variable),
      fillOpacity: 0.85, color: "#666", weight: 0.4,
    }),
    onEachFeature: (feat, layer) => {
      layer.on({
        mouseover(e) {
          e.target.setStyle({ weight:1.5, color:"#111", fillOpacity:0.95 });
          layer.bindTooltip(buildTooltip(feat.properties, state.variable, false), { sticky:true }).openTooltip();
        },
        mouseout(e)  { climateLayer.resetStyle(e.target); },
        click()      { showInfoPanel(feat.properties, state.variable, false); },
      });
    },
  }).addTo(map);
  buildClimateLegend(state.variable);
}

function renderImcLayer() {
  if (imcLayer) { map.removeLayer(imcLayer); imcLayer = null; }
  if (IMC_DATA === null) {
    document.getElementById("mapLegend").innerHTML = "";
    return;
  }
  imcLayer = L.geoJSON(IMC_DATA, {
    style: feat => ({
      fillColor: getImcColor(feat.properties.valor),
      fillOpacity: 0.82, color: "#5e005e", weight: 0.5,
    }),
    onEachFeature: (feat, layer) => {
      layer.on({
        mouseover(e) {
          e.target.setStyle({ weight:1.5, color:"#111", fillOpacity:0.95 });
          layer.bindTooltip(buildTooltip(feat.properties, null, true), { sticky:true }).openTooltip();
        },
        mouseout(e) { imcLayer.resetStyle(e.target); },
        click()     { showInfoPanel(feat.properties, null, true); },
      });
    },
  }).addTo(map);
  buildImcLegend();
}

function renderRefLayer() {
  if (refGeoLayer) { map.removeLayer(refGeoLayer); refGeoLayer = null; }
  if (REF_DATA === null) return;
  refGeoLayer = L.geoJSON(REF_DATA, {
    style: { color:"#000", weight:0.9, fillOpacity:0 },
  }).addTo(map);
}

// ─── Comunicación con Streamlit via query params ──────────
// Actualiza la URL del padre con el nuevo parámetro, lo que
// dispara un rerun de Streamlit que lee el query param y
// sirve el HTML con los nuevos datos ya inlineados.
function notifyStreamlit(key, value) {
  try {
    const url = new URL(window.parent.location.href);
    url.searchParams.set(key, value);
    window.parent.history.pushState({}, "", url.toString());
    // Forzar rerun de Streamlit
    window.parent.location.href = url.toString();
  } catch(e) {
    // Fallback: recargar con query string
    const base = window.parent.location.origin + window.parent.location.pathname;
    const params = new URLSearchParams(window.parent.location.search);
    params.set(key, value);
    window.parent.location.href = base + "?" + params.toString();
  }
}

// ─── Inicializar controles con estado actual ──────────────
function initControls() {
  // Variable
  document.querySelectorAll("#varGroup .radio-card").forEach(card => {
    if (card.dataset.value === state.variable) card.classList.add("active");
    else card.classList.remove("active");
  });
  // Estación
  document.querySelectorAll(".btn-season").forEach(btn => {
    if (btn.dataset.value === state.estacion) btn.classList.add("active");
    else btn.classList.remove("active");
  });
  // IMC
  const toggle = document.getElementById("imcToggle");
  toggle.checked = state.imcActive;
  document.getElementById("imcTypeGroup").style.display = state.imcActive ? "flex" : "none";
  document.querySelectorAll("#imcTypeGroup .radio-card").forEach(card => {
    if (card.dataset.value === state.imcTipo) card.classList.add("active");
    else card.classList.remove("active");
  });
  // Ref layer
  document.querySelectorAll("#refLayerGroup .radio-card").forEach(card => {
    if (card.dataset.value === state.refLayer) card.classList.add("active");
    else card.classList.remove("active");
  });
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

// ─── Eventos de controles ─────────────────────────────────
document.querySelectorAll(".btn-season").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".btn-season").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    state.estacion = btn.dataset.value;
    notifyStreamlit("estacion", state.estacion);
  });
});

setupRadioGroup("varGroup", value => {
  state.variable = value;
  notifyStreamlit("variable", value);
});

setupRadioGroup("refLayerGroup", value => {
  state.refLayer = value;
  notifyStreamlit("ref_layer", value);
});

const imcToggle    = document.getElementById("imcToggle");
const imcTypeGroup = document.getElementById("imcTypeGroup");
imcToggle.addEventListener("change", () => {
  state.imcActive = imcToggle.checked;
  imcTypeGroup.style.display = state.imcActive ? "flex" : "none";
  notifyStreamlit("imc_on", state.imcActive);
});

setupRadioGroup("imcTypeGroup", value => {
  state.imcTipo = value;
  if (state.imcActive) notifyStreamlit("imc_tipo", value);
});

// ─── Búsqueda por coordenadas ─────────────────────────────
document.getElementById("btnBuscar").addEventListener("click", () => {
  const lat = parseFloat(document.getElementById("latInput").value.replace(",","."));
  const lon = parseFloat(document.getElementById("lonInput").value.replace(",","."));
  if (isNaN(lat)||isNaN(lon)||lat<-90||lat>90||lon<-180||lon>180) {
    alert("Coordenadas no válidas. Latitud: −90 a 90 · Longitud: −180 a 180");
    return;
  }
  if (searchMarker) { map.removeLayer(searchMarker); searchMarker = null; }
  map.setView([lat,lon], 11, { animate:true });
  const icon = L.divIcon({
    className:"", html:'<div class="search-marker-icon"></div>',
    iconSize:[18,18], iconAnchor:[9,9],
  });
  searchMarker = L.marker([lat,lon],{icon}).addTo(map)
    .bindTooltip(`${lat.toFixed(5)}, ${lon.toFixed(5)}`, { permanent:false });
});

// ─── Sidebar toggle ───────────────────────────────────────
document.getElementById("sidebarToggle").addEventListener("click", () => {
  document.getElementById("sidebar").classList.toggle("collapsed");
});

// ─── Recibir mensajes de Streamlit ────────────────────────
window.addEventListener("message", (e) => {
  if (e.data && e.data.type === "streamlit:render") {
    // Streamlit re-renderizó; los datos ya están en las variables globales
    // No hace falta hacer nada: el HTML completo se regeneró
  }
});

// ─── Inicialización ───────────────────────────────────────
initControls();
if (state.imcActive) {
  renderImcLayer();
} else {
  renderClimateLayer();
}
renderRefLayer();
hideLoader();
"""

# =========================================================
# HTML COMPLETO
# =========================================================
def build_html(
    css: str,
    app_js: str,
    climate_json: str,
    imc_json: str,
    ref_json: str,
    logo_senamhi_b64: str,
    logo_minam_b64: str,
    state_variable: str,
    state_estacion: str,
    state_imc_on: bool,
    state_imc_tipo: str,
    state_ref_layer: str,
) -> str:
    imc_on_js  = "true" if state_imc_on else "false"
    imc_tipo_js = json.dumps(state_imc_tipo)
    variable_js = json.dumps(state_variable)
    estacion_js = json.dumps(state_estacion)
    ref_layer_js = json.dumps(state_ref_layer)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <link rel="preconnect" href="https://fonts.googleapis.com"/>
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet"/>
  <style>{css}</style>
</head>
<body>

  <header class="navbar">
    <div class="navbar-brand">
      <img src="data:image/png;base64,{logo_senamhi_b64}" alt="SENAMHI" class="navbar-logo"/>
      <div class="navbar-titles">
        <span class="navbar-title">SENAMHI PERÚ</span>
        <span class="navbar-subtitle">Escenarios Climáticos · CMIP6 · 2036–2065</span>
      </div>
    </div>
    <div class="navbar-right">
      <img src="data:image/jpeg;base64,{logo_minam_b64}" alt="MINAM" class="navbar-logo-minam"/>
      <span class="navbar-badge">BETA</span>
    </div>
  </header>

  <div class="layout">
    <aside class="sidebar" id="sidebar">
      <button class="sidebar-toggle" id="sidebarToggle" title="Ocultar panel">&#9776;</button>

      <div class="sidebar-section">
        <div class="section-label">Variable climática</div>
        <div class="radio-group" id="varGroup">
          <label class="radio-card" data-value="pr">
            <span class="radio-dot"></span>
            <div><span class="radio-title">Precipitación</span>
                 <span class="radio-desc">Cambio relativo (%)</span></div>
          </label>
          <label class="radio-card" data-value="tasmax">
            <span class="radio-dot"></span>
            <div><span class="radio-title">T° Máxima</span>
                 <span class="radio-desc">Cambio proyectado (°C)</span></div>
          </label>
          <label class="radio-card" data-value="tasmin">
            <span class="radio-dot"></span>
            <div><span class="radio-title">T° Mínima</span>
                 <span class="radio-desc">Cambio proyectado (°C)</span></div>
          </label>
        </div>
      </div>

      <div class="sidebar-section">
        <div class="section-label">Estación del año</div>
        <div class="btn-group" id="seasonGroup">
          <button class="btn-season" data-value="anual">Anual</button>
          <button class="btn-season" data-value="DEF">Verano</button>
          <button class="btn-season" data-value="MAM">Otoño</button>
          <button class="btn-season" data-value="JJA">Invierno</button>
          <button class="btn-season" data-value="SON">Primavera</button>
        </div>
      </div>

      <div class="sidebar-section">
        <div class="section-label">Índice Multipeligro Climático</div>
        <label class="toggle-switch">
          <input type="checkbox" id="imcToggle"/>
          <span class="toggle-slider"></span>
          <span class="toggle-label">Activar IMC</span>
        </label>
        <div id="imcTypeGroup" class="radio-group" style="display:none; margin-top:10px;">
          <label class="radio-card" data-value="agricola">
            <span class="radio-dot"></span><div><span class="radio-title">Agricultura</span></div>
          </label>
          <label class="radio-card" data-value="electrica">
            <span class="radio-dot"></span><div><span class="radio-title">Electricidad</span></div>
          </label>
          <label class="radio-card" data-value="vivienda">
            <span class="radio-dot"></span><div><span class="radio-title">Vivienda</span></div>
          </label>
          <label class="radio-card" data-value="mineria">
            <span class="radio-dot"></span><div><span class="radio-title">Minería</span></div>
          </label>
          <label class="radio-card" data-value="salud">
            <span class="radio-dot"></span><div><span class="radio-title">Salud</span></div>
          </label>
          <label class="radio-card" data-value="cultura">
            <span class="radio-dot"></span><div><span class="radio-title">Cultura</span></div>
          </label>
        </div>
      </div>

      <div class="sidebar-section">
        <div class="section-label">Capa de referencia</div>
        <div class="radio-group" id="refLayerGroup">
          <label class="radio-card" data-value="ninguna">
            <span class="radio-dot"></span><div><span class="radio-title">Ninguna</span></div>
          </label>
          <label class="radio-card" data-value="departamentos">
            <span class="radio-dot"></span>
            <div><span class="radio-title">Departamentos</span>
                 <span class="radio-desc">25 regiones</span></div>
          </label>
          <label class="radio-card" data-value="provincias">
            <span class="radio-dot"></span>
            <div><span class="radio-title">Provincias</span>
                 <span class="radio-desc">196 provincias</span></div>
          </label>
          <label class="radio-card" data-value="cuencas">
            <span class="radio-dot"></span>
            <div><span class="radio-title">Cuencas</span>
                 <span class="radio-desc">231 unidades hidrográficas</span></div>
          </label>
        </div>
      </div>

      <div class="sidebar-section">
        <div class="section-label">Buscar por coordenadas</div>
        <div class="coord-inputs">
          <div class="input-group">
            <label for="latInput">Latitud</label>
            <input type="text" id="latInput" placeholder="-12.0464" value="-12.0464"/>
          </div>
          <div class="input-group">
            <label for="lonInput">Longitud</label>
            <input type="text" id="lonInput" placeholder="-77.0428" value="-77.0428"/>
          </div>
        </div>
        <button class="btn-buscar" id="btnBuscar">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          Buscar ubicación
        </button>
      </div>

      <div class="sidebar-section">
        <div class="section-label">Período de proyección</div>
        <div class="periodo-badge">2036 – 2065 <span>·</span> CMIP6</div>
      </div>
    </aside>

    <main class="map-container">
      <div class="map-zoom-ctrl" id="zoomCtrl">
        <button id="zoomIn"  title="Acercar">+</button>
        <button id="zoomOut" title="Alejar">−</button>
      </div>
      <div class="map-info-panel" id="infoPanel" style="display:none;">
        <div class="info-panel-header">
          <span>Información del punto</span>
          <button id="closeInfoPanel">✕</button>
        </div>
        <div class="info-panel-body" id="infoPanelBody"></div>
      </div>
      <div class="map-legend" id="mapLegend"></div>
      <div class="map-loader" id="mapLoader">
        <div class="spinner"></div>
        <span>Cargando datos...</span>
      </div>
      <div id="map"></div>
    </main>
  </div>

  <footer class="footer">
    <div class="footer-left">© 2025 SENAMHI — Servicio Nacional de Meteorología e Hidrología del Perú</div>
    <div class="footer-right">Escenarios CMIP6 · Resolución 5 km · Período 2036–2065</div>
  </footer>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    // ── Datos inyectados por Python ──────────────────────
    const CLIMATE_DATA   = {climate_json};
    const IMC_DATA       = {imc_json};
    const REF_DATA       = {ref_json};

    // ── Estado inicial ───────────────────────────────────
    const INIT_VARIABLE  = {variable_js};
    const INIT_ESTACION  = {estacion_js};
    const INIT_IMC_ON    = {imc_on_js};
    const INIT_IMC_TIPO  = {imc_tipo_js};
    const INIT_REF_LAYER = {ref_layer_js};
  </script>
  <script>{app_js}</script>
</body>
</html>"""

# =========================================================
# RECIBIR MENSAJES DEL COMPONENTE (postMessage → query_params)
# Streamlit no tiene forma nativa de recibir postMessage desde
# un componente html(). El truco: usamos st.query_params para
# que el JS redirija con ?key=value y Streamlit los lea.
# Pero la solución más limpia es usar st.components.v1.html con
# bidireccionalidad via st_javascript — aquí usamos el patrón
# de query_params que funciona en Streamlit Cloud sin plugins.
# =========================================================

# Leer cambios enviados vía query_params por el JS
qp = st.query_params
if "variable"  in qp: st.session_state.variable  = qp["variable"]
if "estacion"  in qp: st.session_state.estacion  = qp["estacion"]
if "imc_on"    in qp: st.session_state.imc_on    = qp["imc_on"] == "true"
if "imc_tipo"  in qp: st.session_state.imc_tipo  = qp["imc_tipo"]
if "ref_layer" in qp: st.session_state.ref_layer = qp["ref_layer"]

# =========================================================
# RENDERIZAR
# =========================================================
html_content = build_html(
    css=CSS,
    app_js=APP_JS,
    climate_json=climate_json,
    imc_json=imc_json,
    ref_json=ref_json,
    logo_senamhi_b64=logo_senamhi,
    logo_minam_b64=logo_minam,
    state_variable=st.session_state.variable,
    state_estacion=st.session_state.estacion,
    state_imc_on=st.session_state.imc_on,
    state_imc_tipo=st.session_state.imc_tipo,
    state_ref_layer=st.session_state.ref_layer,
)

# Ocultar todo el chrome de Streamlit (menú, header, padding)
st.markdown("""
<style>
  #MainMenu, header[data-testid="stHeader"], footer { display:none !important; }
  .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
  [data-testid="stAppViewContainer"] { padding: 0 !important; }
</style>
""", unsafe_allow_html=True)

st.components.v1.html(html_content, height=800, scrolling=False)
