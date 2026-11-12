// ═══════════════════════════════════════════════════════════
//  SERVICE WORKER — S G A PWA Offline
//  Versión: 1.1.0
// ═══════════════════════════════════════════════════════════

const CACHE_NAME = 'sga-v89';
const OFFLINE_DB  = 'ambulacia-offline';
const SW_FETCH_TIMEOUT = 30000;
// Con señal débil la red puede tardar minutos en fallar. Pasado este tiempo
// se muestra la copia guardada (si existe) en lugar de dejar la pantalla en blanco.
const RED_LENTA_MS = 5000;
const PAGINA_OFFLINE = '/static/offline.html?v=3';

// Páginas que requieren sesión iniciada. Solo se pueden guardar con la
// sesión activa: si se piden sin sesión, el servidor redirige al login.
const PAGINAS = [
  '/dashboard',
  '/formulario',
  '/formulario_mci',
  '/formularios/atencion-colectiva/registros',
  '/formularios/atencion_vehiculo',
  '/checklist/tam',
  '/checklist/tab',
  '/checklist/avanzada',
  '/checklist/pasb',
  '/checklist/pasm',
  '/checklist/equipos',
  '/checklist/calif_atencion',
  '/checklist/segur_paciente',
  '/formularios/eventos',
  '/reporte_gasto/nuevo',
  '/registros',
  '/pendientes',
  '/pendientes/checklists',
  '/api/cie10_full'
];

// Archivos públicos: se guardan al instalar.
const ESTATICOS = [
  '/static/icon-192.png',
  '/static/icon-512.png',
  '/static/icon-maskable-512.png',
  '/static/manifest.json',
  PAGINA_OFFLINE,
  '/static/pwa-offline.js?v=60',
  '/static/js/dictation.js',
  '/static/data/Departamentos_Municipios.json',
  '/static/data/barrios_medellin.json',
  '/static/data/divipola_estructurado.json'
];

// Formularios que todavía no pueden guardarse sin conexión (su envío se
// perdería). Sin conexión se muestra la página de aviso en lugar del formulario.
const SIN_OFFLINE = new Set([
  '/checklist/preoperacional',
  '/formularios/atencion-colectiva'
]);

// Una respuesta se guarda solo si es la página pedida. Si el servidor
// redirigió (por ejemplo al login porque no había sesión), no se guarda:
// el navegador no puede usar una redirección guardada para abrir una página.
function esGuardable(resp) {
  return !!resp && resp.ok && !resp.redirected && resp.type === 'basic';
}

async function precachear(urls) {
  const cache = await caches.open(CACHE_NAME);
  const fallidos = [];
  await Promise.all(urls.map(async url => {
    try {
      const resp = await fetch(new Request(url, { credentials: 'same-origin', cache: 'no-store' }));
      if (esGuardable(resp)) {
        await cache.put(url, resp);
      } else {
        fallidos.push(url);
      }
    } catch (err) {
      fallidos.push(url);
    }
  }));
  return fallidos;
}

// ── Instalación: archivos públicos y, si hay sesión, las páginas ──
self.addEventListener('install', event => {
  event.waitUntil(
    precachear(ESTATICOS)
      .then(fallidos => {
        if (fallidos.length) console.warn('[SW] No se guardaron:', fallidos);
        // Sin sesión estas fallan y se guardan después del login (mensaje PRECACHE_PAGINAS).
        return precachear(PAGINAS);
      })
      .then(() => self.skipWaiting())
  );
});

// ── Activación: limpiar caches viejos ─────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Mensajes desde la página ──────────────────────────────
self.addEventListener('message', event => {
  const data = event.data || {};
  if (data.type === 'PRECACHE_PAGINAS') {
    const puerto = event.ports && event.ports[0];
    event.waitUntil(
      precachear(PAGINAS.concat(ESTATICOS)).then(fallidos => {
        if (fallidos.length) console.warn('[SW] Páginas no guardadas:', fallidos);
        if (puerto) puerto.postMessage({ fallidos });
      })
    );
  }
});

function esperar(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function buscarEnCache(req) {
  let r = await caches.match(req);
  if (!r) r = await caches.match(req, { ignoreSearch: true });
  // Copias guardadas por versiones anteriores que en realidad eran el login.
  if (r && r.redirected) return null;
  return r || null;
}

async function paginaSinConexion() {
  const offline = await caches.match(PAGINA_OFFLINE, { ignoreSearch: true });
  if (offline) return offline;
  return new Response('<html><body style="font-family:sans-serif; text-align:center; padding: 50px;"><h2>Sin conexion a Internet</h2><p>Esta pagina no esta guardada para uso offline.</p></body></html>', {
    status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' }
  });
}

function aceptaHtml(req) {
  const accept = req.headers.get('accept');
  return req.mode === 'navigate' || (!!accept && accept.includes('text/html'));
}

// ── Fetch: red primero, con copia guardada si la red falla o tarda ──
self.addEventListener('fetch', event => {
  const req = event.request;
  const url = new URL(req.url);

  if (url.origin !== location.origin) return;
  if (url.searchParams.has('_sw_bypass')) return;
  if (url.pathname.startsWith('/api/') && url.pathname !== '/api/cie10_full') return;

  if (req.method !== 'GET') {
    // Envíos de formularios que no se guardan offline: avisar en vez de mostrar un error del navegador.
    if (req.mode === 'navigate') {
      event.respondWith(fetch(req).catch(() => paginaSinConexion()));
    }
    return;
  }

  event.respondWith(redPrimero(req, url));
});

async function redPrimero(req, url) {
  const red = fetch(req).then(resp => {
    if (esGuardable(resp)) {
      const copia = resp.clone();
      caches.open(CACHE_NAME).then(cache => cache.put(req, copia)).catch(() => {});
    }
    return resp;
  });
  red.catch(() => {}); // el error se maneja abajo

  const sinOffline = req.mode === 'navigate' && SIN_OFFLINE.has(url.pathname);

  try {
    if (sinOffline) return await red;
    // Si la red tarda más de RED_LENTA_MS y hay copia guardada, se usa la copia.
    const respaldo = esperar(RED_LENTA_MS)
      .then(() => buscarEnCache(req))
      .then(copia => copia || red);
    return await Promise.race([red, respaldo]);
  } catch (err) {
    if (sinOffline) return paginaSinConexion();
    const copia = await buscarEnCache(req);
    if (copia) return copia;
    if (aceptaHtml(req)) return paginaSinConexion();
    return new Response('Sin conexion', { status: 503 });
  }
}

// ── Sincronización en background cuando vuelve internet ───
self.addEventListener('sync', event => {
  if (event.tag === 'sync-registros') {
    event.waitUntil(conCandado(sincronizarRegistros));
  }
});

// Evita que la página y el service worker envíen el mismo registro a la vez.
function conCandado(fn) {
  if (self.navigator && self.navigator.locks) {
    return self.navigator.locks.request('sync-registros', () => fn());
  }
  return fn();
}

// ── Fetch con timeout ────────────────────────────────────
function fetchConTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(id));
}

// Token CSRF vigente: se pide al servidor, porque el guardado con el
// registro puede ser de una página vieja y ya no coincidir con la cookie.
async function obtenerTokenCSRF(db) {
  try {
    const resp = await fetchConTimeout('/api/csrf', { credentials: 'same-origin', cache: 'no-store' }, 10000);
    if (resp.ok) {
      const data = await resp.json();
      if (data && data.token) return data.token;
    }
  } catch (e) { /* se usa el guardado */ }
  return leerTokenCSRF(db);
}

async function sincronizarRegistros() {
  const db = await abrirIDB();
  const pendientes = await obtenerPendientes(db);
  if (!pendientes.length) return;

  const token = await obtenerTokenCSRF(db);
  const seenDedupe = new Set();
  let fallidos = 0;

  for (const registro of pendientes) {
    // Deduplicación local (un "finalizar" nunca se descarta)
    if (registro.dedupe_key && seenDedupe.has(registro.dedupe_key)
        && !(registro.datos && registro.datos.accion === 'finalizar')) {
      await marcarSincronizado(db, registro.id);
      continue;
    }

    try {
      const formData = new FormData();
      for (const [key, value] of Object.entries(registro.datos)) {
        if (key === 'csrf_token') continue;
        if (value !== null && value !== undefined && value !== '') {
          if (Array.isArray(value)) {
            value.forEach(v => formData.append(key, v));
          } else {
            formData.append(key, value);
          }
        }
      }

      formData.append('_offline_sync', '1');
      formData.append('_offline_id', registro.id);
      formData.append('_offline_dedupe_key', registro.dedupe_key || '');
      const tokenEnvio = token || registro.datos.csrf_token;
      if (tokenEnvio) formData.append('csrf_token', tokenEnvio);

      let urlPost = registro.datos._offline_post_url || '/formulario';
      const acId = registro.datos.atencion_colectiva_id;
      if (!registro.datos._offline_post_url && acId && acId !== 'None' && acId !== 'null' && acId !== 'undefined' && acId !== '') {
        urlPost = '/formulario_mci?atencion_colectiva_id=' + encodeURIComponent(acId);
      }

      const response = await fetchConTimeout(urlPost, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin'
      }, SW_FETCH_TIMEOUT);

      let responseData = {};
      try { responseData = await response.json(); } catch(e) {}

      if (response.ok && responseData.status === 'success') {
        await marcarSincronizado(db, registro.id);
        if (registro.dedupe_key) seenDedupe.add(registro.dedupe_key);
        const clients = await self.clients.matchAll();
        clients.forEach(client => {
          client.postMessage({
            type: 'SYNC_SUCCESS',
            registroId: registro.id,
            paciente: [registro.datos.primer_nombre, registro.datos.primer_apellido].filter(Boolean).join(' ') || ('registro #' + registro.id)
          });
        });
      } else if (response.status !== 401) {
        // 401 = sesión vencida: no se reintenta hasta que el usuario vuelva a entrar.
        console.error('[SW] El servidor no aceptó el registro', registro.id, response.status, responseData);
        fallidos++;
      }
    } catch (err) {
      console.error('[SW] Error sincronizando registro:', registro.id, err);
      fallidos++;
    }
  }

  // Si algo falló, el navegador vuelve a intentar más tarde.
  if (fallidos > 0) throw new Error(fallidos + ' registro(s) sin sincronizar');
}

// ── Helpers IndexedDB ──────────────────────────────────────
function abrirIDB() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(OFFLINE_DB, 2);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('registros')) {
        const store = db.createObjectStore('registros', { keyPath: 'id', autoIncrement: true });
        store.createIndex('sincronizado', 'sincronizado', { unique: false });
        store.createIndex('fecha_creacion', 'fecha_creacion', { unique: false });
        store.createIndex('dedupe_key', 'dedupe_key', { unique: false });
      } else if (e.oldVersion < 2) {
        const tx = e.target.transaction;
        const store = tx.objectStore('registros');
        if (!store.indexNames.contains('dedupe_key')) {
          store.createIndex('dedupe_key', 'dedupe_key', { unique: false });
        }
      }
      if (!db.objectStoreNames.contains('sesion')) {
        const s = db.createObjectStore('sesion', { keyPath: 'key' });
        s.createIndex('fecha_guardado', 'fecha_guardado', { unique: false });
      }
    };
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

function obtenerPendientes(db) {
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('registros', 'readonly');
    const store = tx.objectStore('registros');
    const index = store.index('sincronizado');
    const req   = index.getAll(0);
    req.onsuccess = e => resolve(e.target.result);
    req.onerror   = e => reject(e.target.error);
  });
}

function leerTokenCSRF(db) {
  return new Promise((resolve) => {
    try {
      const tx = db.transaction('sesion', 'readonly');
      const req = tx.objectStore('sesion').get('csrf_token');
      req.onsuccess = e => resolve((e.target.result && e.target.result.token) || null);
      req.onerror = () => resolve(null);
    } catch (e) { resolve(null); }
  });
}

function marcarSincronizado(db, id) {
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('registros', 'readwrite');
    const store = tx.objectStore('registros');
    const req   = store.get(id);
    req.onsuccess = e => {
      const registro = e.target.result;
      if (!registro) return;
      registro.sincronizado = 1;
      registro.fecha_sync   = new Date().toISOString();
      store.put(registro);
    };
    tx.oncomplete = () => resolve();
    tx.onerror    = e => reject(e.target.error);
  });
}
