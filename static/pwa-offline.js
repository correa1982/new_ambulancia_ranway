// ═══════════════════════════════════════════════════════════
//  pwa-offline.js — Lógica offline para Ambulacia
//  Incluir en base.html con: <script src="/static/pwa-offline.js"></script>
//  Versión: 2.0.0
// ═══════════════════════════════════════════════════════════

const PWA = (() => {
  const DB_NAME    = 'ambulacia-offline';
  const DB_VERSION = 2;
  const SESSION_TTL_MS      = 12 * 60 * 60 * 1000;  // 12 horas
  const SYNCED_CLEANUP_DAYS = 7 * 24 * 60 * 60 * 1000; // 7 días
  const FETCH_TIMEOUT_MS    = 30000; // 30 segundos
  const MAX_RETRIES         = 3;
  let   _db        = null;

  // ── Abrir / inicializar IndexedDB ────────────────────────
  function abrirDB() {
    if (_db) return Promise.resolve(_db);
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
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
        } else if (e.oldVersion < 2) {
          const tx = e.target.transaction;
          const s = tx.objectStore('sesion');
          if (!s.indexNames.contains('fecha_guardado')) {
            s.createIndex('fecha_guardado', 'fecha_guardado', { unique: false });
          }
        }
      };
      req.onsuccess = e => { _db = e.target.result; resolve(_db); };
      req.onerror   = e => reject(e.target.error);
    });
  }

  // ── Guardar sesión del usuario (para login offline) ──────
  async function guardarSesion(usuario) {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('sesion', 'readwrite');
      tx.objectStore('sesion').put({ key: 'usuario_activo', fecha_guardado: Date.now(), ...usuario });
      tx.oncomplete = resolve;
      tx.onerror    = e => reject(e.target.error);
    });
  }

  // ── Leer sesión cacheada (con expiración) ────────────────
  async function leerSesion() {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const req = db.transaction('sesion', 'readonly')
                    .objectStore('sesion').get('usuario_activo');
      req.onsuccess = e => {
        const sesion = e.target.result;
        if (!sesion) return resolve(null);
        if (sesion.fecha_guardado && (Date.now() - sesion.fecha_guardado > SESSION_TTL_MS)) {
          const tx2 = db.transaction('sesion', 'readwrite');
          tx2.objectStore('sesion').delete('usuario_activo');
          tx2.oncomplete = () => resolve(null);
          tx2.onerror    = () => resolve(null);
          return;
        }
        resolve(sesion);
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  // ── Generar clave de deduplicación ───────────────────────
  function generarDedupeKey(datos) {
    return [
      datos.tipo_documento || '',
      datos.identificacion_paciente || '',
      datos.fecha_inicio_atencion || '',
      datos.primer_nombre || '',
      datos.primer_apellido || '',
      datos.motivo_consulta || '',
    ].join('|');
  }

  // ── Guardar registro offline ─────────────────────────────
  async function guardarRegistroOffline(datos) {
    if (datos && datos.hasOwnProperty('atencion_colectiva_id')) {
      const acVal = String(datos.atencion_colectiva_id).trim();
      if (!acVal || acVal === 'None' || acVal === 'null' || acVal === 'undefined') {
        datos.atencion_colectiva_id = null;
      }
    }
    const db = await abrirDB();
    const sesion = await leerSesion();
    const registro = {
      datos,
      sincronizado:   0,
      dedupe_key:     generarDedupeKey(datos),
      fecha_creacion: new Date().toISOString(),
      registrado_por: sesion ? sesion.nombre        : 'Desconocido',
      identificacion: sesion ? sesion.identificacion : '',
      perfil:         sesion ? sesion.perfil : '',
      intentos_sync:  0,
    };
    return new Promise((resolve, reject) => {
      const tx  = db.transaction('registros', 'readwrite');
      const req = tx.objectStore('registros').add(registro);
      req.onsuccess = e => resolve(e.target.result);
      tx.onerror    = e => reject(e.target.error);
    });
  }

  // ── Actualizar registro offline existente ──────────────────
  async function actualizarRegistroOffline(id, datos) {
    if (datos && datos.hasOwnProperty('atencion_colectiva_id')) {
      const acVal = String(datos.atencion_colectiva_id).trim();
      if (!acVal || acVal === 'None' || acVal === 'null' || acVal === 'undefined') {
        datos.atencion_colectiva_id = null;
      }
    }
    const numericId = parseInt(id, 10);
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('registros', 'readwrite');
      const store = tx.objectStore('registros');
      const req = store.get(numericId);
      req.onsuccess = e => {
        const registro = e.target.result;
        if (!registro) { reject('Registro no encontrado'); return; }
        registro.datos = datos;
        registro.dedupe_key = generarDedupeKey(datos);
        registro.fecha_actualizacion = new Date().toISOString();
        const putReq = store.put(registro);
        putReq.onsuccess = () => resolve(id);
        putReq.onerror = e2 => reject(e2.target.error);
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  // ── Obtener un registro específico por ID ────────────────
  async function obtenerRegistroPorId(id) {
    const numericId = parseInt(id, 10);
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('registros', 'readonly');
      const req = tx.objectStore('registros').get(numericId);
      req.onsuccess = e => resolve(e.target.result);
      req.onerror = e => reject(e.target.error);
    });
  }

  // ── Obtener registros pendientes por Atencion Colectiva ID ──
  async function obtenerRegistrosPorMCI(acId) {
    const db = await abrirDB();
    const sesion = await leerSesion();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('registros', 'readonly');
      const index = tx.objectStore('registros').index('sincronizado');
      const req = index.getAll(0);
      req.onsuccess = e => {
        let pendientes = e.target.result || [];
        if (sesion && sesion.identificacion) {
          pendientes = pendientes.filter(r => r.identificacion === sesion.identificacion && r.perfil === sesion.perfil);
        }
        const mci = pendientes.filter(r => {
          if (!r.datos) return false;
          const rAcId = r.datos.atencion_colectiva_id;
          if (!rAcId || rAcId === 'None' || rAcId === 'null' || rAcId === 'undefined') return false;
          return String(rAcId) === String(acId);
        });
        resolve(mci);
      };
      req.onerror = e => reject(e.target.error);
    });
  }

  // ── Obtener todos los registros pendientes ───────────────
  async function obtenerPendientes() {
    const db = await abrirDB();
    const sesion = await leerSesion();
    return new Promise((resolve, reject) => {
      const tx    = db.transaction('registros', 'readonly');
      const index = tx.objectStore('registros').index('sincronizado');
      const req   = index.getAll(0);
      req.onsuccess = e => {
        let pendientes = e.target.result || [];
        if (sesion && sesion.identificacion) {
          pendientes = pendientes.filter(r => r.identificacion === sesion.identificacion && r.perfil === sesion.perfil);
        }
        resolve(pendientes);
      };
      req.onerror   = e => reject(e.target.error);
    });
  }

  // ── Obtener todos los registros ──────────────────────────
  async function obtenerTodos() {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const req = db.transaction('registros', 'readonly')
                    .objectStore('registros').getAll();
      req.onsuccess = e => resolve(e.target.result);
      req.onerror   = e => reject(e.target.error);
    });
  }

  // ── Marcar como sincronizado ─────────────────────────────
  async function marcarSincronizado(id) {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx    = db.transaction('registros', 'readwrite');
      const store = tx.objectStore('registros');
      const req   = store.get(id);
      req.onsuccess = e => {
        const r = e.target.result;
        r.sincronizado = 1;
        r.fecha_sync   = new Date().toISOString();
        store.put(r);
      };
      tx.oncomplete = resolve;
      tx.onerror    = e => reject(e.target.error);
    });
  }

  // ── Actualizar intentos de sync ──────────────────────────
  async function actualizarIntentosSync(id, intentos) {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const tx    = db.transaction('registros', 'readwrite');
      const store = tx.objectStore('registros');
      const req   = store.get(id);
      req.onsuccess = e => {
        const r = e.target.result;
        if (r) { r.intentos_sync = intentos; store.put(r); }
      };
      tx.oncomplete = resolve;
      tx.onerror    = e => reject(e.target.error);
    });
  }

  // ── Limpiar registros sincronizados antiguos ─────────────
  async function limpiarSincronizadosViejos() {
    const db = await abrirDB();
    const cutoff = new Date(Date.now() - SYNCED_CLEANUP_DAYS).toISOString();
    return new Promise((resolve, reject) => {
      const tx    = db.transaction('registros', 'readwrite');
      const store = tx.objectStore('registros');
      const index = store.index('sincronizado');
      const req   = index.getAll(1);
      req.onsuccess = e => {
        const sincronizados = e.target.result || [];
        let eliminados = 0;
        for (const r of sincronizados) {
          if (r.fecha_sync && r.fecha_sync < cutoff) {
            store.delete(r.id);
            eliminados++;
          }
        }
        if (eliminados > 0) console.log(`[PWA] Limpiados ${eliminados} registros sincronizados antiguos.`);
      };
      tx.oncomplete = () => resolve();
      tx.onerror    = e => reject(e.target.error);
    });
  }

  let isSyncing = false;

  // ── Fetch con timeout ────────────────────────────────────
  function fetchConTimeout(url, options, timeoutMs) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeoutMs);
    return fetch(url, { ...options, signal: controller.signal })
      .finally(() => clearTimeout(id));
  }

  // ── Sincronizar con el servidor (con retry + dedup) ──────
  async function sincronizar() {
    if (isSyncing) return { ok: 0, errores: 0, omitidos: 0 };
    isSyncing = true;

    try {
      await limpiarSincronizadosViejos();

      const pendientes = await obtenerPendientes();
      if (pendientes.length === 0) return { ok: 0, errores: 0, omitidos: 0 };

      let ok = 0, errores = 0, omitidos = 0;
      const seenDedupe = new Set();

      for (const registro of pendientes) {
        if (registro.dedupe_key && seenDedupe.has(registro.dedupe_key)) {
          await marcarSincronizado(registro.id);
          omitidos++;
          continue;
        }

        const intentos = registro.intentos_sync || 0;
        if (intentos >= MAX_RETRIES) {
          console.warn(`[PWA] Registro ${registro.id} agotó reintentos (${MAX_RETRIES}).`);
          errores++;
          continue;
        }

        let syncOk = false;
        for (let intento = 0; intento <= intentos; intento++) {
          try {
            const formData = new FormData();
            formData.append('_offline_sync', '1');
            formData.append('_offline_id', registro.id);
            formData.append('_offline_dedupe_key', registro.dedupe_key || '');

            for (const [key, val] of Object.entries(registro.datos)) {
              if (val !== null && val !== undefined && val !== '') {
                if (key === 'accion') {
                  formData.append(key, 'borrador');
                } else {
                  formData.append(key, val);
                }
              }
            }

            let urlPost = registro.datos._offline_post_url || '/formulario';
            const acId = registro.datos.atencion_colectiva_id;
            if (!registro.datos._offline_post_url && acId && acId !== 'None' && acId !== 'null' && acId !== 'undefined' && acId !== '') {
              urlPost = '/formulario_mci?atencion_colectiva_id=' + encodeURIComponent(acId);
            }

            const resp = await fetchConTimeout(urlPost, {
              method: 'POST',
              body: formData,
              credentials: 'same-origin'
            }, FETCH_TIMEOUT_MS);

            let data = {};
            try { data = await resp.json(); } catch(e) {}

            if (resp.ok && data.status === 'success') {
              await marcarSincronizado(registro.id);
              if (registro.dedupe_key) seenDedupe.add(registro.dedupe_key);
              syncOk = true;
              ok++;
              break;
            } else if (resp.status === 401) {
              console.error('[PWA] Sesión expirada al sincronizar.');
              errores++;
              syncOk = true;
              break;
            } else {
              console.error('[PWA] Error servidor sync', registro.id, data);
            }
          } catch (err) {
            if (err.name === 'AbortError') {
              console.error(`[PWA] Timeout sync registro ${registro.id} (intento ${intento + 1})`);
            } else {
              console.error(`[PWA] Error sync registro ${registro.id} (intento ${intento + 1}):`, err);
            }
          }

          if (!syncOk && intento < MAX_RETRIES - 1) {
            const delay = Math.min(1000 * Math.pow(2, intento), 15000);
            await new Promise(r => setTimeout(r, delay));
          }
        }

        if (!syncOk) {
          await actualizarIntentosSync(registro.id, intentos + 1);
          errores++;
        }
      }
      return { ok, errores, omitidos };
    } finally {
      isSyncing = false;
    }
  }

  // ── Exportar pendientes a CSV ────────────────────────────
  async function exportarCSV() {
    const todos = await obtenerTodos();
    if (todos.length === 0) {
      alert('No hay registros offline guardados.');
      return;
    }

    const CAMPOS = [
      'id_offline','fecha_creacion','sincronizado','registrado_por',
      'tipo_documento','identificacion_paciente',
      'primer_apellido','segundo_apellido','primer_nombre','segundo_nombre',
      'fecha_nacimiento','edad_visual','sexo_biologico','identidad_genero',
      'estado_civil','ocupacion','nacionalidad','correo_electronico',
      'departamento_residencia','municipio_residencia','barrio_residencia',
      'telefono','direccion','pertenencia_etnica','discapacidad','habitante_calle',
      'aplica_acompanante','acompanante_nombre','acompanante_tipo_doc','acompanante_doc','acompanante_telefono','acompanante_parentesco',
      'aplica_responsable','responsable_nombre','responsable_tipo_doc','responsable_doc','responsable_telefono','responsable_parentesco',
      'primer_respondiente','es_emergencia_medica','detalle_emergencia_medica','es_emergencia_traumatica','detalle_emergencia_traumatica',
      'tipo_afiliacion','aseguradora',
      'presion_arterial','saturacion_oxigeno','frecuencia_cardiaca',
      'frecuencia_respiratoria','glicemia',
      'antecedentes_personales','antecedentes_quirurgicos','antecedentes_toxicologicos','antecedentes_alergicos','antecedentes_ginecobstetricos','medicamentos_actuales','otros_antecedentes','antecedentes_familiares',
      'triage_fecha_hora','triage_clasificacion',
      'glasgow_ocular','glasgow_verbal','glasgow_motora','glasgow_total',
      'estado_consciencia','cincinnati_facial','cincinnati_brazo','cincinnati_habla','cincinnati_total','rts_total',
      'motivo_consulta','enfermedad_actual','analisis','plan',
      'diagnostico_cie10','accion',
    ];

    const escapar = v => {
      if (v === null || v === undefined) return '';
      const s = String(v).replace(/"/g, '""');
      return /[,"\n\r]/.test(s) ? `"${s}"` : s;
    };

    const filas = [CAMPOS.join(',')];
    for (const r of todos) {
      const d = r.datos || {};
      const fila = [
        r.id,
        r.fecha_creacion,
        r.sincronizado ? 'Si' : 'No',
        r.registrado_por,
        ...CAMPOS.slice(4).map(c => escapar(d[c])),
      ];
      filas.push(fila.join(','));
    }

    const blob = new Blob(['\uFEFF' + filas.join('\n')], {
      type: 'text/csv;charset=utf-8;'
    });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `registros_offline_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Exportar pendientes a JSON ───────────────────────────
  async function exportarJSON() {
    const todos = await obtenerTodos();
    const blob  = new Blob([JSON.stringify(todos, null, 2)], { type: 'application/json' });
    const url   = URL.createObjectURL(blob);
    const a     = document.createElement('a');
    a.href      = url;
    a.download  = `registros_offline_${new Date().toISOString().slice(0,10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  // ── Contar pendientes ────────────────────────────────────
  async function contarPendientes() {
    const p = await obtenerPendientes();
    return p.length;
  }

  return {
    abrirDB, guardarSesion, leerSesion,
    guardarRegistroOffline, actualizarRegistroOffline, obtenerRegistroPorId, obtenerRegistrosPorMCI,
    obtenerPendientes,
    marcarSincronizado, sincronizar,
    limpiarSincronizadosViejos,
    exportarCSV, exportarJSON, contarPendientes,
  };
})();


// ═══════════════════════════════════════════════════════════
//  REGISTRO DEL SERVICE WORKER
// ═══════════════════════════════════════════════════════════
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register('/sw.js?v=58', { scope: '/' });
      console.log('[PWA] Service Worker registrado:', reg.scope);

      if (reg.installing) {
          mostrarToast('Descargando plataforma para uso sin conexion...', 'info');
      } else if (reg.active) {
          mostrarToast('Sistema Offline preparado y activo.', 'success');
      }

      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing;
        if (newWorker) {
            newWorker.addEventListener('statechange', () => {
                if (newWorker.state === 'installed') {
                    if (navigator.serviceWorker.controller) {
                        mostrarToast('Actualizacion del modo Offline lista.', 'info');
                    } else {
                        mostrarToast('Descarga completada. Ya puedes desconectarte de internet de forma segura.', 'success');
                    }
                }
            });
        }
      });

      navigator.serviceWorker.addEventListener('message', event => {
        if (event.data?.type === 'SYNC_SUCCESS') {
          mostrarToast(`Sincronizado: ${event.data.paciente}`, 'success');
          actualizarBadgePendientes();
        }
      });
    } catch (err) {
      console.error('[PWA] Error registrando SW:', err);
    }
  });
}


// ═══════════════════════════════════════════════════════════
//  INTERCEPTAR EL FORMULARIO DE HISTORIA CLINICA
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('form-medico') || document.getElementById('form-mci') || document.querySelector('.pwa-offline-form');
  if (!form) return;

  form.addEventListener('submit', async function(e) {
    e.preventDefault();

    const datos = {};
    const fd    = new FormData(form);

    let accionValue = 'borrador';
    if (e.submitter && e.submitter.name) {
      fd.append(e.submitter.name, e.submitter.value);
      accionValue = e.submitter.value;
    } else {
      const hiddenAccion = form.querySelector('input[name="accion"]');
      if (hiddenAccion) {
        fd.append(hiddenAccion.name, hiddenAccion.value);
        accionValue = hiddenAccion.value;
      }
    }

    if (navigator.onLine) {
        try {
            const resp = await fetch('/static/manifest.json?_sw_bypass=1&t=' + Date.now(), { method: 'HEAD', cache: 'no-store' });
            if (!resp.ok) throw new Error('Servidor inaccesible (status ' + resp.status + ')');

            if (e.submitter && e.submitter.name) {
                const hidden = document.createElement('input');
                hidden.type = 'hidden';
                hidden.name = e.submitter.name;
                hidden.value = e.submitter.value;
                form.appendChild(hidden);
            }
            form.submit();
            return;
        } catch (err) {
            console.warn('[PWA] Servidor inaccesible (Fake Online). Forzando guardado offline.', err);
        }
    }

    for (let key of fd.keys()) {
        const values = fd.getAll(key);
        if (key.endsWith('[]') || values.length > 1) {
            datos[key] = values;
        } else {
            datos[key] = values[0];
        }
    }

    datos['_offline_post_url'] = form.getAttribute('action') || (window.location.pathname + window.location.search);

    const cie10Hidden = document.getElementById('cie10-value') || document.getElementById('cie10-value-mci');
    if (cie10Hidden) datos['diagnostico_cie10'] = cie10Hidden.value;

    if (datos.hasOwnProperty('atencion_colectiva_id')) {
      const acVal = String(datos.atencion_colectiva_id).trim();
      if (!acVal || acVal === 'None' || acVal === 'null' || acVal === 'undefined') {
        datos.atencion_colectiva_id = null;
      }
    }

    try {
      const offlineIdInput = document.getElementById('offline_id_input');
      const editId = offlineIdInput && offlineIdInput.value ? parseInt(offlineIdInput.value) : null;
      let id;

      if (editId) {
        id = await PWA.actualizarRegistroOffline(editId, datos);
        mostrarToast(`Registro #${id} actualizado offline.`, 'warning');
        if (window.cancelarEdicionOffline) window.cancelarEdicionOffline(false);
      } else {
        id = await PWA.guardarRegistroOffline(datos);
        if (accionValue === 'finalizar') {
            sessionStorage.setItem('offline_toast_success', `Registro finalizado offline #${id}. Se sincronizara al tener conexion.`);
        } else {
            mostrarToast(`Guardado offline #${id}. Se sincronizara cuando haya internet.`, 'warning');
        }
        form.reset();
      }

      const modalConfirmar = document.getElementById('modal-confirmar-finalizar');
      if (modalConfirmar) {
          modalConfirmar.style.display = 'none';
          document.body.style.overflow = '';
      }
      const modalAceptar = document.getElementById('modal-aceptar-finalizar');
      if (modalAceptar) {
          modalAceptar.disabled = false;
          modalAceptar.innerHTML = 'Si, Finalizar';
      }
      const modalCancelar = document.getElementById('modal-cancelar-finalizar');
      if (modalCancelar) modalCancelar.disabled = false;
      const finalizarBtn = document.getElementById('finalizar-btn');
      if (finalizarBtn) {
          finalizarBtn.disabled = false;
          finalizarBtn.innerHTML = 'Finalizar Historia Clinica';
      }

      const edadEl = document.getElementById('edad');
      if (edadEl) edadEl.value = '';
      const cie10El = document.getElementById('cie10-search');
      if (cie10El) cie10El.value = '';
      const cie10Hidden2 = document.getElementById('cie10-value');
      if (cie10Hidden2) cie10Hidden2.value = '';

      if (typeof window.showStep === 'function') {
          window.showStep(1);
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });

      const btns = form.querySelectorAll('button[type="submit"], button.btn-submit');
      btns.forEach(btn => {
        if (btn.submitTimeoutId) clearTimeout(btn.submitTimeoutId);
        btn.disabled = false;
        btn.style.pointerEvents = 'auto';
        btn.style.opacity = '1';
        if (btn.dataset) delete btn.dataset.clicked;
        if (btn.dataset && btn.dataset.originalHtml) {
            btn.innerHTML = btn.dataset.originalHtml;
        } else {
            if (btn.value === 'guardar_continuar') btn.innerHTML = 'Guardar y Continuar';
            else if (btn.value === 'borrador') btn.innerHTML = 'Guardar como Borrador';
            else if (btn.value === 'guardar') btn.innerHTML = 'Guardar Historia';
            else if (btn.id === 'guardar-continuar-btn') btn.innerHTML = 'Guardar y Continuar';
        }
      });

      actualizarBadgePendientes();
      if (window.cargarRegistrosOfflinePanel) window.cargarRegistrosOfflinePanel();

      if ('serviceWorker' in navigator && 'SyncManager' in window) {
        const sw = await navigator.serviceWorker.ready;
        await sw.sync.register('sync-registros');
      }

      if (accionValue === 'finalizar') {
          if (window.location.pathname.includes('formulario_mci')) {
              if (window.cancelarEdicionOffline) window.cancelarEdicionOffline(false);
              form.reset();
              mostrarToast('Paciente finalizado. El formulario está listo para un nuevo registro.', 'success');
          } else {
              const params = new URLSearchParams(window.location.search);
              const acId = params.get('atencion_colectiva_id');
              if (acId) window.location.href = '/formulario_mci?atencion_colectiva_id=' + encodeURIComponent(acId);
              else window.location.href = '/dashboard';
          }
      }
    } catch (err) {
      console.error('[PWA] Error guardando offline:', err);
      mostrarToast('Error al guardar offline. Intente nuevamente.', 'error');
      const btns = form.querySelectorAll('button[type="submit"], button.btn-submit');
      btns.forEach(btn => { 
          if (btn.submitTimeoutId) clearTimeout(btn.submitTimeoutId);
          btn.disabled = false; 
          btn.style.pointerEvents = 'auto';
          btn.style.opacity = '1';
          if (btn.dataset) delete btn.dataset.clicked;
          if (btn.dataset && btn.dataset.originalHtml) btn.innerHTML = btn.dataset.originalHtml;
      });
    }
  });

  window.addEventListener('online', async () => {
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
      mostrarToast('Conexion restaurada. Sincronizando en segundo plano...', 'info');
      return;
    }

    mostrarToast('Conexion restaurada. Sincronizando...', 'info');
    await new Promise(r => setTimeout(r, 1500));
    try {
      const { ok, errores, omitidos } = await PWA.sincronizar();
      if (ok > 0) {
        let msg = `${ok} registro(s) sincronizado(s) correctamente.`;
        if (omitidos > 0) msg += ` (${omitidos} duplicado(s) omitido(s))`;
        mostrarToast(msg, 'success');
      }
      if (errores > 0) {
        mostrarToast(`${errores} registro(s) no pudieron sincronizarse.`, 'warning');
      }
      actualizarBadgePendientes();
    } catch (err) {
      console.error('[PWA] Error en sync automatico:', err);
    }
  });

  window.addEventListener('offline', () => {
    mostrarToast('Sin conexion. Los registros se guardaran en el dispositivo.', 'warning');
  });
});


// ═══════════════════════════════════════════════════════════
//  CACHEAR SESION TRAS LOGIN (para login offline)
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', async () => {
  const el = document.getElementById('usuario-datos');
  if (!el) return;
  try {
    const usuario = JSON.parse(el.dataset.usuario || '{}');
    if (usuario.nombre) {
      await PWA.guardarSesion(usuario);
    }
  } catch (e) { /* silencioso */ }
});


// ═══════════════════════════════════════════════════════════
//  UI -- Badge de pendientes + Toast
// ═══════════════════════════════════════════════════════════
async function actualizarBadgePendientes() {
  const n = await PWA.contarPendientes();
  const badges = document.querySelectorAll('.pwa-badge-pendientes');
  badges.forEach(b => {
    b.textContent = n;
    b.style.display = n > 0 ? 'inline-flex' : 'none';
  });
  const textos = document.querySelectorAll('.pwa-texto-pendientes');
  textos.forEach(t => {
    t.textContent = n === 0
      ? 'No hay registros pendientes de sincronizar.'
      : `${n} registro(s) pendiente(s) de sincronizar.`;
  });
}

function mostrarToast(mensaje, tipo = 'info') {
  let toast = document.getElementById('pwa-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'pwa-toast';
    toast.style.cssText = `
      position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
      z-index: 99999; padding: 13px 22px; border-radius: 12px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 13px; font-weight: 600; max-width: 90vw;
      box-shadow: 0 8px 32px rgba(0,0,0,0.2);
      transition: opacity 0.3s; display: flex; align-items: center; gap: 10px;
    `;
    document.body.appendChild(toast);
  }

  const colores = {
    success: { bg: '#d1fae5', color: '#065f46', border: '#a7f3d0' },
    warning: { bg: '#fef3c7', color: '#92400e', border: '#fde68a' },
    error:   { bg: '#fee2e2', color: '#991b1b', border: '#fca5a5' },
    info:    { bg: '#eff6ff', color: '#1e40af', border: '#bfdbfe' },
  };
  const c = colores[tipo] || colores.info;

  toast.style.background  = c.bg;
  toast.style.color       = c.color;
  toast.style.border      = `1.5px solid ${c.border}`;
  toast.textContent       = mensaje;
  toast.style.opacity     = '1';

  clearTimeout(toast._timeout);
  toast._timeout = setTimeout(() => { toast.style.opacity = '0'; }, 5000);
}

document.addEventListener('DOMContentLoaded', () => {
  actualizarBadgePendientes();
  const offlineToast = sessionStorage.getItem('offline_toast_success');
  if (offlineToast) {
      sessionStorage.removeItem('offline_toast_success');
      setTimeout(() => mostrarToast(offlineToast, 'warning'), 300);
  }
});

window.PWA_exportarCSV  = () => PWA.exportarCSV();
window.PWA_exportarJSON = () => PWA.exportarJSON();
window.PWA_sincronizar  = async () => {
  if (!navigator.onLine) {
    mostrarToast('Sin internet. No es posible sincronizar ahora.', 'error');
    return;
  }
  mostrarToast('Sincronizando...', 'info');
  const { ok, errores, omitidos } = await PWA.sincronizar();
  let msg;
  if (ok > 0) {
    msg = `${ok} registro(s) sincronizado(s).`;
    if (omitidos > 0) msg += ` (${omitidos} duplicado(s) omitido(s))`;
  } else if (errores > 0) {
    msg = `Hubo errores al sincronizar ${errores} registro(s).`;
  } else {
    msg = 'No habia registros pendientes.';
  }
  mostrarToast(msg, ok > 0 ? 'success' : 'warning');
  actualizarBadgePendientes();
};
