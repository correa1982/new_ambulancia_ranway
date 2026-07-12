// ═══════════════════════════════════════════════════════════
//  SERVICE WORKER — Ambulacia PWA Offline
//  Versión: 1.0.6
// ═══════════════════════════════════════════════════════════

const CACHE_NAME = 'ambulacia-v71';
const OFFLINE_DB  = 'ambulacia-offline';
const SW_FETCH_TIMEOUT = 30000;

// Recursos que se cachean al instalar (shell de la app)
const STATIC_ASSETS = [
  '/',
  '/dashboard',
  '/formulario',
  '/formulario_mci',
  '/formularios/atencion-colectiva',
  '/formularios/atencion-colectiva/registros',
  '/formularios/atencion_vehiculo',
  '/checklist/preoperacional',
  '/checklist/tam',
  '/checklist/tab',
  '/checklist/avanzada',
  '/checklist/pasb',
  '/checklist/pasm',
  '/checklist/equipos',
  '/checklist/calif_atencion',
  '/checklist/segur_paciente',
  '/formularios/eventos',
  '/registros',
  '/pendientes',
  '/pendientes/checklists',
  '/static/css/styles.css',
  '/static/manifest.json',
  '/static/offline.html?v=3',
  '/static/pwa-offline.js?v=24',
  '/static/js/dictation.js',
  '/api/cie10_full',
  '/static/data/Departamentos_Municipios.json',
  '/static/data/barrios_medellin.json',
  '/static/data/divipola_estructurado.json'
];

// ── Instalación: cachear assets estáticos ─────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return Promise.allSettled(
        STATIC_ASSETS.map(url =>
          fetch(new Request(url, { credentials: 'same-origin' }))
            .then(response => {
                if (response.ok) {
                    return cache.put(url, response);
                } else {
                    console.warn('[SW] Status no-200 al cachear:', url, response.status);
                }
            })
            .catch(err => console.warn('[SW] Fetch falló al cachear:', url, err))
        )
      );
    }).then(() => self.skipWaiting())
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

// ── Fetch: Estrategia Network-First con fallback a cache ───
self.addEventListener('fetch', event => {
  const req  = event.request;
  const url  = new URL(req.url);

  if (url.origin !== location.origin) return;
  if (url.searchParams.has('_sw_bypass')) return;
  if (url.pathname.startsWith('/api/') && !url.pathname.includes('/cie10_full')) return;

  event.respondWith(
    fetch(req).then(response => {
      if (response && response.status === 200 && req.method === 'GET') {
        const responseClone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(req, responseClone));
      }
      return response;
    }).catch(() => {
      return caches.match(req).then(cached => {
        if (cached) return cached;

        return caches.match(req, { ignoreSearch: true }).then(cachedFallback => {
          if (cachedFallback) return cachedFallback;

          if (req.headers.get('accept') && req.headers.get('accept').includes('text/html')) {
            return caches.match('/static/offline.html', { ignoreSearch: true }).then(offlinePage => {
                if (offlinePage) return offlinePage;
                return new Response('<html><body style="font-family:sans-serif; text-align:center; padding: 50px;"><h2>Sin conexion a Internet</h2><p>Esta pagina no esta guardada para uso offline.</p></body></html>', {
                    status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' }
                });
            });
          }
          return new Response('Sin conexion', { status: 503 });
        });
      });
    })
  );
});

// ── Sincronización en background cuando vuelve internet ───
self.addEventListener('sync', event => {
  if (event.tag === 'sync-registros') {
    event.waitUntil(sincronizarRegistros());
  }
});

// ── Fetch con timeout ────────────────────────────────────
function fetchConTimeout(url, options, timeoutMs) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(id));
}

async function sincronizarRegistros() {
  const db = await abrirIDB();
  const pendientes = await obtenerPendientes(db);
  const seenDedupe = new Set();

  for (const registro of pendientes) {
    // Deduplicación local
    if (registro.dedupe_key && seenDedupe.has(registro.dedupe_key)) {
      await marcarSincronizado(db, registro.id);
      continue;
    }

    try {
      const formData = new FormData();
      for (const [key, value] of Object.entries(registro.datos)) {
        if (value !== null && value !== undefined) {
          if (key === 'accion') {
            formData.append(key, 'borrador');
          } else {
            formData.append(key, value);
          }
        }
      }

      formData.append('_offline_sync', '1');
      formData.append('_offline_id', registro.id);
      formData.append('_offline_dedupe_key', registro.dedupe_key || '');

      let urlPost = '/formulario';
      const acId = registro.datos.atencion_colectiva_id;
      if (acId && acId !== 'None' && acId !== 'null' && acId !== 'undefined' && acId !== '') {
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
            paciente: registro.datos.primer_nombre + ' ' + registro.datos.primer_apellido
          });
        });
      }
    } catch (err) {
      console.error('[SW] Error sincronizando registro:', registro.id, err);
    }
  }
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
        store.createIndex('dedupe_key', 'dedupe_key', { unique: false });
      } else if (e.oldVersion < 2) {
        const tx = e.target.transaction;
        const store = tx.objectStore('registros');
        if (!store.indexNames.contains('dedupe_key')) {
          store.createIndex('dedupe_key', 'dedupe_key', { unique: false });
        }
      }
      if (!db.objectStoreNames.contains('sesion')) {
        db.createObjectStore('sesion', { keyPath: 'key' });
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

function marcarSincronizado(db, id) {
  return new Promise((resolve, reject) => {
    const tx    = db.transaction('registros', 'readwrite');
    const store = tx.objectStore('registros');
    const req   = store.get(id);
    req.onsuccess = e => {
      const registro = e.target.result;
      registro.sincronizado = 1;
      registro.fecha_sync   = new Date().toISOString();
      store.put(registro);
    };
    tx.oncomplete = () => resolve();
    tx.onerror    = e => reject(e.target.error);
  });
}
