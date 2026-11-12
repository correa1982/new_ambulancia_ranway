// Prueba del service worker (static/sw.js) en un navegador simulado.
// Uso: node tests/js/sw.test.js [ruta/a/sw.js]
// Lo ejecuta automáticamente tests/test_06_offline.py.
const fs = require('fs'), vm = require('vm'), path = require('path');
const rutaSw = process.argv[2] || path.join(__dirname, '..', '..', 'static', 'sw.js');
const codigo = fs.readFileSync(rutaSw, 'utf8');
if (!codigo.includes('const RED_LENTA_MS = 5000;')) { console.log('FALLA  No se encontró RED_LENTA_MS en sw.js'); process.exit(1); }
const src = codigo.replace('const RED_LENTA_MS = 5000;', 'const RED_LENTA_MS = 100;');
const ORIGIN = 'https://app.test';
function mkResp(body, {status=200, redirected=false, type='basic'}={}) {
  return { body, status, ok: status>=200&&status<300, redirected, type, clone(){ return mkResp(body,{status,redirected,type}); } };
}
const store = {};
const keyOf = (r) => (typeof r === 'string' ? new URL(r, ORIGIN).href : r.url);
const cacheObj = { put: async (r, resp) => { store[keyOf(r)] = resp; } };
const caches = {
  open: async () => cacheObj, keys: async () => ['sga-v89'], delete: async () => true,
  match: async (r, opts={}) => {
    const k = keyOf(r);
    if (store[k]) return store[k];
    if (opts.ignoreSearch) { const base = k.split('?')[0]; for (const kk in store) if (kk.split('?')[0] === base) return store[kk]; }
    return undefined;
  }
};
let fetchImpl;
const listeners = {};
const self = { addEventListener: (t, f) => listeners[t] = f, skipWaiting: async()=>{}, clients: { claim: async()=>{}, matchAll: async()=>[] } };
const ctx = { self, caches, fetch: (...a) => fetchImpl(...a), Response: function(body, init){ return mkResp(body, init); },
  Request: function(url){ return { url: new URL(url, ORIGIN).href }; }, URL, location: { origin: ORIGIN },
  setTimeout, clearTimeout, console: { warn(){}, log(){}, error(){} }, Promise, Set, AbortController, FormData: class{} };
vm.createContext(ctx); vm.runInContext(src, ctx);

function evento(path, {mode='navigate', method='GET'}={}) {
  const req = { url: ORIGIN + path, method, mode, headers: { get: h => h==='accept' ? 'text/html' : null } };
  let p; return { request: req, respondWith: x => p = x, waitUntil(){}, get resultado(){ return p; } };
}
const espera = ms => new Promise(r => setTimeout(r, ms));
let fallos = 0;
function ok(cond, nombre) { console.log((cond ? 'PASA ' : 'FALLA') + '  ' + nombre); if (!cond) fallos++; }

(async () => {
  // Instalación desde el login (sin sesión): las páginas redirigen al login
  let sinCerrar = 0, cerradas = 0;
  fetchImpl = async (req) => {
    const u = req.url || req;
    if (/\/static\//.test(u)) return mkResp('archivo');
    const r = mkResp('LOGIN', {redirected: true});
    sinCerrar++;
    r.body = { cancel: () => { cerradas++; return Promise.resolve(); } };
    return r;
  };
  let instalado; listeners.install({ waitUntil: p => instalado = p }); await instalado;
  ok(sinCerrar > 0 && cerradas === sinCerrar,
     `Instalación sin sesión: cierra las respuestas descartadas (${cerradas} de ${sinCerrar}); si no, el navegador se queda sin conexiones`);
  ok(!store[ORIGIN + '/formulario'], 'Instalación sin sesión: no guarda el login como si fuera /formulario');
  ok(!store[ORIGIN + '/api/cie10_full'], 'Instalación sin sesión: no guarda el login como si fuera CIE-10');
  ok(!!store[ORIGIN + '/static/offline.html?v=3'], 'Instalación: guarda la página offline');

  // Después del login: la página pide guardar las páginas
  fetchImpl = async (req) => mkResp('PAGINA ' + (req.url || req));
  let respuesta; let hecho;
  listeners.message({ data: { type: 'PRECACHE_PAGINAS' }, ports: [{ postMessage: m => respuesta = m }], waitUntil: p => hecho = p }); await hecho;
  ok(store[ORIGIN + '/formulario'] && store[ORIGIN + '/formulario'].body.startsWith('PAGINA'), 'Con sesión: guarda /formulario real');
  ok(respuesta && respuesta.fallidos.length === 0, 'Con sesión: responde a la página sin fallidos');

  // Sin conexión: usa la copia
  fetchImpl = async () => { throw new TypeError('Failed to fetch'); };
  let e = evento('/formulario'); listeners.fetch(e); let r = await e.resultado;
  ok(r.body.startsWith('PAGINA'), 'Sin conexión: abre /formulario desde la copia');

  // Copia vieja que era una redirección (guardada por la versión anterior)
  store[ORIGIN + '/checklist/tam'] = mkResp('LOGIN', {redirected: true});
  e = evento('/checklist/tam'); listeners.fetch(e); r = await e.resultado;
  ok(r === store[ORIGIN + '/static/offline.html?v=3'], 'Sin conexión: una copia que era el login no se usa; muestra el aviso offline');

  // Formulario que no guarda offline: aviso en vez del formulario
  store[ORIGIN + '/checklist/preoperacional'] = mkResp('PAGINA preop');
  e = evento('/checklist/preoperacional'); listeners.fetch(e); r = await e.resultado;
  ok(r === store[ORIGIN + '/static/offline.html?v=3'], 'Sin conexión: preoperacional muestra el aviso (su envío se perdería)');

  // Señal débil: la red no responde
  fetchImpl = () => new Promise(() => {});
  e = evento('/formulario'); listeners.fetch(e);
  const t0 = Date.now(); r = await e.resultado;
  ok(r.body.startsWith('PAGINA') && Date.now() - t0 < 1000, 'Señal débil: muestra la copia tras el límite en vez de quedarse esperando');

  // Señal débil sin copia: espera a la red (no inventa)
  let resolver; fetchImpl = () => new Promise(res => resolver = res);
  e = evento('/pagina-nueva'); listeners.fetch(e);
  setTimeout(() => resolver(mkResp('RED tarde')), 300);
  r = await e.resultado;
  ok(r.body === 'RED tarde', 'Señal débil sin copia: espera la respuesta de la red');

  // En línea: respuesta redirigida (sesión vencida) no reemplaza la copia buena
  const antes = store[ORIGIN + '/formulario'];
  fetchImpl = async () => mkResp('LOGIN', {redirected: true});
  e = evento('/formulario'); listeners.fetch(e); r = await e.resultado; await espera(20);
  ok(store[ORIGIN + '/formulario'] === antes, 'Sesión vencida en línea: no se pisa la copia buena con el login');

  // En línea normal: se actualiza la copia
  fetchImpl = async () => mkResp('PAGINA nueva');
  e = evento('/formulario'); listeners.fetch(e); r = await e.resultado; await espera(20);
  ok(r.body === 'PAGINA nueva' && store[ORIGIN + '/formulario'].body === 'PAGINA nueva', 'En línea: muestra la red y actualiza la copia');

  console.log(fallos ? `\n${fallos} prueba(s) fallaron` : '\nTodas las pruebas pasaron');
  process.exit(fallos ? 1 : 0);
})();
