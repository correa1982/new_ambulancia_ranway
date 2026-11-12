"""Recorrido completo en un navegador real (Chromium), incluido el modo sin conexión.

Levanta la aplicación de verdad (con la base de pruebas) y la usa con un
navegador automático, como lo haría una persona:

1. Inicia sesión escribiendo usuario y clave en la pantalla de login.
2. Abre TODAS las páginas y revisa que ninguna tenga errores de JavaScript.
3. Para cada formulario que funciona sin conexión: corta el internet, abre el
   formulario desde la copia guardada, lo guarda en el dispositivo, devuelve
   el internet y comprueba que llegue a la base una sola vez.
4. Prueba la "señal falsa" (el celular cree que hay internet pero el servidor
   no responde) y que el preoperacional avise que no funciona sin conexión.

Necesita Playwright y su navegador (una sola vez):
    python -m pip install playwright
    python -m playwright install chromium
"""
import socket
import threading
import time
from datetime import date

import pytest

from conftest import CLAVE, USUARIOS
from test_04_recorrido import CASOS, _construir_url

sync_api = pytest.importorskip(
    "playwright.sync_api",
    reason="Falta Playwright: python -m pip install playwright  y  python -m playwright install chromium",
)

HOY = date.today().isoformat()
ESPERA_SINCRONIZACION = 60  # segundos

# Mismo criterio que pwa-offline.js para encontrar el formulario con guardado offline.
JS_LLENAR_Y_GUARDAR = """
(campos) => {
  const form = document.getElementById('form-medico') || document.getElementById('form-mci')
            || document.querySelector('.pwa-offline-form');
  if (!form) throw new Error('La página no tiene un formulario con guardado offline');
  for (const [nombre, valor] of Object.entries(campos)) {
    let campo = form.querySelector(`[name="${nombre}"]`);
    if (!campo) {
      campo = document.createElement('input');
      campo.type = 'hidden'; campo.name = nombre;
      form.appendChild(campo);
    }
    if (campo.tagName === 'SELECT' && ![...campo.options].some(o => o.value === valor)) {
      campo.add(new Option(valor, valor));
    }
    campo.value = valor;
  }
  let boton = form.querySelector('button[name="accion"][value="borrador"]');
  if (boton) {
    // "Pulsar" el botón para que corran los manejadores de la pantalla (por ejemplo, el que
    // recuerda si se eligió borrador o finalizar), pero sin el envío del navegador: el envío
    // se hace abajo, como lo hace la persona, para que lo atienda pwa-offline.js.
    const sinEnvioDelNavegador = ev => ev.preventDefault();
    boton.addEventListener('click', sinEnvioDelNavegador);
    boton.click();
    boton.removeEventListener('click', sinEnvioDelNavegador);
  } else {
    boton = document.createElement('button');
    boton.type = 'submit'; boton.name = 'accion'; boton.value = 'borrador'; boton.hidden = true;
    form.appendChild(boton);
  }
  form.dispatchEvent(new SubmitEvent('submit', { bubbles: true, cancelable: true, submitter: boton }));
}
"""


# ── Servidor de la aplicación para el navegador ────────────────────────────
class ServidorDePrueba:
    """La aplicación escuchando en 127.0.0.1. Se puede apagar para simular que no hay internet."""

    def __init__(self, app):
        from werkzeug.serving import WSGIRequestHandler

        class _SinConexionPersistente(WSGIRequestHandler):
            # HTTP/1.0: cada petición abre su propia conexión, así al apagar el
            # servidor no queda ninguna conexión abierta que siga respondiendo.
            protocol_version = "HTTP/1.0"

            def log_message(self, *args):
                pass

        self.app = app
        self._manejador = _SinConexionPersistente
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.puerto = s.getsockname()[1]
        self._servidor = None

    @property
    def url(self):
        return f"http://127.0.0.1:{self.puerto}"

    def iniciar(self):
        from werkzeug.serving import make_server
        if self._servidor is None:
            # Una petición a la vez, igual que gunicorn en Railway (sin hilos). Con varias a la vez,
            # el grupo de conexiones a MySQL (máximo 10) se bloquea: ver hallazgo SQL-03 en
            # docs/auditoria/hallazgos.md.
            self._servidor = make_server("127.0.0.1", self.puerto, self.app, threaded=False,
                                         request_handler=self._manejador)
            threading.Thread(target=self._servidor.serve_forever, daemon=True).start()

    def detener(self):
        if self._servidor is not None:
            self._servidor.shutdown()
            self._servidor.server_close()
            self._servidor = None


def esperar(condicion, segundos, que):
    limite = time.time() + segundos
    ultimo_error = None
    while time.time() < limite:
        try:
            if condicion():
                return
        except Exception as error:  # la página puede estar recargando
            ultimo_error = error
        time.sleep(0.3)
    raise AssertionError(f"Pasaron {segundos} s y no ocurrió: {que}" + (f" ({ultimo_error})" if ultimo_error else ""))


# ── Fixtures ───────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def servidor(app):
    s = ServidorDePrueba(app)
    s.iniciar()
    yield s
    s.detener()


@pytest.fixture(scope="module")
def navegador():
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as error:
            pytest.fail("No se pudo abrir el navegador de pruebas. Instálalo con: "
                        f"python -m playwright install chromium\n{error}")
        yield browser
        browser.close()


class _Sesion:
    def __init__(self, contexto, pagina):
        self.contexto = contexto
        self.pagina = pagina
        self.errores_js = []
        pagina.on("pageerror", lambda error: self.errores_js.append(str(error)))

    def pendientes(self):
        return self.pagina.evaluate("PWA.contarPendientes()")


def _abrir_sesion(navegador, servidor, rol):
    contexto = navegador.new_context(base_url=servidor.url, viewport={"width": 412, "height": 900})
    contexto.set_default_timeout(30000)
    pagina = contexto.new_page()
    sesion = _Sesion(contexto, pagina)
    pagina.goto("/")
    pagina.fill("input[name=identificacion]", USUARIOS[rol]["identificacion"])
    pagina.fill("input[name=contrasena]", CLAVE)
    pagina.press("input[name=contrasena]", "Enter")
    pagina.wait_for_url("**/dashboard")
    return sesion


@pytest.fixture(scope="module")
def sesion_admin(navegador, servidor):
    sesion = _abrir_sesion(navegador, servidor, "admin")
    yield sesion
    sesion.contexto.close()


@pytest.fixture(scope="module")
def sesion_offline(navegador, servidor):
    """Sesión para el modo sin conexión, con el service worker ya activo y las páginas guardadas."""
    sesion = _abrir_sesion(navegador, servidor, "operativo")
    pagina = sesion.pagina
    esperar(lambda: pagina.evaluate("!!navigator.serviceWorker.controller"), 90,
            "que el service worker tome el control de la página")
    esperar(lambda: pagina.evaluate("caches.match('/formulario').then(r => !!r && !r.redirected)"), 90,
            "que el service worker guarde las páginas después del login")
    yield sesion
    sesion.contexto.close()


# ── 1. Inicio de sesión y dashboard ────────────────────────────────────────
def test_login_y_dashboard_sin_errores(sesion_admin):
    assert "/dashboard" in sesion_admin.pagina.url
    assert not sesion_admin.errores_js, f"Errores de JavaScript en el dashboard: {sesion_admin.errores_js}"


# ── 2. Todas las páginas en el navegador ───────────────────────────────────
@pytest.mark.parametrize("endpoint,regla,fijos", CASOS)
def test_pagina_en_navegador(endpoint, regla, fijos, sesion_admin, bd, modulo_app):
    url = _construir_url(endpoint, regla, fijos, bd, modulo_app)
    pagina = sesion_admin.pagina

    # Descargas (Excel, archivos) y datos (JSON): solo se revisa que el servidor no falle.
    previa = pagina.request.get(url, max_redirects=5)
    assert previa.status < 500, f"{url} respondió {previa.status}"
    if "text/html" not in previa.headers.get("content-type", ""):
        return

    sesion_admin.errores_js.clear()
    respuesta = pagina.goto(url, wait_until="load")
    assert respuesta is None or respuesta.status < 500, f"{url} respondió {respuesta.status}"
    pagina.wait_for_timeout(300)  # scripts que corren apenas carga la página
    assert not sesion_admin.errores_js, f"Errores de JavaScript en {url}: {sesion_admin.errores_js}"


# ── 3. Modo sin conexión: cada formulario ──────────────────────────────────
FORMULARIOS_OFFLINE = [
    ("historia_clinica", "/formulario", "pacientes",
     {"tipo_documento": "CC", "identificacion_paciente": "3000000001", "primer_nombre": "Offline",
      "primer_apellido": "Navegador", "fecha_inicio_atencion": f"{HOY}T08:00"},
     ("identificacion_paciente", "3000000001")),
    ("eventos", "/formularios/eventos", "eventos",
     {"fecha_inicio": HOY, "hora_inicio": "08:00", "tipo_evento": "Offline navegador"},
     ("tipo_evento", "Offline navegador")),
    ("atencion_vehiculo", "/formularios/atencion_vehiculo", "atencion_vehiculo",
     {"descripcion": "Offline navegador", "tipo": "Prueba"},
     ("descripcion", "Offline navegador")),
    ("reporte_gasto", "/reporte_gasto/nuevo", "reporte_gasto",
     {"fecha": HOY, "nombre_evento": "Offline navegador"},
     ("nombre_evento", "Offline navegador")),
] + [
    (f"checklist_{tipo}", f"/checklist/{tipo}", tabla, {"fecha": HOY, "hora": "08:00"}, None)
    for tipo, tabla in [("tam", "checklist_tam"), ("tab", "checklist_tab"), ("avanzada", "checklist_avanzada"),
                        ("pasb", "checklist_pasb"), ("pasm", "checklist_pasm"), ("equipos", "checklist_equipos"),
                        ("calif_atencion", "calif_atencion"), ("segur_paciente", "segur_paciente")]
]


@pytest.mark.parametrize("nombre,url,tabla,campos,marcador", FORMULARIOS_OFFLINE,
                         ids=[f[0] for f in FORMULARIOS_OFFLINE])
def test_formulario_sin_conexion(nombre, url, tabla, campos, marcador, sesion_offline, servidor, bd):
    pagina, contexto = sesion_offline.pagina, sesion_offline.contexto
    antes = bd.contar(tabla)

    # Con internet: se abre el formulario (queda guardado en el dispositivo).
    pagina.goto(url, wait_until="load")
    esperar(lambda: pagina.evaluate("u => caches.match(u).then(r => !!r && !r.redirected)", url), 30,
            f"que {url} quede guardado para uso offline")
    pendientes_antes = sesion_offline.pendientes()

    # Sin internet: se abre desde la copia y se guarda en el dispositivo.
    contexto.set_offline(True)
    servidor.detener()
    try:
        pagina.reload(wait_until="load")
        assert pagina.evaluate("!!(document.getElementById('form-medico') || document.getElementById('form-mci')"
                               " || document.querySelector('.pwa-offline-form'))"), \
            f"Sin conexión, {url} no abrió el formulario (¿mostró la página de error?)"
        pagina.evaluate(JS_LLENAR_Y_GUARDAR, campos)
        esperar(lambda: sesion_offline.pendientes() == pendientes_antes + 1, 20,
                f"que {nombre} quede guardado en el dispositivo")
        assert bd.contar(tabla) == antes, "Sin conexión no debería llegar nada a la base"
    finally:
        servidor.iniciar()
        contexto.set_offline(False)

    # Vuelve el internet: se sincroniza solo, una sola vez.
    esperar(lambda: sesion_offline.pendientes() == 0, ESPERA_SINCRONIZACION,
            f"que {nombre} se sincronice al volver internet")
    if marcador:
        columna, valor = marcador
        assert bd.contar(tabla, f"`{columna}` = ?", (valor,)) == 1, \
            f"{nombre}: el registro debe quedar en la base exactamente una vez"
    else:
        assert bd.contar(tabla) == antes + 1, f"{nombre}: el registro debe quedar en la base exactamente una vez"


def test_senal_falsa_guarda_en_el_dispositivo_y_sincroniza_al_abrir(sesion_offline, servidor, bd):
    """El celular cree que hay internet, pero el servidor no responde (señal débil)."""
    pagina = sesion_offline.pagina
    pagina.goto("/formulario", wait_until="load")
    pendientes_antes = sesion_offline.pendientes()

    servidor.detener()  # sin cortar el internet del navegador
    try:
        pagina.evaluate(JS_LLENAR_Y_GUARDAR, {
            "tipo_documento": "CC", "identificacion_paciente": "3000000099", "primer_nombre": "Senal",
            "primer_apellido": "Falsa", "fecha_inicio_atencion": f"{HOY}T09:00"})
        esperar(lambda: sesion_offline.pendientes() == pendientes_antes + 1, 20,
                "que con señal falsa el registro quede guardado en el dispositivo")
    finally:
        servidor.iniciar()

    # No hay evento "volvió internet" (el navegador nunca lo perdió): se sincroniza al abrir la app.
    pagina.reload(wait_until="load")
    esperar(lambda: sesion_offline.pendientes() == 0, ESPERA_SINCRONIZACION,
            "que se sincronice al abrir la app con internet")
    assert bd.contar("pacientes", "identificacion_paciente = ?", ("3000000099",)) == 1


def test_preoperacional_sin_conexion_avisa(sesion_offline, servidor):
    """El preoperacional no guarda sin conexión: debe avisar en vez de dejar llenar y perder los datos."""
    pagina, contexto = sesion_offline.pagina, sesion_offline.contexto
    pagina.goto("/preoperacional", wait_until="load")
    contexto.set_offline(True)
    servidor.detener()
    try:
        pagina.reload(wait_until="load")
        assert "Sin conexión" in pagina.content(), "Sin conexión el preoperacional debería mostrar el aviso"
    finally:
        servidor.iniciar()
        contexto.set_offline(False)
