/**
 * Team 13 API Client — Places, Events, Routes, Emergency.
 * Appends format=json to all requests. CSRF helper for POST (rating).
 */

const API_BASE = window.TEAM13_API_BASE || '';

/**
 * Get CSRF token from cookie (Django's csrftoken cookie).
 * @returns {string|null}
 */
function getCsrfToken() {
  const name = 'csrftoken';
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === name + '=') {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

/**
 * Fetch JSON from a team13 endpoint. Automatically appends format=json.
 * @param {string} endpoint - Path without base, e.g. '/team13/places/' or 'places/'
 * @param {Record<string, string>} [params] - Optional query params (merged with format=json)
 * @returns {Promise<object>} Parsed JSON
 */
async function fetchData(endpoint, params = {}) {
  const url = new URL(endpoint.startsWith('http') ? endpoint : API_BASE + endpoint.replace(/^\//, ''), window.location.origin);
  const query = { format: 'json', ...params };
  Object.keys(query).forEach(key => {
    if (query[key] != null && query[key] !== '') url.searchParams.set(key, query[key]);
  });
  const res = await fetch(url.toString(), {
    method: 'GET',
    headers: { Accept: 'application/json' },
    credentials: 'same-origin',
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  return res.json();
}

/**
 * POST for rating (place or event). Sends CSRF via header and form body.
 * @param {string} url - Full URL, e.g. /team13/places/<uuid>/rate/
 * @param {{ rating: number }} data - e.g. { rating: 5 }
 * @returns {Promise<Response>}
 */
async function postRating(url, data) {
  const csrf = getCsrfToken();
  const body = new URLSearchParams(data);
  if (csrf) body.append('csrfmiddlewaretoken', csrf);
  const fullUrl = url.startsWith('http') ? url : (API_BASE ? API_BASE.replace(/\/$/, '') + url : url);
  return fetch(fullUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': csrf || '',
      'Accept': 'application/json',
    },
    body: body.toString(),
    credentials: 'same-origin',
  });
}

// Convenience API names aligned with backend
const api = {
  places: (params) => fetchData('/team13/places/', params),
  placeDetail: (placeId) => fetchData(`/team13/places/${placeId}/`),
  placeRate: (placeId, rating) => postRating(`/team13/places/${placeId}/rate/`, { rating }),
  events: () => fetchData('/team13/events/'),
  eventDetail: (eventId) => fetchData(`/team13/events/${eventId}/`),
  eventRate: (eventId, rating) => postRating(`/team13/events/${eventId}/rate/`, { rating }),
  routes: (sourcePlaceId, destinationPlaceId, travelMode = 'car') =>
    fetchData('/team13/routes/', {
      source_place_id: sourcePlaceId,
      destination_place_id: destinationPlaceId,
      travel_mode: travelMode,
    }),
  emergency: (lat, lon, limit = 10) =>
    fetchData('/team13/emergency/', { lat: String(lat), lon: String(lon), limit: String(limit) }),
};

/**
 * Load places and events from backend for map and sidebar.
 * GET requests; no CSRF required.
 * @returns {Promise<{ places: Array, events: Array }>}
 */
async function loadMapData() {
  const base = window.location.origin + (window.TEAM13_API_BASE || '');
  const [placesRes, eventsRes] = await Promise.all([
    fetch(`${base}/team13/places/?format=json`, { method: 'GET', headers: { Accept: 'application/json' }, credentials: 'same-origin' }),
    fetch(`${base}/team13/events/?format=json`, { method: 'GET', headers: { Accept: 'application/json' }, credentials: 'same-origin' }),
  ]);
  if (!placesRes.ok) throw new Error('Places fetch failed: ' + placesRes.status);
  if (!eventsRes.ok) throw new Error('Events fetch failed: ' + eventsRes.status);
  const placesData = await placesRes.json();
  const eventsData = await eventsRes.json();
  return {
    places: placesData.places || [],
    events: eventsData.events || [],
  };
}

const COLOR_DRIVING = '#1b4332';
const COLOR_WALKING = '#40916c';
const COLOR_BICYCLE = '#2d6a4f';
const COLOR_TRANSIT = '#1b4332';
const MAPIR_ROUTES_BASE = 'https://map.ir/routes';
const MAPIR_SEARCH_POI = 'https://map.ir/search/v2/poi';
const MAPIR_REVERSE = 'https://map.ir/reverse';

/**
 * Map.ir Routing API reference (مستندات مسیریابی مپ):
 * - Service: https://help.map.ir/route-api/
 * - Endpoints (base MAPIR_ROUTES_BASE):
 *   - Car: route/v1/driving/{coordinates}
 *   - Foot: foot/v1/driving/{coordinates}
 *   - Bicycle: bicycle/v1/driving/{coordinates}
 *   - Traffic/zojofard: tarh/v1/driving, zojofard/v1/driving
 * - Input: coordinates = "lon,lat;lon,lat" (path), x-api-key (header), steps=true, alternatives=false, geometries=polyline|polyline6|geojson
 * - Output: routes[].distance (m), routes[].duration (s), routes[].legs[].steps (maneuver locations), routes[].geometry (encoded polyline if requested)
 * - Web SDK examples: draw-route-api, advanced-routing, color-route
 */

/**
 * Decode route geometry from Map.ir response using polyline.js.
 * 1. Prefer data.routes[0].geometry (compressed string) → polyline.decode(geometry) with precision 5 or 6.
 * 2. Fallback: geometry.coordinates or legs/steps polyline arrays.
 * @returns {Array<[number, number]>} [[lat, lng], ...]
 */
function decodeRouteGeometry(data, oLat, oLng, destLat, destLng) {
  const route = data.route || (data.routes && data.routes[0]);
  if (!route) return [[oLat, oLng], [destLat, destLng]];

  const geom = route.geometry;
  if (typeof geom === 'string') {
    if (typeof polyline !== 'undefined' && polyline.decode) {
      try {
        const decoded = polyline.decode(geom, 5);
        if (decoded && decoded.length >= 2) return decoded;
      } catch (e) {}
      try {
        const decoded = polyline.decode(geom, 6);
        if (decoded && decoded.length >= 2) return decoded;
      } catch (e) {}
      return polyline.decode(geom);
    }
  }
  if (geom && Array.isArray(geom.coordinates)) {
    return geom.coordinates.map((c) => (Array.isArray(c) ? [c[1], c[0]] : [c.lat ?? c[1], c.lng ?? c[0]]));
  }

  const latlngs = [];
  if (route.legs && Array.isArray(route.legs)) {
    route.legs.forEach((leg) => {
      if (leg.steps && Array.isArray(leg.steps)) {
        leg.steps.forEach((step) => {
          if (step.polyline && Array.isArray(step.polyline)) {
            step.polyline.forEach((c) => {
              if (Array.isArray(c) && c.length >= 2) latlngs.push([c[1], c[0]]);
            });
          }
        });
      }
    });
  }
  if (latlngs.length >= 2) return latlngs;
  if (data.waypoints && Array.isArray(data.waypoints)) {
    data.waypoints.forEach((p) => {
      if (Array.isArray(p)) latlngs.push([p[1], p[0]]);
      else if (p && typeof p.lat !== 'undefined') latlngs.push([p.lat, p.lng]);
    });
  }
  if (latlngs.length >= 2) return latlngs;
  return [[oLat, oLng], [destLat, destLng]];
}

function parseRouteDistance(data) {
  const route = data.route || (data.routes && data.routes[0]);
  if (route && typeof route.distance === 'number') return route.distance / 1000;
  if (route && route.legs && route.legs.length) {
    let d = 0;
    route.legs.forEach((leg) => { d += leg.distance || 0; });
    return d / 1000;
  }
  return null;
}

/**
 * Pull duration (seconds) from the specific route object returned by Map.ir.
 * Checks route.duration, then sum of route.legs[].duration.
 */
function parseRouteDuration(data) {
  const route = data.route || (data.routes && data.routes[0]);
  if (!route) return null;
  if (typeof route.duration === 'number') return route.duration;
  if (route.legs && route.legs.length) {
    let d = 0;
    route.legs.forEach((leg) => { d += leg.duration || 0; });
    return d;
  }
  return null;
}

/** Walking speed for fallback ETA when API does not return walking duration: ~5 km/h */
const WALKING_SPEED_KMH = 5;

/** Safety cap: max points for interpolated route to avoid browser crash on very long routes (e.g. >500km). */
const MAX_ROUTE_POINTS = 50000;

/**
 * Haversine distance between two [lat, lng] points in meters.
 * @param {number} lat1
 * @param {number} lng1
 * @param {number} lat2
 * @param {number} lng2
 * @returns {number}
 */
function haversineDistanceMeters(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLng = ((lng2 - lng1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Linear interpolation (LERP): break segments longer than maxDistanceInMeters into sub-segments with "ghost points"
 * so the line hugs the road at ultra-high resolution. Safety cap at MAX_ROUTE_POINTS to avoid crash on very long routes.
 * @param {Array<[number, number]>} points - [lat, lng] pairs from the route
 * @param {number} maxDistanceInMeters - max length of each micro-segment (default 2 meters)
 * @returns {Array<[number, number]>}
 */
function interpolatePoints(points, maxDistanceInMeters = 2) {
  if (!points || points.length < 2 || maxDistanceInMeters <= 0) return points;
  const out = [points[0]];
  for (let i = 0; i < points.length - 1; i++) {
    if (out.length >= MAX_ROUTE_POINTS) break;
    const p1 = points[i];
    const p2 = points[i + 1];
    const lat1 = p1[0];
    const lng1 = p1[1];
    const lat2 = p2[0];
    const lng2 = p2[1];
    const distM = haversineDistanceMeters(lat1, lng1, lat2, lng2);
    if (distM <= maxDistanceInMeters) {
      out.push(p2);
      continue;
    }
    const steps = Math.ceil(distM / maxDistanceInMeters);
    const remaining = MAX_ROUTE_POINTS - out.length - 1;
    const stepsToAdd = Math.min(steps - 1, Math.max(0, remaining));
    for (let k = 1; k <= stepsToAdd; k++) {
      const t = k / steps;
      out.push([lat1 + (lat2 - lat1) * t, lng1 + (lng2 - lng1) * t]);
    }
    out.push(p2);
  }
  return out;
}

/**
 * Normalize a coordinate to [lat, lng]. Input may be [lon, lat], {lat, lng}, {lat, lon}, etc.
 * @returns {[number, number]|null}
 */
function normCoord(c) {
  if (!c) return null;
  let lat, lng;
  if (Array.isArray(c) && c.length >= 2) {
    lng = parseFloat(c[0]);
    lat = parseFloat(c[1]);
  } else if (typeof c === 'object') {
    lat = parseFloat(c.lat != null ? c.lat : c[1]);
    lng = parseFloat(c.lon != null ? c.lon : c.lng != null ? c.lng : c[0]);
  } else return null;
  if (isNaN(lat) || isNaN(lng)) return null;
  return [lat, lng];
}

/**
 * Full geometry decoding: use only data.routes[0].geometry (ignore legs/steps for drawing).
 * Map.ir uses precision 5; try 6 if offset. Fallback to start->dest line if decode fails.
 * @param {object} route - data.routes[0]
 * @param {number} startLat
 * @param {number} startLng
 * @param {number} destLat
 * @param {number} destLng
 * @returns {Array<[number, number]>}
 */
function decodeRouteGeometryOnly(route, startLat, startLng, destLat, destLng) {
  const routeGeom = route && route.geometry;
  if (typeof routeGeom === 'string' && typeof polyline !== 'undefined' && polyline.decode) {
    try {
      let fullPath = polyline.decode(routeGeom, 5);
      if (fullPath && fullPath.length >= 2) return fullPath;
    } catch (e) {}
    try {
      let fullPath = polyline.decode(routeGeom, 6);
      if (fullPath && fullPath.length >= 2) return fullPath;
    } catch (e2) {}
    try {
      let fullPath = polyline.decode(routeGeom);
      if (fullPath && fullPath.length >= 2) return fullPath;
    } catch (e3) {}
  }
  return [[startLat, startLng], [destLat, destLng]];
}

/**
 * Map.ir route path by mode: Car = route/v1/driving, Walking = foot/v1/driving, Bicycle = bicycle/v1/driving, Transit = route/v1/driving.
 * @see https://help.map.ir/documentation/websdk-docs/
 */
function getRoutePath(serviceType) {
  const mode = String(serviceType).toLowerCase();
  if (mode === 'walking') return 'foot/v1/driving';
  if (mode === 'bicycle') return 'bicycle/v1/driving';
  return 'route/v1/driving';
}

/**
 * Get user location, call Map.ir route API (driving/foot/bicycle/transit), draw L.polyline, fitBounds.
 * ETA: data.routes[0].duration (seconds) → Math.floor(duration / 60) minutes.
 * @param {{ lat: number, lng: number }} destinationCoords - Destination point
 * @param {string} serviceType - 'driving' | 'walking' | 'bicycle' | 'transit'
 * @returns {Promise<{ distanceKm: number|null, durationMinutes: number|null, serviceType: string }>}
 */
async function getMapirRoute(destinationCoords, serviceType) {
  const map = window.team13MapInstance;
  const config = window.MAPIR_CONFIG;
  if (!map || typeof L === 'undefined') throw new Error('Map not ready');
  if (!config || !config.apiKey) throw new Error('MAPIR API key not set');

  const destLat = destinationCoords && typeof destinationCoords.lat === 'number' ? destinationCoords.lat : parseFloat(destinationCoords?.lat);
  const destLng = destinationCoords && typeof destinationCoords.lng === 'number' ? destinationCoords.lng : parseFloat(destinationCoords?.lng);
  if (isNaN(destLat) || isNaN(destLng)) throw new Error('Invalid destination coordinates');

  const mode = String(serviceType).toLowerCase();
  const type = (mode === 'walking' ? 'walking' : mode === 'bicycle' ? 'bicycle' : mode === 'transit' ? 'transit' : 'driving');
  const position = await new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('Geolocation not supported'));
    navigator.geolocation.getCurrentPosition(resolve, (e) => reject(new Error(e.message || 'موقعیت یافت نشد')), { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 });
  });

  const startLat = position.coords.latitude;
  const startLng = position.coords.longitude;
  const coords = `${startLng},${startLat};${destLng},${destLat}`;
  const path = getRoutePath(serviceType);
  const url = `${MAPIR_ROUTES_BASE}/${path}/${encodeURIComponent(coords)}?steps=true&alternatives=false&geometries=polyline`;

  const res = await fetch(url, {
    method: 'GET',
    headers: { 'x-api-key': config.apiKey, Accept: 'application/json' },
  });
  if (!res.ok) throw new Error('Route request failed: ' + res.status);
  const data = await res.json();

  const distanceKm = parseRouteDistance(data);
  let durationSec = parseRouteDuration(data);
  if ((type === 'walking') && (durationSec == null || durationSec <= 0) && distanceKm != null && distanceKm > 0) {
    durationSec = (distanceKm / WALKING_SPEED_KMH) * 3600;
  }
  let durationMinutes = durationSec != null ? Math.max(1, Math.floor(durationSec / 60)) : null;
  if (type === 'transit' && durationMinutes != null) {
    durationMinutes = Math.max(1, Math.round(durationMinutes * 1.4));
  }

  const route = data.routes && data.routes[0];
  const fullPath = decodeRouteGeometryOnly(route, startLat, startLng, destLat, destLng);
  const linePoints = interpolatePoints(fullPath, 2);

  if (window.currentPath && map) map.removeLayer(window.currentPath);
  if (window.routeLayer && map) map.removeLayer(window.routeLayer);
  if (window.currentRoute && map) map.removeLayer(window.currentRoute);
  if (window.team13RouteLine && map) map.removeLayer(window.team13RouteLine);

  window.currentPath = L.polyline(linePoints, {
    color: '#40916c',
    weight: 6,
    opacity: 0.9,
    smoothFactor: 0,
    noClip: true,
    lineJoin: 'round',
    lineCap: 'round',
    pane: 'overlayPane',
  }).addTo(map);
  window.routeLayer = window.currentPath;
  window.currentRoute = window.currentPath;
  window.team13RouteLine = window.currentPath;

  map.fitBounds(window.currentPath.getBounds(), { padding: [40, 40] });

  return { distanceKm, durationMinutes, serviceType: type };
}

/**
 * Draw route between two points (no geolocation). Uses Map.ir route API with polyline geometry.
 * @param {{ lat: number, lng: number }} startCoords - Start point
 * @param {{ lat: number, lng: number }} destCoords - Destination point
 * @param {string} serviceType - 'driving' | 'walking' | 'bicycle' | 'transit'
 * @returns {Promise<{ distanceKm: number|null, durationMinutes: number|null, serviceType: string }>}
 */
async function getMapirRouteFromTo(startCoords, destCoords, serviceType) {
  const map = window.team13MapInstance;
  const config = window.MAPIR_CONFIG;
  if (!map || typeof L === 'undefined') throw new Error('Map not ready');
  if (!config || !config.apiKey) throw new Error('MAPIR API key not set');

  const startLat = startCoords && typeof startCoords.lat === 'number' ? startCoords.lat : parseFloat(startCoords?.lat);
  const startLng = startCoords && typeof startCoords.lng === 'number' ? startCoords.lng : parseFloat(startCoords?.lng);
  const destLat = destCoords && typeof destCoords.lat === 'number' ? destCoords.lat : parseFloat(destCoords?.lat);
  const destLng = destCoords && typeof destCoords.lng === 'number' ? destCoords.lng : parseFloat(destCoords?.lng);
  if (isNaN(startLat) || isNaN(startLng) || isNaN(destLat) || isNaN(destLng)) throw new Error('Invalid start or destination coordinates');

  const mode = String(serviceType).toLowerCase();
  const type = (mode === 'walking' ? 'walking' : mode === 'bicycle' ? 'bicycle' : mode === 'transit' ? 'transit' : 'driving');
  const coords = `${startLng},${startLat};${destLng},${destLat}`;
  const path = getRoutePath(serviceType);
  const url = `${MAPIR_ROUTES_BASE}/${path}/${encodeURIComponent(coords)}?steps=true&alternatives=false&geometries=polyline`;

  const res = await fetch(url, {
    method: 'GET',
    headers: { 'x-api-key': config.apiKey, Accept: 'application/json' },
  });
  if (!res.ok) throw new Error('Route request failed: ' + res.status);
  const data = await res.json();

  const distanceKm = parseRouteDistance(data);
  let durationSec = parseRouteDuration(data);
  if ((type === 'walking') && (durationSec == null || durationSec <= 0) && distanceKm != null && distanceKm > 0) {
    durationSec = (distanceKm / WALKING_SPEED_KMH) * 3600;
  }
  let durationMinutes = durationSec != null ? Math.max(1, Math.floor(durationSec / 60)) : null;
  if (type === 'transit' && durationMinutes != null) {
    durationMinutes = Math.max(1, Math.round(durationMinutes * 1.4));
  }

  const route = data.routes && data.routes[0];
  const fullPath = decodeRouteGeometryOnly(route, startLat, startLng, destLat, destLng);
  const linePoints = interpolatePoints(fullPath, 2);

  if (window.currentPath && map) map.removeLayer(window.currentPath);
  if (window.routeLayer && map) map.removeLayer(window.routeLayer);
  if (window.currentRoute && map) map.removeLayer(window.currentRoute);
  if (window.team13RouteLine && map) map.removeLayer(window.team13RouteLine);

  window.currentPath = L.polyline(linePoints, {
    color: '#40916c',
    weight: 6,
    opacity: 0.9,
    smoothFactor: 0,
    noClip: true,
    lineJoin: 'round',
    lineCap: 'round',
    pane: 'overlayPane',
  }).addTo(map);
  window.routeLayer = window.currentPath;
  window.currentRoute = window.currentPath;
  window.team13RouteLine = window.currentPath;

  map.fitBounds(window.currentPath.getBounds(), { padding: [40, 40] });

  return { distanceKm, durationMinutes, serviceType: type };
}

/**
 * Reverse geocode: get Iranian address for a point (Map.ir Reverse API).
 * @see https://help.map.ir/reverse_api/
 * @param {number} lat - Latitude
 * @param {number} lon - Longitude
 * @returns {Promise<{ address: string, address_compact?: string, city?: string, province?: string, [key: string]: any }|null>}
 */
async function reverseGeocode(lat, lon) {
  const config = window.MAPIR_CONFIG;
  if (!config || !config.apiKey) return null;
  const url = `${MAPIR_REVERSE}?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`;
  const res = await fetch(url, {
    method: 'GET',
    headers: { 'x-api-key': config.apiKey, Accept: 'application/json' },
  });
  if (!res.ok) return null;
  return res.json();
}

/**
 * Get city (or province) from coordinates using Map.ir Reverse Geocode. Saves to window.currentCity.
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @returns {Promise<{ city: string, province?: string, lat: number, lng: number }|null>}
 */
async function getCityFromCoords(lat, lng) {
  const data = await reverseGeocode(lat, lng);
  if (!data) return null;
  const city = (data.city && String(data.city).trim()) || (data.province && String(data.province).trim()) || '';
  const province = (data.province && String(data.province).trim()) || '';
  const coords = data.geom && data.geom.coordinates;
  const latOut = Array.isArray(coords) && coords.length >= 2 ? parseFloat(coords[1]) : lat;
  const lngOut = Array.isArray(coords) && coords.length >= 2 ? parseFloat(coords[0]) : lng;
  if (city) {
    try {
      window.currentCity = city;
    } catch (e) {}
  }
  return city ? { city, province, lat: latOut, lng: lngOut } : null;
}

/**
 * Find nearest POI by category using Map.ir Search API (POI).
 * URL: https://map.ir/search/v2/poi?text=${category}&lat=${userLat}&lon=${userLon}
 * @param {string} category - e.g. "بیمارستان" or "آتش نشانی"
 * @returns {Promise<{ lat: number, lng: number, title?: string }|null>} First result or null
 */
async function findNearest(category) {
  const config = window.MAPIR_CONFIG;
  if (!config || !config.apiKey) return null;
  const position = await new Promise((resolve, reject) => {
    if (!navigator.geolocation) return reject(new Error('Geolocation not supported'));
    navigator.geolocation.getCurrentPosition(resolve, (e) => reject(new Error(e.message || 'موقعیت یافت نشد')), { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 });
  });
  const userLat = position.coords.latitude;
  const userLon = position.coords.longitude;
  const url = `${MAPIR_SEARCH_POI}?text=${encodeURIComponent(category)}&lat=${userLat}&lon=${userLon}`;
  const res = await fetch(url, {
    method: 'GET',
    headers: { 'x-api-key': config.apiKey, Accept: 'application/json' },
  });
  if (!res.ok) return null;
  const data = await res.json();
  const value = data.value || data;
  const list = Array.isArray(value) ? value : (value.results || value.items || []);
  const first = list[0];
  if (!first) return null;
  const lat = first.y != null ? parseFloat(first.y) : (first.lat != null ? parseFloat(first.lat) : first.geometry?.coordinates?.[1]);
  const lng = first.x != null ? parseFloat(first.x) : (first.lon != null ? parseFloat(first.lon) : first.geometry?.coordinates?.[0]);
  if (lat == null || lng == null || isNaN(lat) || isNaN(lng)) return null;
  return { lat: Number(lat), lng: Number(lng), title: first.title || first.name || category };
}

if (typeof window !== 'undefined') {
  window.Team13Api = { fetchData, getCsrfToken, postRating, api, loadMapData, getMapirRoute, getMapirRouteFromTo, findNearest, reverseGeocode, getCityFromCoords };
}
