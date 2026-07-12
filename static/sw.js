// ═══════════════════════════════════════════════════════════
//  SERVICE WORKER — Ambulacia PWA Offline
//  Versión: 1.0.5
// ═══════════════════════════════════════════════════════════

const CACHE_NAME = 'ambulacia-v59';
const OFFLINE_DB  = 'ambulacia-offline';

// Recursos que se cachean al instalar (shell de la app)
const STATIC_ASSETS = [
  '/',
  '/dashboard',
  '/formulario',
  '/formulario_mci',
  '/formularios/eventos',
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
  '/registros',
  '/pendientes',
  '/pendientes/checklists',
  '/static/manifest.json',
  '/static/offline.html?v=3',
  '/static/pwa-offline.js?v=23',
  '/static/js/dictation.js',
  '/static/js/vosk_worker.js',
  '/static/vosk/vosk.js',
  '/static/vosk/model.tar.gz',
  '/api/cie10_full',
  '/static/data/Departamentos_Municipios.json',
  '/static/data/barrios_medellin.json',
  '/static/data/divipola_estructurado.json'
];

// ── Instalación: cachear assets estáticos ─────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      // Intentamos cachear cada asset con credenciales para que pasen el @login_required
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

  // Solo interceptamos peticiones al mismo origen
  if (url.origin !== location.origin) return;

  // No interceptar peticiones de ping (para detectar conexión real)
  if (url.searchParams.has('_sw_bypass')) return;

  // No interceptar llamadas al API (excepto el JSON grande de cie10)
  if (url.pathname.startsWith('/api/') && !url.pathname.includes('/cie10_full')) return;

  // Para el formulario y recursos estáticos: Network first → Cache fallback
  event.respondWith(
    fetch(req).then(response => {
      // Si la respuesta es válida, la guardamos en cache
      if (response && response.status === 200 && req.method === 'GET') {
        const responseClone = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(req, responseClone));
      }
      return response;
    }).catch(() => {
      // Sin internet: servir desde cache
      return caches.match(req).then(cached => {
        if (cached) return cached;
        
        // Intento 2: buscar ignorando parámetros (sirve la plantilla base de /formulario si no hay cache exacto)
        return caches.match(req, { ignoreSearch: true }).then(cachedFallback => {
          if (cachedFallback) return cachedFallback;
          
          // Si no hay cache para esta ruta, servir página offline
          if (req.headers.get('accept') && req.headers.get('accept').includes('text/html')) {
            return caches.match('/static/offline.html', { ignoreSearch: true }).then(offlinePage => {
                if (offlinePage) return offlinePage;
                return new Response('<html><body style="font-family:sans-serif; text-align:center; padding: 50px;"><h2>Sin conexión a Internet</h2><p>Esta página no está guardada para uso offline.</p></body></html>', { 
                    status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } 
                });
            });
          }
          return new Response('Sin conexión', { status: 503 });
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

async function sincronizarRegistros() {
  const db = await abrirIDB();
  const pendientes = await obtenerPendientes(db);

  for (const registro of pendientes) {
    try {
      const formData = new FormData();
      // Convertir objeto a FormData
      for (const [key, value] of Object.entries(registro.datos)) {
        if (value !== null && value !== undefined) {
          formData.append(key, value);
        }
      }

      // Añadir flags indicando que es sync offline (crucial para que el backend no haga redirect)
      formData.append('_offline_sync', '1');
      formData.append('_offline_id', registro.id);

      let urlPost = '/formulario';
      const acId = registro.datos.atencion_colectiva_id;
      if (acId && acId !== 'None' && acId !== 'null' && acId !== 'undefined' && acId !== '') {
        urlPost = '/formulario_mci?atencion_colectiva_id=' + encodeURIComponent(acId);
      }

      const response = await fetch(urlPost, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin'
      });

      let responseData = {};
      try { responseData = await response.json(); } catch(e) {}

      if (response.ok && responseData.status === 'success') {
        // Marcar como sincronizado
        await marcarSincronizado(db, registro.id);
        // Notificar al cliente
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
    const req = indexedDB.open(OFFLINE_DB, 1);
    req.onupgradeneeded = e => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('registros')) {
        const store = db.createObjectStore('registros', { keyPath: 'id', autoIncrement: true });
        store.createIndex('sincronizado', 'sincronizado', { unique: false });
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
    const req   = index.getAll(0); // 0 = no sincronizado
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
