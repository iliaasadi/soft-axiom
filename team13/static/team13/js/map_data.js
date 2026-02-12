/**
 * Team 13 — Database sync, Search (Map.ir Autocomplete), Routing & ETA, Emergency.
 * syncDatabaseLayers(): places (Sage Green) + events (distinct icon); popups with "مسیریابی به اینجا"; sidebar flyTo.
 * Search bar → Map.ir autocomplete; on select → temporary marker + zoom.
 * Routing from user location → Map.ir driving API → polyline + ETA/distance box. Loading spinner during fetch.
 * Emergency: nearest hospital (DB), nearest fire station (Map.ir search).
 */
(function () {
  var SAGE_GREEN = '#40916c';
  var EVENT_MARKER_COLOR = '#c1121f';
  var MAPIR_AUTOCOMPLETE = 'https://map.ir/search/v2/autocomplete';
  var MAPIR_ROUTE_BASE = 'https://map.ir/routes/route/v1/driving';
  var MAPIR_ETA_BASE = 'https://map.ir/eta/route/v1/driving';

  if (typeof window !== 'undefined') {
    window.allMarkers = window.allMarkers || {};
    window.currentlyShownPoiMarker = window.currentlyShownPoiMarker || null;
    window.emergencyPoiMarker = window.emergencyPoiMarker || null;
  }

  function getMap() {
    return window.team13MapInstance || null;
  }

  function getConfig() {
    return window.MAPIR_CONFIG || {};
  }

  function escapeHtml(s) {
    if (!s) return '';
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  // --- Markers ---
  function createPlaceIcon() {
    if (typeof L === 'undefined') return null;
    return L.divIcon({
      className: 'team13-place-marker',
      html: '<span style="width:24px;height:24px;background:' + SAGE_GREEN + ';border:2px solid #1b4332;border-radius:50%;display:block;box-shadow:0 2px 4px rgba(0,0,0,0.2);"></span>',
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });
  }

  function createDiscoveryPlaceIcon() {
    if (typeof L === 'undefined') return null;
    return L.divIcon({
      className: 'team13-place-marker team13-discovery-marker',
      html: '<span style="width:24px;height:24px;background:' + SAGE_GREEN + ';border:2px solid #1b4332;border-radius:50%;display:block;box-shadow:0 2px 4px rgba(0,0,0,0.2);"></span>',
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });
  }

  function createEventIcon() {
    if (typeof L === 'undefined') return null;
    return L.divIcon({
      className: 'team13-event-marker',
      html: '<span style="width:22px;height:22px;background:' + EVENT_MARKER_COLOR + ';border:2px solid #9d0208;border-radius:4px;display:block;box-shadow:0 2px 4px rgba(0,0,0,0.2);"></span>',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    });
  }

  function createSearchResultIcon() {
    if (typeof L === 'undefined') return null;
    return L.divIcon({
      className: 'team13-search-marker',
      html: '<span style="width:20px;height:20px;background:#2563eb;border:2px solid #1d4ed8;border-radius:50%;display:block;box-shadow:0 2px 6px rgba(0,0,0,0.3);"></span>',
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    });
  }

  function createSelectedPlaceIcon() {
    if (typeof L === 'undefined') return null;
    return L.divIcon({
      className: 'team13-place-marker team13-marker-selected',
      html: '<span style="width:24px;height:24px;background:' + SAGE_GREEN + ';border:2px solid #1b4332;border-radius:50%;display:block;box-shadow:0 2px 8px rgba(64,145,108,0.5);"></span>',
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });
  }

  function createSelectedEventIcon() {
    if (typeof L === 'undefined') return null;
    return L.divIcon({
      className: 'team13-event-marker team13-marker-selected',
      html: '<span style="width:22px;height:22px;background:' + SAGE_GREEN + ';border:2px solid #1b4332;border-radius:4px;display:block;box-shadow:0 2px 8px rgba(64,145,108,0.5);"></span>',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    });
  }

  function createEmergencyPoiIcon() {
    if (typeof L === 'undefined') return null;
    return L.divIcon({
      className: 'team13-emergency-poi-marker team13-marker-selected',
      html: '<span style="width:26px;height:26px;background:' + SAGE_GREEN + ';border:2px solid #1b4332;border-radius:50%;display:block;box-shadow:0 2px 10px rgba(64,145,108,0.6);"></span>',
      iconSize: [26, 26],
      iconAnchor: [13, 13],
    });
  }

  function createStartMarkerIcon() {
    if (typeof L === 'undefined') return null;
    return L.divIcon({
      className: 'team13-route-start-marker',
      html: '<span style="width:28px;height:28px;background:#22c55e;border:2px solid #1b4332;border-radius:50%;display:block;box-shadow:0 2px 8px rgba(0,0,0,0.25);font-size:12px;line-height:24px;text-align:center;color:#fff;font-weight:bold;">A</span>',
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });
  }

  function createDestMarkerIcon() {
    if (typeof L === 'undefined') return null;
    return L.divIcon({
      className: 'team13-route-dest-marker',
      html: '<span style="width:28px;height:28px;background:#dc2626;border:2px solid #991b1b;border-radius:50%;display:block;box-shadow:0 2px 8px rgba(0,0,0,0.25);font-size:12px;line-height:24px;text-align:center;color:#fff;font-weight:bold;">B</span>',
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });
  }

  /** Live user location: blue pulse marker (silent, no popup). */
  function createUserLocationIcon() {
    if (typeof L === 'undefined') return null;
    return L.divIcon({
      className: 'team13-user-location-marker',
      html: '<span class="team13-user-location-pulse"></span><span class="team13-user-location-dot"></span>',
      iconSize: [32, 32],
      iconAnchor: [16, 16],
    });
  }

  // --- Popup: Place (title, address, button "مسیریابی به اینجا") ---
  function buildPlacePopupContent(p, lat, lng) {
    var name = (p.name_fa || p.name_en || p.type_display || '').trim() || p.place_id;
    var address = (p.address || p.city || '').trim() || '—';
    var btn = '<button type="button" class="team13-btn-route-to-place" data-lat="' + lat + '" data-lng="' + lng + '" data-name="' + escapeHtml(name) + '">مسیریابی به اینجا</button>';
    return '<div class="team13-popup"><strong>' + escapeHtml(name) + '</strong><br><span class="text-muted">' + escapeHtml(address) + '</span><br>' + btn + '</div>';
  }

  // --- Popup: Event (time + "مسیریابی به رویداد") ---
  function buildEventPopupContent(e) {
    var lat = parseFloat(e.latitude);
    var lng = parseFloat(e.longitude);
    var title = (e.title_fa || e.title_en || e.event_id || '').trim();
    var timeText = (e.start_at || e.start_at_iso || '') + (e.end_at || e.end_at_iso ? ' تا ' + (e.end_at || e.end_at_iso) : '');
    var routeBtn = '<button type="button" class="team13-btn-route-to-event" data-lat="' + lat + '" data-lng="' + lng + '" data-name="' + escapeHtml(title) + '">مسیریابی به رویداد</button>';
    return '<div class="team13-popup"><strong>' + escapeHtml(title) + '</strong><br><span class="text-muted">زمان: ' + escapeHtml(timeText || '—') + '</span><br>' + routeBtn + '</div>';
  }

  // --- Sync DB layers: fetch places + events, add markers, sidebar cards ---
  function syncDatabaseLayers() {
    var map = getMap();
    if (!map || !window.Team13Api || !window.Team13Api.loadMapData) return Promise.reject(new Error('Map or API not ready'));

    return window.Team13Api.loadMapData().then(function (data) {
      var places = data.places || [];
      var events = data.events || [];
      window._team13PlacesCache = places;
      window._team13EventsCache = events;
      clearPlaceAndEventMarkers(map);
      window.allMarkers = {};
      addPlaceMarkers(map, places);
      addEventMarkers(map, events);
      injectSidebarCards(places, events);
      bindRouteButtonInPopups(map);
      return { places: places, events: events };
    });
  }

  function clearPlaceAndEventMarkers(map) {
    if (!map) return;
    if (window.currentlyShownPoiMarker) {
      map.removeLayer(window.currentlyShownPoiMarker);
      window.currentlyShownPoiMarker = null;
    }
    if (window.team13PlaceLayerGroup) {
      map.removeLayer(window.team13PlaceLayerGroup);
      window.team13PlaceLayerGroup = null;
    }
    if (window.team13EventLayerGroup) {
      map.removeLayer(window.team13EventLayerGroup);
      window.team13EventLayerGroup = null;
    }
    if (window.team13CityEventLayerGroup) {
      map.removeLayer(window.team13CityEventLayerGroup);
      window.team13CityEventLayerGroup = null;
    }
  }

  /**
   * Apply city-based event filter: clear event markers on map, filter by city, render filtered markers, update sidebar, optional center.
   * @param {string|null} cityName - null = show all events in sidebar only (no event markers on map)
   * @param {number|null} centerLat - optional center for map
   * @param {number|null} centerLng - optional center for map
   */
  function applyEventCityFilter(cityName, centerLat, centerLng) {
    var map = getMap();
    var events = window._team13EventsCache || [];
    if (!map || !L) return;

    var filtered = events;
    if (cityName && String(cityName).trim()) {
      var cityNorm = String(cityName).trim();
      filtered = events.filter(function (e) {
        var c = (e.city && String(e.city).trim()) || '';
        return c === cityNorm;
      });
    }

    if (window.team13CityEventLayerGroup) {
      map.removeLayer(window.team13CityEventLayerGroup);
      window.team13CityEventLayerGroup = null;
    }

    injectEventsList(filtered);

    if (!cityName || !String(cityName).trim()) {
      window.allMarkers = {};
      addPlaceMarkers(map, window._team13PlacesCache || []);
      addEventMarkers(map, window._team13EventsCache || []);
    } else if (filtered.length > 0) {
      var layer = L.layerGroup();
      var icon = createEventIcon();
      var allMarkers = Object.assign({}, window.allMarkers || {});
      filtered.forEach(function (e) {
        var lat = parseFloat(e.latitude);
        var lng = parseFloat(e.longitude);
        if (isNaN(lat) || isNaN(lng)) return;
        var id = 'event-' + (e.event_id || e.id || String(lat) + ',' + String(lng));
        var popupContent = buildEventPopupContent(e);
        var m = L.marker([lat, lng], { icon: icon }).bindPopup(popupContent);
        layer.addLayer(m);
        allMarkers[id] = m;
      });
      window.allMarkers = allMarkers;
      layer.addTo(map);
      window.team13CityEventLayerGroup = layer;
      if (centerLat != null && centerLng != null && !isNaN(centerLat) && !isNaN(centerLng)) {
        flyTo(map, centerLat, centerLng, 12);
      } else {
        var first = filtered[0];
        flyTo(map, parseFloat(first.latitude), parseFloat(first.longitude), 11);
      }
    } else if (centerLat != null && centerLng != null && !isNaN(centerLat) && !isNaN(centerLng)) {
      flyTo(map, centerLat, centerLng, 12);
    }
  }

  /** Update only the events list in sidebar (used by city filter). */
  function injectEventsList(events) {
    var eventsList = document.getElementById('events-list');
    if (!eventsList) return;
    eventsList.innerHTML = '';
    (events || []).forEach(function (e) {
      eventsList.insertAdjacentHTML('beforeend', renderEventCard(e));
    });
  }

  function addPlaceMarkers(map, places) {
    if (!map || !L) return;
    var icon = createPlaceIcon();
    var allMarkers = Object.assign({}, window.allMarkers || {});
    (places || []).forEach(function (p) {
      var lat = parseFloat(p.latitude);
      var lng = parseFloat(p.longitude);
      if (isNaN(lat) || isNaN(lng)) return;
      var id = 'place-' + (p.place_id || p.id || String(lat) + ',' + String(lng));
      var popupContent = buildPlacePopupContent(p, lat, lng);
      var m = L.marker([lat, lng], { icon: icon }).bindPopup(popupContent);
      allMarkers[id] = m;
    });
    window.allMarkers = allMarkers;
  }

  function addEventMarkers(map, events) {
    if (!map || !L) return;
    var icon = createEventIcon();
    var allMarkers = Object.assign({}, window.allMarkers || {});
    (events || []).forEach(function (e) {
      var lat = parseFloat(e.latitude);
      var lng = parseFloat(e.longitude);
      if (isNaN(lat) || isNaN(lng)) return;
      var id = 'event-' + (e.event_id || e.id || String(lat) + ',' + String(lng));
      var popupContent = buildEventPopupContent(e);
      var m = L.marker([lat, lng], { icon: icon }).bindPopup(popupContent);
      allMarkers[id] = m;
    });
    window.allMarkers = allMarkers;
  }

  function clearTemporaryMapItems(map) {
    if (!map) return;
    if (window.currentlyShownPoiMarker) {
      map.removeLayer(window.currentlyShownPoiMarker);
      window.currentlyShownPoiMarker = null;
    }
    if (searchResultMarker && map.hasLayer(searchResultMarker)) {
      map.removeLayer(searchResultMarker);
      searchResultMarker = null;
    }
    if (window.emergencyPoiMarker && map.hasLayer(window.emergencyPoiMarker)) {
      map.removeLayer(window.emergencyPoiMarker);
      window.emergencyPoiMarker = null;
    }
    var routeLayer = window.currentPath || window.routeLayer || window.currentRoute || window.team13RouteLine;
    if (routeLayer && map.hasLayer(routeLayer)) {
      map.removeLayer(routeLayer);
    }
    window.currentPath = null;
    window.routeLayer = null;
    window.currentRoute = null;
    window.team13RouteLine = null;
  }

  function showPoiMarkerById(map, id, lat, lng, isPlace) {
    var allMarkers = window.allMarkers || {};
    var marker = allMarkers[id];
    if (!marker) return;
    clearTemporaryMapItems(map);
    marker.setIcon(isPlace ? createSelectedPlaceIcon() : createSelectedEventIcon());
    marker.addTo(map);
    window.currentlyShownPoiMarker = marker;
    flyTo(map, lat, lng, 15);
    marker.openPopup();
  }

  function bindRouteButtonInPopups(map) {
    if (!map) return;
    function bindRouteBtn(btn) {
      if (!btn) return;
      btn.onclick = function () {
        var lat = parseFloat(btn.getAttribute('data-lat'));
        var lng = parseFloat(btn.getAttribute('data-lng'));
        var name = (btn.getAttribute('data-name') || '').trim();
        if (isNaN(lat) || isNaN(lng)) return;
        setRouteLoading(true);
        if (window.Team13Api && typeof window.Team13Api.getMapirRouteFromTo === 'function') {
          getCurrentPosition()
            .then(function (pos) {
              var userLat = pos.coords.latitude;
              var userLng = pos.coords.longitude;
              switchToRoutesTabAndSetRoute(userLat, userLng, lat, lng, name || 'مقصد', 'driving');
              setRouteLoading(false);
            })
            .catch(function () {
              setDestFromCoords(lat, lng, name || '');
              var tabBtn = document.querySelector('[data-tab="routes"]');
              if (tabBtn) tabBtn.click();
              setRouteLoading(false);
              if (window.showToast) window.showToast('مقصد تنظیم شد. مبدا را انتخاب کنید.');
            });
        } else if (window.Team13Api && typeof window.Team13Api.getMapirRoute === 'function') {
          window.Team13Api.getMapirRoute({ lat: lat, lng: lng }, 'driving')
            .then(function (r) {
              setRouteLoading(false);
              if (typeof window.updateRouteInfoBox === 'function') window.updateRouteInfoBox(r);
              var distStr = r && r.distanceKm != null ? (Math.round(r.distanceKm * 10) / 10) + ' کیلومتر' : '';
              var timeStr = r && r.durationMinutes != null ? r.durationMinutes + ' دقیقه' : '';
              showRouteInfo('فاصله: ' + distStr, 'زمان تقریبی: ' + timeStr);
            })
            .catch(function (err) {
              setRouteLoading(false);
              showRouteInfo('خطا: ' + (err && err.message ? err.message : 'مسیر ناموفق'), '');
            });
        } else {
          requestRouteFromUserTo(lat, lng);
        }
      };
    }
    map.on('popupopen', function (e) {
      var popup = e.popup;
      var el = popup.getElement && popup.getElement();
      if (!el) return;
      var btnPlace = el.querySelector('.team13-btn-route-to-place');
      var btnEvent = el.querySelector('.team13-btn-route-to-event');
      bindRouteBtn(btnPlace);
      bindRouteBtn(btnEvent);
    });
  }

  // --- User location then route + ETA ---
  function requestRouteFromUserTo(targetLat, targetLng) {
    setRouteLoading(true);
    hideRouteInfo();
    getCurrentPosition()
      .then(function (pos) {
        var userLat = pos.coords.latitude;
        var userLng = pos.coords.longitude;
        return fetchRouteAndEta(userLat, userLng, targetLat, targetLng);
      })
      .then(function (result) {
        setRouteLoading(false);
        if (result && result.polyline) {
          showRouteInfo(result.distanceText, result.etaText);
        }
      })
      .catch(function (err) {
        setRouteLoading(false);
        showRouteInfo('خطا: ' + (err && err.message ? err.message : 'موقعیت یا مسیر در دسترس نیست'), '');
      });
  }

  function getCurrentPosition() {
    return new Promise(function (resolve, reject) {
      if (!navigator.geolocation) return reject(new Error('Geolocation not supported'));
      navigator.geolocation.getCurrentPosition(resolve, function (e) {
        reject(new Error(e.message || 'موقعیت یافت نشد'));
      }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 });
    });
  }

  function setRouteLoading(show) {
    var el = document.getElementById('team13-route-loading');
    if (el) el.hidden = !show;
  }

  function showRouteInfo(distanceText, etaText) {
    var box = document.getElementById('team13-route-info');
    var distEl = document.getElementById('team13-route-distance');
    var etaEl = document.getElementById('team13-route-eta');
    if (box) box.hidden = false;
    if (distEl) distEl.textContent = distanceText || '';
    if (etaEl) etaEl.textContent = etaText || '';
  }

  function hideRouteInfo() {
    var box = document.getElementById('team13-route-info');
    if (box) box.hidden = true;
  }

  function fetchRouteAndEta(originLat, originLng, destLat, destLng) {
    var map = getMap();
    var config = getConfig();
    if (!config.apiKey) return Promise.reject(new Error('MAPIR API key not set'));

    var coords = originLng + ',' + originLat + ';' + destLng + ',' + destLat;
    var routeUrl = (config.routingUrl || MAPIR_ROUTE_BASE).replace(/\/?$/, '') + '/' + encodeURIComponent(coords);
    var etaUrl = MAPIR_ETA_BASE + '/' + encodeURIComponent(coords);

    var headers = { 'x-api-key': config.apiKey, Accept: 'application/json' };

    return fetch(routeUrl, { method: 'GET', headers: headers })
      .then(function (res) { return res.json(); })
      .then(function (routeData) {
        var latlngs = parseRouteGeometry(routeData, originLat, originLng, destLat, destLng);
        var distanceKm = parseRouteDistance(routeData);
        var durationSec = parseRouteDuration(routeData);

        if (!durationSec && config.apiKey) {
          return fetch(etaUrl, { method: 'GET', headers: headers })
            .then(function (r) { return r.json(); })
            .then(function (etaData) {
              var dur = parseEtaDuration(etaData);
              return { latlngs: latlngs, distanceKm: distanceKm, durationSec: dur };
            })
            .catch(function () { return { latlngs: latlngs, distanceKm: distanceKm, durationSec: null }; });
        }
        return { latlngs: latlngs, distanceKm: distanceKm, durationSec: durationSec };
      })
      .then(function (out) {
        if (window.team13RouteLine && map) map.removeLayer(window.team13RouteLine);
        window.team13RouteLine = L.polyline(out.latlngs, { color: SAGE_GREEN, weight: 5 }).addTo(map);
        map.fitBounds(window.team13RouteLine.getBounds(), { padding: [40, 40] });

        var distanceText = out.distanceKm != null ? 'فاصله: ' + (Math.round(out.distanceKm * 10) / 10) + ' کیلومتر' : '';
        var etaText = out.durationSec != null ? 'زمان تقریبی: ' + formatDuration(out.durationSec) : '';
        return { polyline: window.team13RouteLine, distanceText: distanceText, etaText: etaText };
      });
  }

  function parseRouteGeometry(data, oLat, oLng, tLat, tLng) {
    var latlngs = [];
    var route = data.route || (data.routes && data.routes[0]);
    if (route && route.legs && Array.isArray(route.legs)) {
      route.legs.forEach(function (leg) {
        if (leg.steps && Array.isArray(leg.steps)) {
          leg.steps.forEach(function (step) {
            if (step.polyline && Array.isArray(step.polyline)) {
              step.polyline.forEach(function (c) {
                if (Array.isArray(c) && c.length >= 2) latlngs.push([c[1], c[0]]);
              });
            }
          });
        }
      });
    }
    if (latlngs.length < 2 && data.waypoints && Array.isArray(data.waypoints)) {
      data.waypoints.forEach(function (p) {
        if (Array.isArray(p)) latlngs.push([p[1], p[0]]);
        else if (p && typeof p.lat !== 'undefined') latlngs.push([p.lat, p.lng]);
      });
    }
    if (latlngs.length < 2 && data.routes && data.routes[0] && data.routes[0].geometry && data.routes[0].geometry.coordinates) {
      latlngs = data.routes[0].geometry.coordinates.map(function (c) { return [c[1], c[0]]; });
    }
    if (latlngs.length < 2) latlngs = [[oLat, oLng], [tLat, tLng]];
    return latlngs;
  }

  function parseRouteDistance(data) {
    var route = data.route || (data.routes && data.routes[0]);
    if (route && typeof route.distance === 'number') return route.distance / 1000;
    if (route && route.legs && route.legs[0] && typeof route.legs[0].distance === 'number') {
      var d = 0;
      route.legs.forEach(function (leg) { d += leg.distance || 0; });
      return d / 1000;
    }
    return null;
  }

  function parseRouteDuration(data) {
    var route = data.route || (data.routes && data.routes[0]);
    if (route && typeof route.duration === 'number') return route.duration;
    if (route && route.legs && route.legs[0] && typeof route.legs[0].duration === 'number') {
      var d = 0;
      route.legs.forEach(function (leg) { d += leg.duration || 0; });
      return d;
    }
    return null;
  }

  function parseEtaDuration(data) {
    if (data && typeof data.duration === 'number') return data.duration;
    if (data && data.routes && data.routes[0] && typeof data.routes[0].duration === 'number') return data.routes[0].duration;
    return null;
  }

  function formatDuration(seconds) {
    if (seconds < 60) return seconds + ' ثانیه';
    var m = Math.floor(seconds / 60);
    var s = Math.round(seconds % 60);
    if (s === 0) return m + ' دقیقه';
    return m + ' دقیقه و ' + s + ' ثانیه';
  }

  // --- Sidebar: cards with flyTo on click ---
  function renderPlaceCard(p) {
    var name = (p.name_fa || p.name_en || p.type_display || p.place_id).trim();
    var lat = parseFloat(p.latitude);
    var lng = parseFloat(p.longitude);
    var btn = '<button type="button" class="team13-btn-show-map" data-lat="' + lat + '" data-lng="' + lng + '" data-place-id="' + escapeHtml(p.place_id) + '" data-name="' + escapeHtml(name) + '">نمایش روی نقشه</button>';
    return '<div class="team13-card team13-data-card team13-clickable-card" data-lat="' + lat + '" data-lng="' + lng + '" data-place-id="' + escapeHtml(p.place_id) + '" data-name="' + escapeHtml(name) + '"><p class="font-semibold text-[#1b4332]">' + escapeHtml(name) + '</p><p class="text-sm text-gray-600">' + escapeHtml(p.type_display || '') + (p.city ? ' — ' + escapeHtml(p.city) : '') + '</p>' + btn + '</div>';
  }

  function renderEventCard(e) {
    var title = (e.title_fa || e.title_en || e.event_id).trim();
    var eventId = e.event_id;
    var btn = '<button type="button" class="team13-btn-show-event-on-map" data-event-id="' + escapeHtml(eventId) + '" data-title="' + escapeHtml(title) + '">نمایش روی نقشه</button>';
    return '<div class="team13-card team13-data-card team13-clickable-card" data-event-id="' + escapeHtml(eventId) + '" data-title="' + escapeHtml(title) + '"><p class="font-semibold text-[#1b4332]">' + escapeHtml(title) + '</p><p class="text-sm text-gray-600">' + (e.start_at || e.start_at_iso || '') + (e.city ? ' — ' + escapeHtml(e.city) : '') + '</p>' + btn + '</div>';
  }

  function flyTo(map, lat, lng, zoom) {
    if (!map) return;
    var z = zoom != null ? zoom : (map.getZoom && map.getZoom()) || 14;
    if (map.flyTo) map.flyTo([lat, lng], z, { duration: 0.5 });
    else map.setView([lat, lng], z, { animate: true });
  }

  function injectSidebarCards(places, events) {
    var placesList = document.getElementById('places-list');
    var eventsList = document.getElementById('events-list');
    var welcomeCard = document.querySelector('#panel-places .team13-welcome-card');
    if (welcomeCard) welcomeCard.remove();
    if (placesList) {
      placesList.innerHTML = '<p class="text-sm text-gray-600 mb-2">برای یافتن مکان‌ها (رستوران، هتل، بیمارستان و ...) از تب <strong>اطراف من</strong> استفاده کنید.</p>' +
        '<button type="button" class="team13-btn-discovery-goto" data-tab="discovery">برو به اطراف من</button>';
      var gotoBtn = placesList.querySelector('.team13-btn-discovery-goto');
      if (gotoBtn) gotoBtn.addEventListener('click', function () {
        var t = document.querySelector('[data-tab="discovery"]');
        if (t) t.click();
      });
    }
    if (eventsList) {
      eventsList.innerHTML = '';
      (events || []).forEach(function (e) {
        eventsList.insertAdjacentHTML('beforeend', renderEventCard(e));
      });
    }
    var map = getMap();
    function openActionMenuAt(lat, lng, name) {
      flyTo(map, lat, lng);
      if (typeof window.showActionMenu === 'function') window.showActionMenu(lat, lng, name || 'مکان');
    }

    placesList && placesList.addEventListener('click', function (ev) {
      var btn = ev.target.closest('.team13-btn-show-map');
      if (btn) {
        var lat = parseFloat(btn.getAttribute('data-lat'));
        var lng = parseFloat(btn.getAttribute('data-lng'));
        var placeId = btn.getAttribute('data-place-id') || '';
        var name = btn.getAttribute('data-name') || '';
        if (!isNaN(lat) && !isNaN(lng) && placeId) {
          showPoiMarkerById(map, 'place-' + placeId, lat, lng, true);
        } else if (!isNaN(lat) && !isNaN(lng)) {
          openActionMenuAt(lat, lng, name);
        }
        if (typeof window.Team13CloseSidebar === 'function') window.Team13CloseSidebar();
        return;
      }
      var card = ev.target.closest('.team13-clickable-card[data-lat][data-lng]');
      if (card) {
        var lat = parseFloat(card.getAttribute('data-lat'));
        var lng = parseFloat(card.getAttribute('data-lng'));
        var placeId = card.getAttribute('data-place-id') || '';
        var name = card.getAttribute('data-name') || '';
        if (!isNaN(lat) && !isNaN(lng) && placeId) {
          showPoiMarkerById(map, 'place-' + placeId, lat, lng, true);
        } else if (!isNaN(lat) && !isNaN(lng)) {
          openActionMenuAt(lat, lng, name);
        }
        if (typeof window.Team13CloseSidebar === 'function') window.Team13CloseSidebar();
      }
    });
    eventsList && eventsList.addEventListener('click', function (ev) {
      var btn = ev.target.closest('.team13-btn-show-event-on-map');
      if (btn) {
        var eventId = btn.getAttribute('data-event-id');
        var title = btn.getAttribute('data-title') || '';
        if (eventId && window.Team13Api && window.Team13Api.api) {
          window.Team13Api.api.eventDetail(eventId).then(function (detail) {
            var lat = detail.latitude != null ? parseFloat(detail.latitude) : NaN;
            var lng = detail.longitude != null ? parseFloat(detail.longitude) : NaN;
            if (!isNaN(lat) && !isNaN(lng)) {
              if (window.allMarkers && window.allMarkers['event-' + eventId]) {
                showPoiMarkerById(map, 'event-' + eventId, lat, lng, false);
              } else {
                openActionMenuAt(lat, lng, title);
              }
            }
          }).catch(function () {});
        }
        if (typeof window.Team13CloseSidebar === 'function') window.Team13CloseSidebar();
        return;
      }
      var card = ev.target.closest('.team13-clickable-card[data-event-id]');
      if (card && window.Team13Api && window.Team13Api.api) {
        var eventId = card.getAttribute('data-event-id');
        var title = card.getAttribute('data-title') || '';
        window.Team13Api.api.eventDetail(eventId).then(function (detail) {
          var lat = detail.latitude != null ? parseFloat(detail.latitude) : NaN;
          var lng = detail.longitude != null ? parseFloat(detail.longitude) : NaN;
          if (!isNaN(lat) && !isNaN(lng)) {
            if (window.allMarkers && window.allMarkers['event-' + eventId]) {
              showPoiMarkerById(map, 'event-' + eventId, lat, lng, false);
            } else {
              openActionMenuAt(lat, lng, title);
            }
          }
        }).catch(function () {});
        if (typeof window.Team13CloseSidebar === 'function') window.Team13CloseSidebar();
      }
    });
  }

  // --- Search: Map.ir Autocomplete ---
  var searchDebounceTimer;
  var searchResultMarker = null;

  function initSearch() {
    var input = document.getElementById('team13-search-input');
    var resultsEl = document.getElementById('team13-search-results');
    if (!input || !resultsEl) return;

    input.addEventListener('input', function () {
      clearTimeout(searchDebounceTimer);
      var q = (input.value || '').trim();
      if (q.length < 2) {
        resultsEl.hidden = true;
        resultsEl.innerHTML = '';
        return;
      }
      searchDebounceTimer = setTimeout(function () {
        mapirAutocomplete(q).then(function (items) {
          renderSearchResults(resultsEl, items);
          resultsEl.hidden = items.length === 0;
        }).catch(function () {
          resultsEl.hidden = true;
          resultsEl.innerHTML = '';
        });
      }, 300);
    });

    input.addEventListener('blur', function () {
      setTimeout(function () {
        resultsEl.hidden = true;
      }, 200);
    });

    var btnClearSearch = document.getElementById('team13-clear-search');
    if (btnClearSearch) btnClearSearch.addEventListener('click', function () {
      clearSearchResult();
    });
  }

  function mapirAutocomplete(text) {
    var config = getConfig();
    if (!config.apiKey) return Promise.resolve([]);
    var url = MAPIR_AUTOCOMPLETE + '?text=' + encodeURIComponent(text);
    return fetch(url, { method: 'GET', headers: { 'x-api-key': config.apiKey, Accept: 'application/json' } })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        var value = data.value || data;
        if (!Array.isArray(value)) return [];
        return value.slice(0, 8);
      })
      .catch(function () { return []; });
  }

  function getItemLatLng(item) {
    if (item.y != null && item.x != null) return { lat: parseFloat(item.y), lng: parseFloat(item.x) };
    if (item.lat != null && item.lon != null) return { lat: parseFloat(item.lat), lng: parseFloat(item.lon) };
    if (item.latitude != null && item.longitude != null) return { lat: parseFloat(item.latitude), lng: parseFloat(item.longitude) };
    var geom = item.geom || item.geometry;
    if (geom && geom.coordinates && Array.isArray(geom.coordinates) && geom.coordinates.length >= 2)
      return { lng: parseFloat(geom.coordinates[0]), lat: parseFloat(geom.coordinates[1]) };
    return null;
  }

  function renderSearchResults(container, items) {
    container.innerHTML = '';
    items.forEach(function (item) {
      var title = (item.title || item.address || item.name || item.text || JSON.stringify(item)).trim();
      var ll = getItemLatLng(item);
      if (!ll) return;
      var lat = ll.lat;
      var lng = ll.lng;
      var div = document.createElement('div');
      div.className = 'team13-search-result-item';
      div.textContent = title;
      div.dataset.lat = lat;
      div.dataset.lng = lng;
      div.dataset.title = title;
      div.addEventListener('click', function () {
        selectSearchResult(lat, lng, title);
      });
      container.appendChild(div);
    });
  }

  function selectSearchResult(lat, lng, title) {
    var map = getMap();
    var input = document.getElementById('team13-search-input');
    var resultsEl = document.getElementById('team13-search-results');
    if (input) input.value = title || '';
    if (resultsEl) { resultsEl.hidden = true; resultsEl.innerHTML = ''; }

    setDestFromCoords(lat, lng, title || '');
    var inputDest = document.getElementById('team13-input-dest');
    if (inputDest) inputDest.value = title || '';
    clearTemporaryMapItems(map);
    flyTo(map, lat, lng, 15);
  }

  // --- Emergency: nearest hospital (DB), nearest fire (Map.ir search) ---
  function initEmergencyButtons() {
    var btnHospital = document.getElementById('team13-btn-nearest-hospital');
    var btnFire = document.getElementById('team13-btn-nearest-fire');
    if (btnHospital) btnHospital.addEventListener('click', triggerNearestHospital);
    if (btnFire) btnFire.addEventListener('click', triggerNearestFireStation);
  }

  /**
   * Emergency: find nearest POI, clear other markers, draw multi-point route, show only that POI marker.
   * @param {string} category - "بیمارستان" or "آتش نشانی"
   */
  function triggerNearestPoi(category) {
    var map = getMap();
    setRouteLoading(true);
    hideRouteInfo();
    clearTemporaryMapItems(map);
    if (!window.Team13Api || typeof window.Team13Api.findNearest !== 'function' || typeof window.Team13Api.getMapirRoute !== 'function') {
      setRouteLoading(false);
      showRouteInfo('خطا: سرویس مسیریابی در دسترس نیست', '');
      return;
    }
    window.Team13Api.findNearest(category)
      .then(function (poi) {
        if (!poi || poi.lat == null || poi.lng == null) throw new Error(category === 'بیمارستان' ? 'بیمارستانی یافت نشد' : 'آتش‌نشانی یافت نشد');
        if (map && window.emergencyPoiMarker && map.hasLayer(window.emergencyPoiMarker)) map.removeLayer(window.emergencyPoiMarker);
        window.emergencyPoiMarker = L.marker([poi.lat, poi.lng], { icon: createEmergencyPoiIcon() })
          .bindPopup('<div class="team13-popup"><strong>' + escapeHtml(poi.title || category) + '</strong></div>');
        window.emergencyPoiMarker.addTo(map);
        return window.Team13Api.getMapirRoute({ lat: poi.lat, lng: poi.lng }, 'driving');
      })
      .then(function (r) {
        setRouteLoading(false);
        if (typeof window.updateRouteInfoBox === 'function') window.updateRouteInfoBox(r);
      })
      .catch(function (err) {
        setRouteLoading(false);
        if (window.emergencyPoiMarker && map && map.hasLayer(window.emergencyPoiMarker)) {
          map.removeLayer(window.emergencyPoiMarker);
          window.emergencyPoiMarker = null;
        }
        showRouteInfo('خطا: ' + (err && err.message ? err.message : (category === 'بیمارستان' ? 'بیمارستان' : 'آتش‌نشانی') + ' یافت نشد'), '');
      });
  }

  function triggerNearestHospital() {
    triggerNearestPoi('بیمارستان');
  }

  function triggerNearestFireStation() {
    triggerNearestPoi('آتش نشانی');
  }

  // --- Start/Destination routing state ---
  var startCoords = null;
  var startAddress = '';
  var destCoords = null;
  var destAddress = '';
  var startMarker = null;
  var destMarker = null;
  var pickMode = null;
  var routeMode = 'driving';
  var reverseGeocodeMarker = null;

  function setPickMode(mode) {
    pickMode = mode;
    var map = getMap();
    var container = map && map.getContainer && map.getContainer();
    if (container) container.style.cursor = mode ? 'crosshair' : '';
    var btnStart = document.getElementById('team13-btn-pick-start');
    var btnDest = document.getElementById('team13-btn-pick-dest');
    if (btnStart) btnStart.classList.toggle('active', mode === 'start');
    if (btnDest) btnDest.classList.toggle('active', mode === 'dest');
  }

  function setStartFromCoords(lat, lng, address) {
    startCoords = { lat: lat, lng: lng };
    startAddress = address || '';
    var input = document.getElementById('team13-input-start');
    if (input) input.value = startAddress;
    var map = getMap();
    if (map && startMarker) map.removeLayer(startMarker);
    startMarker = L.marker([lat, lng], { icon: createStartMarkerIcon(), draggable: true })
      .on('dragend', function () {
        var pos = startMarker.getLatLng();
        startCoords = { lat: pos.lat, lng: pos.lng };
        window.Team13Api.reverseGeocode(pos.lat, pos.lng).then(function (data) {
          startAddress = (data && (data.address || data.address_compact || data.postal_address)) || '';
          var inp = document.getElementById('team13-input-start');
          if (inp) inp.value = startAddress;
          drawRouteFromToIfBoth();
        });
      })
      .addTo(map);
    drawRouteFromToIfBoth();
  }

  function setDestFromCoords(lat, lng, address) {
    destCoords = { lat: lat, lng: lng };
    destAddress = address || '';
    var input = document.getElementById('team13-input-dest');
    if (input) input.value = destAddress;
    var topInput = document.getElementById('team13-search-input');
    if (topInput) topInput.value = destAddress;
    var map = getMap();
    if (map && destMarker) map.removeLayer(destMarker);
    destMarker = L.marker([lat, lng], { icon: createDestMarkerIcon(), draggable: true })
      .on('dragend', function () {
        var pos = destMarker.getLatLng();
        destCoords = { lat: pos.lat, lng: pos.lng };
        window.Team13Api.reverseGeocode(pos.lat, pos.lng).then(function (data) {
          destAddress = (data && (data.address || data.address_compact || data.postal_address)) || '';
          var inp = document.getElementById('team13-input-dest');
          if (inp) inp.value = destAddress;
          var top = document.getElementById('team13-search-input');
          if (top) top.value = destAddress;
          drawRouteFromToIfBoth();
        });
      })
      .addTo(map);
    drawRouteFromToIfBoth();
  }

  function drawRouteFromToIfBoth() {
    if (!startCoords || !destCoords || !window.Team13Api || typeof window.Team13Api.getMapirRouteFromTo !== 'function') return;
    var clearBtn = document.getElementById('team13-btn-clear-path');
    if (clearBtn) clearBtn.style.display = 'block';
    window.Team13Api.getMapirRouteFromTo(startCoords, destCoords, routeMode)
      .then(function (r) {
        if (typeof window.updateRouteInfoBox === 'function') window.updateRouteInfoBox(r);
      })
      .catch(function (err) {
        if (typeof window.updateRouteInfoBox === 'function') window.updateRouteInfoBox(null);
        if (typeof window.showToast === 'function') window.showToast('خطا: ' + (err && err.message ? err.message : 'مسیریابی ناموفق'));
      });
  }

  function clearRouteLine() {
    var map = getMap();
    [window.currentPath, window.routeLayer, window.currentRoute, window.team13RouteLine].forEach(function (layer) {
      if (layer && map && map.hasLayer(layer)) map.removeLayer(layer);
    });
    window.currentPath = null;
    window.routeLayer = null;
    window.currentRoute = null;
    window.team13RouteLine = null;
    hideRouteInfo();
    if (typeof window.updateRouteInfoBox === 'function') window.updateRouteInfoBox(null);
    var clearBtn = document.getElementById('team13-btn-clear-path');
    if (clearBtn) clearBtn.style.display = 'none';
  }

  function clearStart() {
    startCoords = null;
    startAddress = '';
    var input = document.getElementById('team13-input-start');
    if (input) input.value = '';
    var map = getMap();
    if (startMarker && map && map.hasLayer(startMarker)) {
      map.removeLayer(startMarker);
    }
    startMarker = null;
    clearRouteLine();
  }

  function clearDest() {
    destCoords = null;
    destAddress = '';
    var input = document.getElementById('team13-input-dest');
    if (input) input.value = '';
    var topInput = document.getElementById('team13-search-input');
    if (topInput) topInput.value = '';
    var map = getMap();
    if (destMarker && map && map.hasLayer(destMarker)) {
      map.removeLayer(destMarker);
    }
    destMarker = null;
    clearRouteLine();
  }

  function initStartDestUI() {
    var inputStart = document.getElementById('team13-input-start');
    var inputDest = document.getElementById('team13-input-dest');
    var resultsStart = document.getElementById('team13-start-results');
    var resultsDest = document.getElementById('team13-dest-results');
    var btnPickStart = document.getElementById('team13-btn-pick-start');
    var btnPickDest = document.getElementById('team13-btn-pick-dest');
    var btnMyLocation = document.getElementById('team13-btn-my-location');
    var modeWrap = document.getElementById('team13-route-mode-wrap');
    if (!inputStart || !inputDest) return;

    function bindAutocomplete(inputEl, resultsEl, setter) {
      if (!inputEl || !resultsEl) return;
      var debounce;
      inputEl.addEventListener('input', function () {
        clearTimeout(debounce);
        var q = (inputEl.value || '').trim();
        if (q.length < 2) { resultsEl.hidden = true; resultsEl.innerHTML = ''; return; }
        debounce = setTimeout(function () {
          mapirAutocomplete(q).then(function (items) {
            resultsEl.innerHTML = '';
            items.forEach(function (item) {
              var title = (item.title || item.address || item.name || item.text || '').trim();
              var ll = getItemLatLng(item);
              if (!ll) return;
              var div = document.createElement('div');
              div.className = 'team13-search-result-item';
              div.textContent = title;
              div.dataset.lat = ll.lat;
              div.dataset.lng = ll.lng;
              div.dataset.title = title;
              div.addEventListener('click', function () {
                setter(ll.lat, ll.lng, title);
                resultsEl.hidden = true;
                resultsEl.innerHTML = '';
              });
              resultsEl.appendChild(div);
            });
            resultsEl.hidden = items.length === 0;
          });
        }, 300);
      });
      inputEl.addEventListener('blur', function () {
        setTimeout(function () { resultsEl.hidden = true; }, 200);
      });
    }

    bindAutocomplete(inputStart, resultsStart, setStartFromCoords);
    bindAutocomplete(inputDest, resultsDest, setDestFromCoords);

    if (btnPickStart) {
      btnPickStart.addEventListener('click', function () {
        setPickMode(pickMode === 'start' ? null : 'start');
      });
    }
    if (btnPickDest) {
      btnPickDest.addEventListener('click', function () {
        setPickMode(pickMode === 'dest' ? null : 'dest');
      });
    }
    if (btnMyLocation) {
      btnMyLocation.addEventListener('click', function () {
        if (!navigator.geolocation) {
          if (window.showToast) window.showToast('موقعیت یافت نشد');
          return;
        }
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            var lat = pos.coords.latitude;
            var lng = pos.coords.longitude;
            window.Team13Api.reverseGeocode(lat, lng).then(function (data) {
              var addr = (data && (data.address || data.address_compact || data.postal_address)) || '';
              setStartFromCoords(lat, lng, addr);
              if (window.showToast) window.showToast('مبدا روی موقعیت شما تنظیم شد');
            }).catch(function () {
              setStartFromCoords(lat, lng, '');
            });
          },
          function () {
            if (window.showToast) window.showToast('دسترسی به موقعیت امکان‌پذیر نیست');
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
        );
      });
    }
    if (modeWrap) {
      modeWrap.querySelectorAll('.team13-route-mode-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
          routeMode = this.getAttribute('data-mode') || 'driving';
          modeWrap.querySelectorAll('.team13-route-mode-btn').forEach(function (b) {
            b.classList.remove('active', 'active-transport');
          });
          this.classList.add('active', 'active-transport');
          drawRouteFromToIfBoth();
          if (typeof window.Team13CloseSidebar === 'function') window.Team13CloseSidebar();
        });
      });
    }

    var btnClearStart = document.getElementById('team13-clear-start');
    var btnClearDest = document.getElementById('team13-clear-dest');
    if (btnClearStart) btnClearStart.addEventListener('click', clearStart);
    if (btnClearDest) btnClearDest.addEventListener('click', clearDest);
  }

  function onMapClickForStartDest(e) {
    if (!pickMode || pickMode !== 'start' && pickMode !== 'dest') return false;
    var map = getMap();
    if (!map || !e || !e.latlng) return true;
    var lat = e.latlng.lat;
    var lng = e.latlng.lng;
    var mode = pickMode;
    setPickMode(null);
    window.Team13Api.reverseGeocode(lat, lng)
      .then(function (data) {
        var addr = (data && (data.address || data.address_compact || data.postal_address)) || '';
        if (mode === 'start') setStartFromCoords(lat, lng, addr);
        else setDestFromCoords(lat, lng, addr);
      })
      .catch(function () {
        if (mode === 'start') setStartFromCoords(lat, lng, '');
        else setDestFromCoords(lat, lng, '');
      });
    return true;
  }

  // --- Reverse geocode on map click: place marker and show Iranian address (when not in pick mode) ---
  function initReverseGeocodeClick() {
    var map = getMap();
    if (!map || !window.Team13Api || typeof window.Team13Api.reverseGeocode !== 'function') return;
    map.off('click', onMapClickReverseGeocode);
    map.on('click', onMapClickReverseGeocode);
  }

  function onMapClickReverseGeocode(e) {
    if (onMapClickForDiscovery(e)) return;
    if (onMapClickForStartDest(e)) return;
    var map = getMap();
    if (!map || !e || !e.latlng) return;
    var lat = e.latlng.lat;
    var lng = e.latlng.lng;

    if (reverseGeocodeMarker && map) {
      map.removeLayer(reverseGeocodeMarker);
      reverseGeocodeMarker = null;
    }

    var markerIcon = L.divIcon({
      className: 'team13-reverse-marker',
      html: '<span style="width:22px;height:22px;background:#40916c;border:2px solid #1b4332;border-radius:50%;display:block;box-shadow:0 2px 8px rgba(0,0,0,0.3);"></span>',
      iconSize: [22, 22],
      iconAnchor: [11, 11],
    });
    reverseGeocodeMarker = L.marker([lat, lng], { icon: markerIcon }).addTo(map);
    reverseGeocodeMarker.bindPopup('در حال دریافت آدرس...', { className: 'team13-reverse-popup', closeButton: true }).openPopup();

    window.Team13Api.reverseGeocode(lat, lng)
      .then(function (data) {
        if (!data || !reverseGeocodeMarker) return;
        var address = (data.address || data.address_compact || data.postal_address || '').trim() || 'آدرس یافت نشد';
        var wrap = document.createElement('div');
        wrap.className = 'team13-reverse-popup-content';
        wrap.innerHTML = '<p class="team13-reverse-popup-address">' + escapeHtml(address) + '</p><button type="button" class="team13-btn-delete-point">حذف نقطه</button>';
        var btn = wrap.querySelector('.team13-btn-delete-point');
        if (btn) {
          btn.addEventListener('click', function () {
            var m = reverseGeocodeMarker;
            if (m && map && map.hasLayer(m)) map.removeLayer(m);
            reverseGeocodeMarker = null;
          });
        }
        reverseGeocodeMarker.setPopupContent(wrap).openPopup();
      })
      .catch(function () {
        if (!reverseGeocodeMarker) return;
        var wrap = document.createElement('div');
        wrap.className = 'team13-reverse-popup-content';
        wrap.innerHTML = '<p class="team13-reverse-popup-address">آدرس یافت نشد</p><button type="button" class="team13-btn-delete-point">حذف نقطه</button>';
        var btn = wrap.querySelector('.team13-btn-delete-point');
        if (btn) {
          btn.addEventListener('click', function () {
            var m = reverseGeocodeMarker;
            if (m && map && map.hasLayer(m)) map.removeLayer(m);
            reverseGeocodeMarker = null;
          });
        }
        reverseGeocodeMarker.setPopupContent(wrap).openPopup();
      });
  }

  // --- Live user location (advancegeolocation: watch + custom blue marker, silent) ---
  function startUserLocationTracking() {
    var map = getMap();
    if (!map || window._userLocationWatchStarted) return;
    window._userLocationWatchStarted = true;
    window.userLocationCoords = null;

    map.locate({ watch: true, enableHighAccuracy: true, setView: false, maxZoom: 16 });

    map.on('locationfound', function (e) {
      var latlng = e.latlng;
      window.userLocationCoords = { lat: latlng.lat, lng: latlng.lng };

      if (!window.userMarker) {
        window.userMarker = L.marker(latlng, {
          icon: createUserLocationIcon(),
          interactive: false,
          keyboard: false,
          zIndexOffset: 1000,
        }).addTo(map);
        map.flyTo(latlng, 16, { duration: 0.6 });
      } else {
        window.userMarker.setLatLng(latlng);
      }
    });

    map.on('locationerror', function (e) {
      if (window._userLocationWatchStarted && e.message) {
        console.warn('Team13 location error:', e.message);
      }
    });
  }

  function initCenterOnMeButton() {
    var btn = document.getElementById('team13-btn-center-me');
    if (!btn) return;
    btn.addEventListener('click', function () {
      var map = getMap();
      if (!map || !window.userMarker) return;
      var latlng = window.userMarker.getLatLng();
      map.flyTo(latlng, 16, { duration: 0.5 });
    });
  }

  // --- Discovery (اطراف من): radius-based POI search ---
  var discoveryCenter = null;
  var discoveryRadiusKm = 2;
  var discoveryCircleLayer = null;
  /** Single layer group for discovery POIs — created once, use clearLayers() to avoid removing base map. */
  var discoveryMarkersLayer = null;
  var pickModeDiscovery = false;

  /** Ensure discovery markers layer exists and is on the map once (recovery: never use map.eachLayer). */
  function ensureDiscoveryMarkersLayer() {
    var map = getMap();
    if (!map || !L) return null;
    if (!discoveryMarkersLayer) {
      discoveryMarkersLayer = L.layerGroup();
      discoveryMarkersLayer.addTo(map);
    }
    return discoveryMarkersLayer;
  }

  function distanceMeters(lat1, lng1, lat2, lng2) {
    var R = 6371000;
    var dLat = ((lat2 - lat1) * Math.PI) / 180;
    var dLng = ((lng2 - lng1) * Math.PI) / 180;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  function buildDiscoveryPlacePopup(p, lat, lng) {
    var name = (p.name_fa || p.name_en || p.type_display || '').trim() || p.place_id;
    var address = (p.address || p.city || '').trim() || '—';
    var detailUrl = '/team13/places/' + (p.place_id || '') + '/';
    var html = '<div class="team13-popup team13-discovery-popup">' +
      '<strong>' + escapeHtml(name) + '</strong><br><span class="text-muted">' + escapeHtml(address) + '</span><br>' +
      '<a href="' + escapeHtml(detailUrl) + '" class="team13-btn-discovery-detail">مشاهده جزئیات</a> ' +
      '<button type="button" class="team13-btn-discovery-route" data-lat="' + lat + '" data-lng="' + lng + '" data-place-id="' + escapeHtml(String(p.place_id || '')) + '" data-name="' + escapeHtml(name) + '">مسیریابی به اینجا</button>' +
      '</div>';
    return html;
  }

  function switchToRoutesTabAndSetRoute(fromLat, fromLng, toLat, toLng, toName, mode) {
    var tabBtn = document.querySelector('[data-tab="routes"]');
    if (tabBtn) tabBtn.click();
    setStartFromCoords(fromLat, fromLng, '');
    setDestFromCoords(toLat, toLng, toName || '');
    routeMode = mode || 'driving';
    var modeWrap = document.getElementById('team13-route-mode-wrap');
    if (modeWrap) {
      modeWrap.querySelectorAll('.team13-route-mode-btn').forEach(function (b) {
        var isActive = (b.getAttribute('data-mode') || '') === routeMode;
        b.classList.toggle('active', isActive);
        b.classList.toggle('active-transport', isActive);
      });
    }
    drawRouteFromToIfBoth();
  }

  /** Deselect Area: remove circle, clear POI markers via clearLayers() (do not remove layer group), reset radius, clear center, deactivate Pick on Map. */
  function clearDiscoveryArea() {
    var map = getMap();
    if (discoveryCircleLayer && map && map.hasLayer(discoveryCircleLayer)) {
      map.removeLayer(discoveryCircleLayer);
      discoveryCircleLayer = null;
    }
    if (discoveryMarkersLayer) {
      discoveryMarkersLayer.clearLayers();
    }
    discoveryCenter = null;
    discoveryRadiusKm = 0.5;
    pickModeDiscovery = false;
    if (map) {
      var container = map.getContainer && map.getContainer();
      if (container) container.style.cursor = '';
    }
    var btnPick = document.getElementById('team13-discovery-pick-map');
    if (btnPick) btnPick.classList.remove('active');
    var slider = document.getElementById('team13-discovery-radius');
    var valueEl = document.getElementById('team13-discovery-radius-value');
    if (slider) {
      slider.value = 0.5;
      discoveryRadiusKm = 0.5;
    }
    if (valueEl) valueEl.textContent = '0.5';
    if (window.showToast) window.showToast('محدوده پاکسازی شد');
  }

  function runDiscoverySearch() {
    var map = getMap();
    if (!map) return;
    if (!discoveryCenter) {
      if (window.showToast) window.showToast('ابتدا نقطه مرکز را انتخاب کنید.');
      return;
    }
    if (window.currentlyShownPoiMarker && map.hasLayer(window.currentlyShownPoiMarker)) {
      map.removeLayer(window.currentlyShownPoiMarker);
      window.currentlyShownPoiMarker = null;
    }
    if (searchResultMarker && map.hasLayer(searchResultMarker)) {
      map.removeLayer(searchResultMarker);
      searchResultMarker = null;
    }
    if (window.emergencyPoiMarker && map.hasLayer(window.emergencyPoiMarker)) {
      map.removeLayer(window.emergencyPoiMarker);
      window.emergencyPoiMarker = null;
    }
    if (reverseGeocodeMarker && map.hasLayer(reverseGeocodeMarker)) {
      map.removeLayer(reverseGeocodeMarker);
      reverseGeocodeMarker = null;
    }
    var places = window._team13PlacesCache || [];
    if (places.length === 0 && window.Team13Api && window.Team13Api.loadMapData) {
      window.Team13Api.loadMapData().then(function (data) {
        window._team13PlacesCache = data.places || [];
        runDiscoverySearch();
      }).catch(function () {
        if (window.showToast) window.showToast('بارگذاری مکان‌ها ناموفق بود.');
      });
      return;
    }
    var checked = document.querySelectorAll('input[name="discovery-cat"]:checked');
    var selectedTypes = [];
    checked.forEach(function (el) { selectedTypes.push(el.value); });
    var radiusM = discoveryRadiusKm * 1000;
    var centerLat = discoveryCenter.lat;
    var centerLng = discoveryCenter.lng;
    var filtered = places.filter(function (p) {
      var lat = parseFloat(p.latitude);
      var lng = parseFloat(p.longitude);
      if (isNaN(lat) || isNaN(lng)) return false;
      if (distanceMeters(centerLat, centerLng, lat, lng) > radiusM) return false;
      if (selectedTypes.length > 0 && selectedTypes.indexOf(p.type) === -1) return false;
      return true;
    });

    if (discoveryCircleLayer && map) map.removeLayer(discoveryCircleLayer);
    discoveryCircleLayer = L.circle([centerLat, centerLng], {
      radius: radiusM,
      color: '#40916c',
      fillColor: '#40916c',
      fillOpacity: 0.12,
      weight: 2,
    }).addTo(map);

    var layer = ensureDiscoveryMarkersLayer();
    if (layer) layer.clearLayers();
    var discoveryIcon = createDiscoveryPlaceIcon();
    filtered.forEach(function (p) {
      var lat = parseFloat(p.latitude);
      var lng = parseFloat(p.longitude);
      if (isNaN(lat) || isNaN(lng)) return;
      var popupContent = buildDiscoveryPlacePopup(p, lat, lng);
      var m = L.marker([lat, lng], { icon: discoveryIcon }).bindPopup(popupContent);
      m._team13DiscoveryPlace = p;
      if (discoveryMarkersLayer) discoveryMarkersLayer.addLayer(m);
    });

    if (discoveryMarkersLayer) discoveryMarkersLayer.eachLayer(function (layer) {
      if (layer.bindPopup && layer.getPopup) {
        layer.on('popupopen', function () {
          var popup = layer.getPopup();
          var el = popup && popup.getElement && popup.getElement();
          if (!el) return;
          var btn = el.querySelector('.team13-btn-discovery-route');
          if (!btn || btn._bound) return;
          btn._bound = true;
          btn.addEventListener('click', function () {
            var lat = parseFloat(btn.getAttribute('data-lat'));
            var lng = parseFloat(btn.getAttribute('data-lng'));
            var name = btn.getAttribute('data-name') || '';
            if (!discoveryCenter || isNaN(lat) || isNaN(lng)) return;
            var wrap = document.createElement('div');
            wrap.className = 'team13-discovery-route-mode';
            wrap.innerHTML = '<p class="team13-discovery-route-title">نوع مسیر:</p>' +
              '<button type="button" class="team13-route-mode-btn" data-mode="driving">خودرو</button>' +
              '<button type="button" class="team13-route-mode-btn" data-mode="walking">پیاده</button>' +
              '<button type="button" class="team13-route-mode-btn" data-mode="bicycle">دوچرخه</button>';
            var btns = wrap.querySelectorAll('.team13-route-mode-btn');
            btns.forEach(function (b) {
              b.addEventListener('click', function () {
                var mode = b.getAttribute('data-mode') || 'driving';
                switchToRoutesTabAndSetRoute(discoveryCenter.lat, discoveryCenter.lng, lat, lng, name, mode);
              });
            });
            popup.setContent(wrap);
          });
        });
      }
    });

    if (filtered.length > 0 && discoveryMarkersLayer) map.fitBounds(discoveryMarkersLayer.getBounds(), { padding: [40, 40], maxZoom: 15 });
    if (window.showToast) window.showToast('یافت شد: ' + filtered.length + ' مکان');
  }

  function initDiscoveryUI() {
    var map = getMap();
    if (map) ensureDiscoveryMarkersLayer();
    var btnMyLoc = document.getElementById('team13-discovery-my-location');
    var btnPick = document.getElementById('team13-discovery-pick-map');
    var slider = document.getElementById('team13-discovery-radius');
    var valueEl = document.getElementById('team13-discovery-radius-value');
    var btnSearch = document.getElementById('team13-discovery-search');

    if (btnMyLoc) {
      btnMyLoc.addEventListener('click', function () {
        if (!navigator.geolocation) {
          if (window.showToast) window.showToast('موقعیت یافت نشد');
          return;
        }
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            discoveryCenter = { lat: pos.coords.latitude, lng: pos.coords.longitude };
            pickModeDiscovery = false;
            var map = getMap();
            if (map) {
              var container = map.getContainer && map.getContainer();
              if (container) container.style.cursor = '';
            }
            if (btnPick) btnPick.classList.remove('active');
            var radiusKm = parseFloat(slider && slider.value) || 2;
            discoveryRadiusKm = radiusKm;
            if (discoveryCircleLayer && map) map.removeLayer(discoveryCircleLayer);
            discoveryCircleLayer = L.circle([discoveryCenter.lat, discoveryCenter.lng], {
              radius: radiusKm * 1000,
              color: '#40916c',
              fillColor: '#40916c',
              fillOpacity: 0.12,
              weight: 2,
            }).addTo(map);
            flyTo(map, discoveryCenter.lat, discoveryCenter.lng, 14);
            if (window.showToast) window.showToast('مرکز روی موقعیت شما تنظیم شد');
          },
          function () {
            if (window.showToast) window.showToast('دسترسی به موقعیت امکان‌پذیر نیست');
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
        );
      });
    }

    if (btnPick) {
      btnPick.addEventListener('click', function () {
        pickModeDiscovery = !pickModeDiscovery;
        var map = getMap();
        if (map) {
          var container = map.getContainer && map.getContainer();
          if (container) container.style.cursor = pickModeDiscovery ? 'crosshair' : '';
        }
        btnPick.classList.toggle('active', pickModeDiscovery);
      });
    }

    if (slider && valueEl) {
      slider.addEventListener('input', function () {
        discoveryRadiusKm = parseFloat(slider.value) || 2;
        valueEl.textContent = discoveryRadiusKm;
      });
      valueEl.textContent = parseFloat(slider.value) || 2;
    }

    if (btnSearch) btnSearch.addEventListener('click', runDiscoverySearch);
    var btnClearArea = document.getElementById('team13-discovery-clear-area');
    if (btnClearArea) btnClearArea.addEventListener('click', clearDiscoveryArea);
    var btnDeselect = document.getElementById('team13-discovery-deselect');
    if (btnDeselect) btnDeselect.addEventListener('click', clearDiscoveryArea);
  }

  function onMapClickForDiscovery(e) {
    if (!pickModeDiscovery) return false;
    var map = getMap();
    if (!map || !e || !e.latlng) return true;
    var lat = e.latlng.lat;
    var lng = e.latlng.lng;
    pickModeDiscovery = false;
    var container = map.getContainer && map.getContainer();
    if (container) container.style.cursor = '';
    var btnPick = document.getElementById('team13-discovery-pick-map');
    if (btnPick) btnPick.classList.remove('active');
    discoveryCenter = { lat: lat, lng: lng };
    var radiusKm = parseFloat(document.getElementById('team13-discovery-radius') && document.getElementById('team13-discovery-radius').value) || 2;
    discoveryRadiusKm = radiusKm;
    if (discoveryCircleLayer && map) map.removeLayer(discoveryCircleLayer);
    discoveryCircleLayer = L.circle([lat, lng], {
      radius: radiusKm * 1000,
      color: '#40916c',
      fillColor: '#40916c',
      fillOpacity: 0.12,
      weight: 2,
    }).addTo(map);
    if (window.showToast) window.showToast('مرکز انتخاب شد');
    return true;
  }

  // --- Events tab: city selector + Events Near Me ---
  function initEventsCityUI() {
    var cityInput = document.getElementById('team13-events-city-input');
    var btnNearMe = document.getElementById('team13-events-near-me');

    if (btnNearMe) {
      btnNearMe.addEventListener('click', function () {
        if (!window.Team13Api || typeof window.Team13Api.getCityFromCoords !== 'function') {
          if (window.showToast) window.showToast('سرویس موقعیت در دسترس نیست');
          return;
        }
        if (!navigator.geolocation) {
          if (window.showToast) window.showToast('دسترسی به موقعیت امکان‌پذیر نیست');
          return;
        }
        if (window.showToast) window.showToast('در حال دریافت موقعیت...');
        navigator.geolocation.getCurrentPosition(
          function (pos) {
            var lat = pos.coords.latitude;
            var lng = pos.coords.longitude;
            window.Team13Api.getCityFromCoords(lat, lng).then(function (result) {
              if (!result || !result.city) {
                if (window.showToast) window.showToast('شهر برای این موقعیت یافت نشد');
                return;
              }
              if (cityInput) cityInput.value = result.city;
              applyEventCityFilter(result.city, result.lat, result.lng);
              if (window.showToast) window.showToast('رویدادهای ' + result.city);
            }).catch(function () {
              if (window.showToast) window.showToast('خطا در دریافت شهر');
            });
          },
          function () {
            if (window.showToast) window.showToast('دسترسی به موقعیت امکان‌پذیر نیست');
          },
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
        );
      });
    }

    if (cityInput) {
      function applyCityFromInput() {
        var city = (cityInput.value && cityInput.value.trim()) || '';
        if (city) window.currentCity = city;
        applyEventCityFilter(city || null, null, null);
      }
      cityInput.addEventListener('change', applyCityFromInput);
      cityInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          applyCityFromInput();
        }
      });
    }
  }

  // --- Run: sync layers + init search + emergency + reverse geocode click + start/dest UI + live location + discovery + events city ---
  function run() {
    var map = getMap();
    if (!map) return;
    syncDatabaseLayers().catch(function (err) {
      console.warn('Team13 syncDatabaseLayers failed', err);
    });
    initSearch();
    initEmergencyButtons();
    initStartDestUI();
    initDiscoveryUI();
    initEventsCityUI();
    initReverseGeocodeClick();
    startUserLocationTracking();
    initCenterOnMeButton();
  }

  function waitMapAndRun() {
    if (getMap() && window.Team13Api) {
      run();
      return;
    }
    setTimeout(waitMapAndRun, 150);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', waitMapAndRun);
  } else {
    waitMapAndRun();
  }

  function clearSearchResult() {
    var map = getMap();
    if (searchResultMarker && map) {
      map.removeLayer(searchResultMarker);
      searchResultMarker = null;
    }
    var input = document.getElementById('team13-search-input');
    if (input) input.value = '';
    var resultsEl = document.getElementById('team13-search-results');
    if (resultsEl) { resultsEl.hidden = true; resultsEl.innerHTML = ''; }
  }

  /** Called when user switches to Events tab: optional city detection and filter; smooth FlyTo on city change. */
  function onEventsTabActivated() {
    if (!window.Team13Api || typeof window.Team13Api.getCityFromCoords !== 'function') return;
    if (window._team13EventsCityAutoDone) return;
    if (!navigator.geolocation) return;
    window._team13EventsCityAutoDone = true;
    navigator.geolocation.getCurrentPosition(
      function (pos) {
        var lat = pos.coords.latitude;
        var lng = pos.coords.longitude;
        window.Team13Api.getCityFromCoords(lat, lng).then(function (result) {
          if (!result || !result.city) return;
          var cityInput = document.getElementById('team13-events-city-input');
          if (cityInput) cityInput.value = result.city;
          applyEventCityFilter(result.city, result.lat, result.lng);
          if (window.showToast) window.showToast('رویدادهای ' + result.city);
        }).catch(function () {});
      },
      function () {},
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 120000 }
    );
  }

  window.Team13MapData = {
    syncDatabaseLayers: syncDatabaseLayers,
    getRouteToPlace: requestRouteFromUserTo,
    flyTo: flyTo,
    panTo: function (map, lat, lng) { flyTo(map, lat, lng); },
    addPlaceMarkers: addPlaceMarkers,
    addEventMarkers: addEventMarkers,
    clearSearchResult: clearSearchResult,
    applyEventCityFilter: applyEventCityFilter,
    onEventsTabActivated: onEventsTabActivated,
    run: run,
  };
})();
