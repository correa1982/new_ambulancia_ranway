// ═══════════════════════════════════════════════════════════
//  pwa-offline.js — Lógica offline para Ambulacia
//  Incluir en base.html con: <script src="/static/pwa-offline.js"></script>
// ═══════════════════════════════════════════════════════════

const PWA = (() => {
  const DB_NAME    = 'ambulacia-offline';
  const DB_VERSION = 1;
  let   _db        = null;

  // ── Abrir / inicializar IndexedDB ────────────────────────
  function abrirDB() {
    if (_db) return Promise.resolve(_db);
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = e => {
        const db = e.target.result;
        // Tabla de registros offline
        if (!db.objectStoreNames.contains('registros')) {
          const store = db.createObjectStore('registros', { keyPath: 'id', autoIncrement: true });
          store.createIndex('sincronizado', 'sincronizado', { unique: false });
          store.createIndex('fecha_creacion', 'fecha_creacion', { unique: false });
        }
        // Sesión cacheada para login offline
        if (!db.objectStoreNames.contains('sesion')) {
          db.createObjectStore('sesion', { keyPath: 'key' });
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
      tx.objectStore('sesion').put({ key: 'usuario_activo', ...usuario });
      tx.oncomplete = resolve;
      tx.onerror    = e => reject(e.target.error);
    });
  }

  // ── Leer sesión cacheada ─────────────────────────────────
  async function leerSesion() {
    const db = await abrirDB();
    return new Promise((resolve, reject) => {
      const req = db.transaction('sesion', 'readonly')
                    .objectStore('sesion').get('usuario_activo');
      req.onsuccess = e => resolve(e.target.result || null);
      req.onerror   = e => reject(e.target.error);
    });
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
      fecha_creacion: new Date().toISOString(),
      registrado_por: sesion ? sesion.nombre        : 'Desconocido',
      identificacion: sesion ? sesion.identificacion : '',
      perfil:         sesion ? sesion.perfil : '',
    };
    return new Promise((resolve, reject) => {
      const tx  = db.transaction('registros', 'readwrite');
      const req = tx.objectStore('registros').add(registro);
      req.onsuccess = e => resolve(e.target.result); // ID generado
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
    const sesion = await leerSesion();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('registros', 'readwrite');
      const store = tx.objectStore('registros');
      const req = store.get(numericId);
      req.onsuccess = e => {
        const registro = e.target.result;
        if (!registro) {
            reject('Registro no encontrado');
            return;
        }
        registro.datos = datos;
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

  let isSyncing = false;

  // ── Sincronizar con el servidor ──────────────────────────
  async function sincronizar() {
    if (isSyncing) return { ok: 0, errores: 0 };
    isSyncing = true;
    
    try {
      const pendientes = await obtenerPendientes();
      if (pendientes.length === 0) return { ok: 0, errores: 0 };

      let ok = 0, errores = 0;

    for (const registro of pendientes) {
      try {
        const formData = new FormData();
        // Marcar como proveniente de sync offline
        formData.append('_offline_sync', '1');
        formData.append('_offline_id',   registro.id);

        for (const [key, val] of Object.entries(registro.datos)) {
          if (val !== null && val !== undefined && val !== '') {
            formData.append(key, val);
          }
        }

        let urlPost = '/formulario';
        const acId = registro.datos.atencion_colectiva_id;
        if (acId && acId !== 'None' && acId !== 'null' && acId !== 'undefined' && acId !== '') {
          urlPost = '/formulario_mci?atencion_colectiva_id=' + encodeURIComponent(acId);
        }

        const resp = await fetch(urlPost, {
          method: 'POST',
          body: formData,
          credentials: 'same-origin'
        });

        let data = {};
        try { data = await resp.json(); } catch(e) {}

        if (resp.ok && data.status === 'success') {
          await marcarSincronizado(registro.id);
          ok++;
        } else {
          errores++;
          if (resp.status === 401) {
            console.error('[PWA] Sesión expirada al sincronizar. Por favor inicie sesión nuevamente.');
          } else {
            console.error('[PWA] Error servidor al sincronizar', data);
          }
        }
      } catch (err) {
        errores++;
        console.error('[PWA] Error sync registro', registro.id, err);
      }
    }
    return { ok, errores };
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

    // Cabeceras — todos los campos del formulario
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
        r.sincronizado ? 'Sí' : 'No',
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
    exportarCSV, exportarJSON, contarPendientes,
  };
})();


// ═══════════════════════════════════════════════════════════
//  REGISTRO DEL SERVICE WORKER
// ═══════════════════════════════════════════════════════════
if ('serviceWorker' in navigator) {
  window.addEventListener('load', async () => {
    try {
      const reg = await navigator.serviceWorker.register('/sw.js?v=47', { scope: '/' });
      console.log('[PWA] Service Worker registrado:', reg.scope);

      // Escuchar mensajes de sync del SW
      navigator.serviceWorker.addEventListener('message', event => {
        if (event.data?.type === 'SYNC_SUCCESS') {
          mostrarToast(`✅ Sincronizado: ${event.data.paciente}`, 'success');
          actualizarBadgePendientes();
        }
      });
    } catch (err) {
      console.error('[PWA] Error registrando SW:', err);
    }
  });
}


// ═══════════════════════════════════════════════════════════
//  INTERCEPTAR EL FORMULARIO DE HISTORIA CLÍNICA
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('form-medico') || document.getElementById('form-mci');
  if (!form) return; // Solo actuar en la página del formulario

  // ── Interceptar submit cuando no hay internet ────────────
  form.addEventListener('submit', async function(e) {
    e.preventDefault(); // Interceptamos siempre primero

    // Obtener los datos del formulario
    const datos = {};
    const fd    = new FormData(form);
    
    // Capturar el botón que se presionó (o el hidden_input inyectado)
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

    // --- VALIDACIÓN DE CAMPOS VACÍOS ---
    let hasData = false;
    const textInputs = form.querySelectorAll('input[type="text"], input[type="number"], textarea');
    textInputs.forEach(input => {
        if (input.name && input.value && input.value.trim() !== '' && input.id !== 'cie10-search' && input.id !== 'cie10-search-mci') {
            hasData = true;
        }
    });

    if (!hasData) {
        mostrarToast('⚠️ No se puede guardar. Diligencie al menos un campo de texto.', 'error');
        const btns = form.querySelectorAll('button[type="submit"], button.btn-submit');
        btns.forEach(btn => {
            btn.disabled = false;
            if (btn.value === 'guardar_continuar') btn.innerHTML = '💾 Guardar y Continuar';
            else if (btn.value === 'borrador') btn.innerHTML = '📝 Guardar como Borrador';
            else if (btn.value === 'guardar') btn.innerHTML = '💾 Guardar Historia';
            else if (btn.id === 'guardar-continuar-btn') btn.innerHTML = '💾 Guardar y Continuar';
        });
        return;
    }
    // -----------------------------------

    if (navigator.onLine) {
        try {
            // Ping rápido para verificar si el servidor Flask realmente responde
            // Usamos un endpoint estático ligero, ignorando el SW
            const resp = await fetch('/static/manifest.json?_sw_bypass=1&t=' + Date.now(), { method: 'HEAD', cache: 'no-store' });
            if (!resp.ok) throw new Error('Servidor inaccesible (status ' + resp.status + ')');
            
            // Si responde, hay conexión real. Enviamos el formulario normalmente.
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

    // --- MODO OFFLINE (guardado en IndexedDB) ---
    // Extraer FormData manejando arrays (ej: checkboxes, campos dinámicos con el mismo nombre)
    for (let key of fd.keys()) {
        const values = fd.getAll(key);
        // Si el nombre termina en [] O tiene múltiples valores, forzar a array
        if (key.endsWith('[]') || values.length > 1) {
            datos[key] = values;
        } else {
            datos[key] = values[0];
        }
    }

    // Capturar campo CIE10 (es hidden con id cie10-value o cie10-value-mci)
    const cie10Hidden = document.getElementById('cie10-value') || document.getElementById('cie10-value-mci');
    if (cie10Hidden) datos['diagnostico_cie10'] = cie10Hidden.value;

    // Sanear atencion_colectiva_id para evitar strings de Jinja 'None'/'null'
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
        mostrarToast(`💾 Registro #${id} actualizado offline.`, 'warning');
        // Salir del modo edición sin mostrar toast de cancelación
        if (window.cancelarEdicionOffline) window.cancelarEdicionOffline(false);
      } else {
        id = await PWA.guardarRegistroOffline(datos);
        if (accionValue === 'finalizar') {
            sessionStorage.setItem('offline_toast_success', `💾 Registro finalizado offline #${id}. Se sincronizará al tener conexión.`);
        } else {
            mostrarToast(`💾 Guardado offline #${id}. Se sincronizará cuando haya internet.`, 'warning');
        }
        form.reset();
      }

      // Cerrar modal de finalizar si está abierto
      const modalConfirmar = document.getElementById('modal-confirmar-finalizar');
      if (modalConfirmar) {
          modalConfirmar.style.display = 'none';
          document.body.style.overflow = '';
      }
      const modalAceptar = document.getElementById('modal-aceptar-finalizar');
      if (modalAceptar) {
          modalAceptar.disabled = false;
          modalAceptar.innerHTML = '✅ Sí, Finalizar';
      }
      const modalCancelar = document.getElementById('modal-cancelar-finalizar');
      if (modalCancelar) modalCancelar.disabled = false;
      const finalizarBtn = document.getElementById('finalizar-btn');
      if (finalizarBtn) {
          finalizarBtn.disabled = false;
          finalizarBtn.innerHTML = '🔒 Finalizar Historia Clínica';
      }

      // Resetear edad y CIE10 (por si form.reset no lo hizo bien)
      const edadEl = document.getElementById('edad');
      if (edadEl) edadEl.value = '';
      const cie10El = document.getElementById('cie10-search');
      if (cie10El) cie10El.value = '';
      const cie10Hidden = document.getElementById('cie10-value');
      if (cie10Hidden) cie10Hidden.value = '';
      
      // Volver al paso 1 del formulario (si existe la función) y hacer scroll arriba
      if (typeof window.showStep === 'function') {
          window.showStep(1);
      }
      window.scrollTo({ top: 0, behavior: 'smooth' });
      
      // Re-habilitar botones y restaurar texto original para poder seguir guardando offline
      const btns = form.querySelectorAll('button[type="submit"], button.btn-submit');
      btns.forEach(btn => {
        btn.disabled = false;
        if (btn.value === 'guardar_continuar') btn.innerHTML = '💾 Guardar y Continuar';
        else if (btn.value === 'borrador') btn.innerHTML = '📝 Guardar como Borrador';
        else if (btn.value === 'guardar') btn.innerHTML = '💾 Guardar Historia';
        else if (btn.id === 'guardar-continuar-btn') btn.innerHTML = '💾 Guardar y Continuar';
      });

      actualizarBadgePendientes();
      if (window.cargarRegistrosOfflinePanel) window.cargarRegistrosOfflinePanel();

      // Registrar tarea de sync para cuando vuelva internet
      if ('serviceWorker' in navigator && 'SyncManager' in window) {
        const sw = await navigator.serviceWorker.ready;
        await sw.sync.register('sync-registros');
      }

      // Si la acción era finalizar, redirigir igual que el comportamiento online
      if (accionValue === 'finalizar') {
          const params = new URLSearchParams(window.location.search);
          const acId = params.get('atencion_colectiva_id');
          if (acId) window.location.href = '/formulario_mci?atencion_colectiva_id=' + encodeURIComponent(acId);
          else window.location.href = '/dashboard';
      }
    } catch (err) {
      console.error('[PWA] Error guardando offline:', err);
      mostrarToast('❌ Error al guardar offline. Intente nuevamente.', 'error');
      // Re-habilitar botones en caso de error
      const btns = form.querySelectorAll('button[type="submit"], button.btn-submit');
      btns.forEach(btn => { btn.disabled = false; });
    }
  });

  // ── Cuando vuelve internet: sincronizar automáticamente ──
  window.addEventListener('online', async () => {
    // Si el navegador soporta Background Sync, dejamos que el Service Worker se encargue
    if ('serviceWorker' in navigator && 'SyncManager' in window) {
      mostrarToast('🌐 Conexión restaurada. Sincronizando en segundo plano...', 'info');
      return;
    }

    mostrarToast('🌐 Conexión restaurada. Sincronizando...', 'info');
    await new Promise(r => setTimeout(r, 1500)); // Esperar estabilidad
    try {
      const { ok, errores } = await PWA.sincronizar();
      if (ok > 0) {
        mostrarToast(`✅ ${ok} registro(s) sincronizado(s) correctamente.`, 'success');
      }
      if (errores > 0) {
        mostrarToast(`⚠️ ${errores} registro(s) no pudieron sincronizarse.`, 'warning');
      }
      actualizarBadgePendientes();
    } catch (err) {
      console.error('[PWA] Error en sync automático:', err);
    }
  });

  window.addEventListener('offline', () => {
    mostrarToast('📡 Sin conexión. Los registros se guardarán en el dispositivo.', 'warning');
  });
});


// ═══════════════════════════════════════════════════════════
//  CACHEAR SESIÓN TRAS LOGIN (para login offline)
// ═══════════════════════════════════════════════════════════
// Llamar esto desde la página que renderiza al usuario logueado
// Se llama automáticamente si existe el elemento #usuario-datos
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
//  UI — Badge de pendientes + Toast
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

// ── Inicializar badge al cargar cualquier página ──────────
document.addEventListener('DOMContentLoaded', () => {
  actualizarBadgePendientes();
  const offlineToast = sessionStorage.getItem('offline_toast_success');
  if (offlineToast) {
      sessionStorage.removeItem('offline_toast_success');
      setTimeout(() => mostrarToast(offlineToast, 'warning'), 300);
  }
});

// Exponer funciones para botones en templates
window.PWA_exportarCSV  = () => PWA.exportarCSV();
window.PWA_exportarJSON = () => PWA.exportarJSON();
window.PWA_sincronizar  = async () => {
  if (!navigator.onLine) {
    mostrarToast('❌ Sin internet. No es posible sincronizar ahora.', 'error');
    return;
  }
  mostrarToast('🔄 Sincronizando...', 'info');
  const { ok, errores } = await PWA.sincronizar();
  mostrarToast(
    ok > 0
      ? `✅ ${ok} registro(s) sincronizado(s).`
      : errores > 0
        ? `⚠️ Hubo errores al sincronizar ${errores} registro(s).`
        : 'No había registros pendientes.',
    ok > 0 ? 'success' : 'warning'
  );
  actualizarBadgePendientes();
};
