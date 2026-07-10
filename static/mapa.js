var CONFIG = {
    pollingInterval: 15000,
    cacheKey: 'mapa_ubicaciones_cache',
    cacheTTL: 3600000,
    colombiaBounds: [[-4.227, -81.821], [13.390, -66.848]],
    defaultCenter: [4.6097, -74.0817],
    defaultZoom: 6,
};

var map, markersCluster;
var allLocations = [];
var profileColors = {};
var activeFilters = { perfiles: [], maxMinutos: 0, search: '' };
var reverseGeocodeCache = {};
var statusOnline = true;

function initMap() {
    map = L.map('map', {
        maxBounds: CONFIG.colombiaBounds,
        maxBoundsViscosity: 1.0,
        minZoom: 5,
        zoomControl: false,
    }).setView(CONFIG.defaultCenter, CONFIG.defaultZoom);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
        maxZoom: 19,
    }).addTo(map);

    var osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
        maxZoom: 19,
    });
    var sat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        attribution: '&copy; Esri',
        maxZoom: 19,
    });
    L.control.layers({ 'Calles': osm, 'Satelital': sat }, null, { position: 'topright' }).addTo(map);

    markersCluster = L.markerClusterGroup({
        chunkedLoading: true,
        maxClusterRadius: 50,
        spiderfyOnMaxZoom: true,
        showCoverageOnHover: false,
        zoomToBoundsOnClick: true,
        disableClusteringAtZoom: 16,
    });
    map.addLayer(markersCluster);

    zoomControl = L.control.zoom({ position: 'topright' }).addTo(map);
}

var zoomLocked = false;
var zoomControl;

function toggleZoomLock(lock) {
    zoomLocked = lock;
    if (lock) {
        map.scrollWheelZoom.disable();
        map.doubleClickZoom.disable();
        map.touchZoom.disable();
        map.boxZoom.disable();
        map.keyboard.disable();
        if (zoomControl) map.removeControl(zoomControl);
    } else {
        map.scrollWheelZoom.enable();
        map.doubleClickZoom.enable();
        map.touchZoom.enable();
        map.boxZoom.enable();
        map.keyboard.enable();
        if (zoomControl) map.addControl(zoomControl);
    }
}

function formatTimeAgo(dateStr) {
    if (!dateStr) return 'Desconocido';
    var date = new Date(dateStr.replace(' ', 'T'));
    var diff = Math.floor((new Date() - date) / 60000);
    if (diff < 1) return '<1 min';
    if (diff < 60) return diff + ' min';
    var h = Math.floor(diff / 60);
    var m = diff % 60;
    return h + 'h ' + m + 'm';
}

function getMinutesSince(dateStr) {
    if (!dateStr) return 99999;
    return Math.floor((new Date() - new Date(dateStr.replace(' ', 'T'))) / 60000);
}

function getColor(perfilesStr) {
    for (var p in profileColors) {
        if (perfilesStr.indexOf(p) !== -1) return profileColors[p];
    }
    return '#64748b';
}

function createIcon(color, active) {
    var size = active ? 22 : 16;
    return L.divIcon({
        html: '<div style="background:' + color + ';width:' + size + 'px;height:' + size + 'px;border-radius:50%;border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,0.3);opacity:' + (active ? '1' : '0.5') + ';"></div>',
        iconSize: [size + 6, size + 6],
        iconAnchor: [(size + 6) / 2, (size + 6) / 2],
        popupAnchor: [0, -(size + 6) / 2 - 8],
        className: '',
    });
}

function createPopupContent(user) {
    var perfiles = 'Usuario';
    try {
        var parsed = JSON.parse(user.perfil);
        if (Array.isArray(parsed)) perfiles = parsed.join(', ');
    } catch (e) {
        perfiles = user.perfil || perfiles;
    }
    var diffMin = getMinutesSince(user.ultima_actualizacion_gps);
    var antiguedad = formatTimeAgo(user.ultima_actualizacion_gps);
    var color = getColor(perfiles);
    var indicador = diffMin < 5 ? '🟢' : (diffMin < 30 ? '🟡' : '🔴');

    var html = '<div style="font-size:13px;min-width:220px;">';
    html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">';
    html += '<div style="width:12px;height:12px;border-radius:50%;background:' + color + ';flex-shrink:0;"></div>';
    html += '<strong style="font-size:15px;color:#1e40af;">' + user.nombre + '</strong></div>';
    html += '<div style="color:#64748b;line-height:1.6;">🎯 ' + perfiles + '<br>';
    html += '🆔 ' + (user.identificacion || '') + '<br>';
    html += '<span id="geocode-' + user.identificacion + '" style="font-size:11px;color:#94a3b8;">📍 Obteniendo dirección…</span></div>';
    html += '<div style="background:#f1f5f9;padding:6px 8px;border-radius:6px;margin-top:6px;font-size:11px;">' + indicador + ' ' + antiguedad + '</div></div>';
    return html;
}

function reverseGeocode(lat, lng, key) {
    var cacheKey = lat.toFixed(4) + ',' + lng.toFixed(4);
    var el = document.getElementById('geocode-' + key);
    if (!el) return;
    if (reverseGeocodeCache[cacheKey]) {
        el.textContent = '📍 ' + reverseGeocodeCache[cacheKey];
        return;
    }
    if (reverseGeocodeCache[cacheKey] === null) return;
    reverseGeocodeCache[cacheKey] = null;

    fetch('https://nominatim.openstreetmap.org/reverse?format=json&lat=' + lat + '&lon=' + lng + '&addressdetails=1', { headers: { 'Accept-Language': 'es' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            var addr = data && data.display_name ? data.display_name.split(', ').slice(0, 3).join(', ') : 'No disponible';
            reverseGeocodeCache[cacheKey] = addr;
            var e = document.getElementById('geocode-' + key);
            if (e) e.textContent = '📍 ' + addr;
        })
        .catch(function () {
            var e = document.getElementById('geocode-' + key);
            if (e) e.textContent = '📍 No disponible';
        });
}

function updateLocationsInfo(data) {
    var count = data.filter(function (u) { return u.ultima_latitud && u.ultima_longitud; }).length;
    document.getElementById('contador-unidades').textContent = count + ' activa(s)';
    document.getElementById('info-actualizacion').textContent = 'Última actualización: ' + new Date().toLocaleTimeString('es-CO');
}

function applyFilters() {
    markersCluster.clearLayers();
    var bounds = [];
    var usedCoords = {};

    allLocations.forEach(function (user) {
        if (!user.ultima_latitud || !user.ultima_longitud) return;
        var lat = parseFloat(user.ultima_latitud);
        var lng = parseFloat(user.ultima_longitud);
        if (isNaN(lat) || isNaN(lng)) return;

        var perfilesArr = [];
        try { var p = JSON.parse(user.perfil || ''); perfilesArr = Array.isArray(p) ? p : [p]; } catch (e) { perfilesArr = [(user.perfil || '')]; }

        if (!activeFilters.search) {
            var match = perfilesArr.some(function (pr) { return activeFilters.perfiles.indexOf(pr) !== -1; });
            if (!match) return;
        }

        if (activeFilters.maxMinutos > 0) {
            if (getMinutesSince(user.ultima_actualizacion_gps) > activeFilters.maxMinutos) return;
        }

        if (activeFilters.search) {
            var s = activeFilters.search.toLowerCase();
            if ((user.nombre || '').toLowerCase().indexOf(s) === -1 && (user.identificacion || '').indexOf(s) === -1) return;
        }

        var minsAgo = getMinutesSince(user.ultima_actualizacion_gps);
        var isActive = minsAgo < 5;
        var color = getColor(user.perfil || '');
        var icon = createIcon(color, isActive);

        var coordKey = lat.toFixed(5) + ',' + lng.toFixed(5);
        if (usedCoords[coordKey] !== undefined) {
            lat += (Math.random() - 0.5) * 0.0003;
            lng += (Math.random() - 0.5) * 0.0003;
        }
        usedCoords[coordKey] = (usedCoords[coordKey] || 0) + 1;

        var mktLat = lat, mktLng = lng, mktId = user.identificacion;
        var marker = L.marker([lat, lng], { icon: icon });
        marker.bindPopup(createPopupContent(user));
        marker.on('popupopen', function () { reverseGeocode(mktLat, mktLng, mktId); });
        markersCluster.addLayer(marker);
        bounds.push([lat, lng]);
    });

    if (bounds.length > 0 && !zoomLocked) {
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16 });
    }
    updateConnectionStatus(true);
}

function loadLocations() {
    fetch('/admin/api/locations')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            allLocations = data;
            try { localStorage.setItem(CONFIG.cacheKey, JSON.stringify({ ts: Date.now(), data: data })); } catch (e) {}
            updateLocationsInfo(data);
            applyFilters();
        })
        .catch(function () {
            try {
                var raw = localStorage.getItem(CONFIG.cacheKey);
                if (raw) {
                    var pkt = JSON.parse(raw);
                    if (Date.now() - pkt.ts < CONFIG.cacheTTL) {
                        allLocations = pkt.data;
                        updateLocationsInfo(pkt.data);
                        applyFilters();
                        document.getElementById('contador-unidades').textContent = pkt.data.length + ' (caché)';
                        return;
                    }
                }
            } catch (e) {}
            document.getElementById('contador-unidades').textContent = 'Error';
            updateConnectionStatus(false);
        });
}

function loadProfiles() {
    fetch('/admin/api/perfiles')
        .then(function (r) { return r.json(); })
        .then(function (colors) {
            profileColors = colors;
            buildFilterUI(colors);
        })
        .catch(function () {
            profileColors = {
                'Médico': '#ef4444', 'Enfermero': '#3b82f6', 'APH': '#10b981',
                'Socorrista': '#f59e0b', 'Conductor': '#8b5cf6', 'Administrador': '#ec4899',
            };
            buildFilterUI(profileColors);
        });
}

function buildFilterUI(colors) {
    var container = document.getElementById('filtros-perfiles');
    if (!container) return;
    container.innerHTML = '';
    activeFilters.perfiles = [];

    Object.keys(colors).forEach(function (p) {
        var pill = document.createElement('button');
        pill.type = 'button';
        pill.dataset.perfil = p;
        pill.dataset.activo = '1';
        var bg = colors[p];
        pill.style.cssText = 'display:inline-flex;align-items:center;gap:5px;padding:4px 10px;border-radius:20px;border:1.5px solid ' + bg + ';background:' + bg + ';color:#fff;font-size:12px;font-weight:600;cursor:pointer;transition:all 0.15s;font-family:inherit;line-height:1.3;';
        pill.innerHTML = '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:#fff;opacity:0.8;"></span> ' + p;
        activeFilters.perfiles.push(p);

        pill.addEventListener('click', function () {
            var activo = this.dataset.activo === '1';
            if (activo) {
                this.style.background = 'transparent';
                this.style.color = bg;
                this.dataset.activo = '0';
            } else {
                this.style.background = bg;
                this.style.color = '#fff';
                this.dataset.activo = '1';
            }
            activeFilters.perfiles = [];
            container.querySelectorAll('button[data-activo="1"]').forEach(function (btn) {
                activeFilters.perfiles.push(btn.dataset.perfil);
            });
            applyFilters();
        });

        container.appendChild(pill);
    });
}

function updateConnectionStatus(online) {
    statusOnline = online;
    var el = document.getElementById('status-conexion');
    if (!el) return;
    var ok = online && navigator.onLine;
    el.textContent = ok ? 'En línea' : 'Sin conexión';
    el.style.cssText = 'font-size:11px;font-weight:700;padding:3px 10px;border-radius:10px;display:inline-block;background:' + (ok ? '#d1fae5' : '#fee2e2') + ';color:' + (ok ? '#065f46' : '#991b1b') + ';';
}

document.addEventListener('DOMContentLoaded', function () {
    initMap();
    loadProfiles();
    loadLocations();

    document.getElementById('btn-actualizar').addEventListener('click', loadLocations);

    document.getElementById('desactivar-zoom-auto').addEventListener('change', function () {
        toggleZoomLock(this.checked);
    });
    if (document.getElementById('desactivar-zoom-auto').checked) {
        toggleZoomLock(true);
    }

    document.getElementById('filtro-tiempo').addEventListener('change', function () {
        activeFilters.maxMinutos = parseInt(this.value) || 0;
        applyFilters();
    });

    var searchInput = document.getElementById('filtro-busqueda');
    var searchTimer;
    searchInput.addEventListener('input', function () {
        clearTimeout(searchTimer);
        searchTimer = setTimeout(function () {
            activeFilters.search = searchInput.value.trim();
            loadLocations();
        }, 300);
    });

    setInterval(loadLocations, CONFIG.pollingInterval);

    window.addEventListener('online', function () { updateConnectionStatus(statusOnline); });
    window.addEventListener('offline', function () { updateConnectionStatus(false); });
});
