/**
 * map_controls.js
 * Se inyecta dentro del HTML del mapa Folium para:
 *  1. Ocultar los controles nativos de Leaflet (zoom +/−, atribución, LayerControl)
 *  2. Inyectar estilos limpios dentro del iframe del mapa
 */

(function () {
    "use strict";

    function hideLeafletControls() {
        var style = document.createElement("style");
        style.textContent = [
            /* botones zoom +/- */
            ".leaflet-control-zoom { display: none !important; }",
            /* atribución "Leaflet | © OpenStreetMap contributors" */
            ".leaflet-control-attribution { display: none !important; }",
            /* control de capas nativo de Leaflet (lo reemplazamos con los botones del sidebar) */
            ".leaflet-control-layers { display: none !important; }",
            /* escala opcional: la dejamos visible pero la posicionamos limpio */
            ".leaflet-control-scale {",
            "  bottom: 8px !important;",
            "  right: 12px !important;",
            "  left: auto !important;",
            "  font-family: 'Inter', Arial, sans-serif;",
            "  font-size: 10px;",
            "  border-color: #999;",
            "}",
            /* Fondo del mapa sin marco extra */
            ".leaflet-container {",
            "  background: #e8eef4;",
            "  font-family: 'Inter', Arial, sans-serif;",
            "}",
            /* Tooltips más limpios */
            ".leaflet-tooltip {",
            "  border-radius: 6px !important;",
            "  border: 1px solid #ccc !important;",
            "  box-shadow: 0 2px 8px rgba(0,0,0,0.18) !important;",
            "  font-family: 'Inter', Arial, sans-serif !important;",
            "  font-size: 12px !important;",
            "  padding: 6px 10px !important;",
            "}",
            /* Popups más limpios */
            ".leaflet-popup-content-wrapper {",
            "  border-radius: 8px !important;",
            "  box-shadow: 0 4px 16px rgba(0,0,0,0.2) !important;",
            "  font-family: 'Inter', Arial, sans-serif !important;",
            "}",
            ".leaflet-popup-tip { display: none !important; }",
        ].join("\n");
        document.head.appendChild(style);
    }

    /* Ejecutar tan pronto el DOM esté listo */
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", hideLeafletControls);
    } else {
        hideLeafletControls();
    }

})();
