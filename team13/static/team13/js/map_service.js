/**
 * Team 13 Map Service — Leaflet.js with Map.ir raster tile layer.
 * Center: Tehran [35.7219, 51.3347]. addMarkers() for Place and Event items.
 */

(function (global) {
  const TEHRAN_CENTER = [35.7219, 51.3347];
  const DEFAULT_ZOOM = 11;

  // Map.ir raster tile layer (Shive). Optional: set window.MAPIR_API_KEY for tile auth if required.
  function getTileLayerUrl() {
    const key = (typeof window !== 'undefined' && window.MAPIR_API_KEY) || '';
    if (key) {
      return 'https://map.ir/shive/tiles/1.0.0/Shive:Shive@EPSG:900913@png/{z}/{x}/{y}.png?x-api-key=' + encodeURIComponent(key);
    }
    // Fallback: OSM-based (no key). Replace with Map.ir URL when key is available.
    return 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  }

  let mapInstance = null;

  /**
   * Initialize Leaflet map in container element. Uses Map.ir raster tiles when API key set.
   * @param {string|HTMLElement} container - Id or DOM element
   * @param {object} [options] - { center: [lat, lng], zoom: number }
   * @returns {L.Map}
   */
  function initMap(container, options = {}) {
    const el = typeof container === 'string' ? document.getElementById(container) : container;
    if (!el) throw new Error('Map container not found');
    if (mapInstance) {
      mapInstance.remove();
      mapInstance = null;
    }
    const L = global.L;
    if (!L || !L.map) throw new Error('Leaflet (L) is required. Include Leaflet CSS and JS before this script.');

    const center = options.center || TEHRAN_CENTER;
    const zoom = options.zoom != null ? options.zoom : DEFAULT_ZOOM;
    mapInstance = L.map(el, { center, zoom });
    L.tileLayer(getTileLayerUrl(), {
      attribution: '© Map.ir © OpenStreetMap',
      maxZoom: 18,
      minZoom: 1,
    }).addTo(mapInstance);
    return mapInstance;
  }

  /**
   * Add markers for Place and/or Event items. Uses latitude/longitude from backend shape.
   * Place: { place_id, latitude, longitude, name_fa, name_en, type, ... }
   * Event: { event_id, latitude, longitude, title_fa, title_en, start_at, ... }
   * @param {Array<object>} items - List of Place or Event objects from API
   * @param {object} [options] - { placeIconUrl?, eventIconUrl?, popupTemplate?: (item) => string }
   */
  function addMarkers(items, options = {}) {
    if (!mapInstance || !global.L) return;
    const L = global.L;
    const markers = [];
    (items || []).forEach(function (item) {
      const lat = item.latitude != null ? Number(item.latitude) : null;
      const lng = item.longitude != null ? Number(item.longitude) : null;
      if (lat == null || lng == null || isNaN(lat) || isNaN(lng)) return;
      const name = item.name_fa || item.name_en || item.title_fa || item.title_en || '';
      const isEvent = 'event_id' in item;
      const icon = L.Icon.Default;
      const marker = L.marker([lat, lng], { icon }).addTo(mapInstance);
      if (name || options.popupTemplate) {
        const popupContent = options.popupTemplate ? options.popupTemplate(item) : (name || (isEvent ? 'رویداد' : 'مکان'));
        marker.bindPopup(popupContent);
      }
      markers.push(marker);
    });
    return markers;
  }

  /**
   * Clear all layers that are markers (optional helper; call before addMarkers to reset).
   */
  function clearMarkers(markerRefs) {
    if (Array.isArray(markerRefs)) markerRefs.forEach(function (m) { if (m && m.remove) m.remove(); });
  }

  function getMap() {
    return mapInstance;
  }

  const mapService = {
    TEHRAN_CENTER,
    DEFAULT_ZOOM,
    initMap,
    addMarkers,
    clearMarkers,
    getMap,
    getTileLayerUrl,
  };
  if (typeof global !== 'undefined') global.Team13Map = mapService;
})(typeof window !== 'undefined' ? window : this);
