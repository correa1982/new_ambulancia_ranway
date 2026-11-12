"""Seguridad: rutas que cambian datos, token CSRF, archivos y contraseñas."""
import re

import pytest

from conftest import USUARIOS, cargar_modulo_app, enviar, sin_error_de_servidor

# Envíos (POST) que se pueden hacer sin sesión, a propósito.
POST_PUBLICOS = {"login", "recuperar_contrasena", "nomina.nomina_consulta", "seleccionar_perfil",
                 "cambiar_contrasena"}

_PARAMETRO = re.compile(r"<(?:([^:<>]+):)?([^<>]+)>")


def _url_de_prueba(regla):
    """Reemplaza los parámetros de la ruta por valores que no existen."""
    def valor(m):
        convertidor = m.group(1) or "string"
        if convertidor == "int":
            return "999999"
        if m.group(2) == "tipo":
            return "tam"
        return "no_existe"
    return _PARAMETRO.sub(valor, regla)


def _rutas_post():
    modulo = cargar_modulo_app()
    reglas = [r for r in modulo.app.url_map.iter_rules() if "POST" in r.methods and r.endpoint != "static"]
    return [pytest.param(r.endpoint, r.rule, id=r.rule) for r in sorted(reglas, key=lambda r: r.rule)]


@pytest.mark.parametrize("endpoint,regla", _rutas_post())
def test_envio_sin_sesion_es_rechazado(endpoint, regla, app):
    """Nadie sin sesión puede guardar, cambiar o borrar datos (aunque traiga el token CSRF)."""
    cliente = app.test_client()
    respuesta = enviar(cliente, _url_de_prueba(regla), {})
    assert sin_error_de_servidor(respuesta), f"{regla} respondió {respuesta.status_code}"
    if endpoint not in POST_PUBLICOS:
        assert respuesta.status_code != 200, f"{regla} aceptó un envío sin sesión"


def test_envio_sin_token_csrf_es_rechazado(cliente_operativo, bd):
    antes = bd.contar("eventos")
    respuesta = cliente_operativo.post("/formularios/eventos", data={"tipo_evento": "Sin token"})
    assert respuesta.status_code == 400
    assert bd.contar("eventos") == antes


def test_envio_con_token_falso_es_rechazado(cliente_operativo, bd):
    antes = bd.contar("eventos")
    respuesta = cliente_operativo.post("/formularios/eventos",
                                       data={"tipo_evento": "Token falso", "csrf_token": "falso"})
    assert respuesta.status_code == 400
    assert bd.contar("eventos") == antes


def test_ruta_que_cambia_datos_desde_otro_sitio_es_rechazada(cliente_admin, bd):
    """Un enlace en otro sitio no puede desactivar usuarios usando la sesión del administrador."""
    usuario = bd.uno("SELECT id, activo FROM usuarios WHERE identificacion = ?",
                     (USUARIOS["sin_permisos"]["identificacion"],))
    respuesta = cliente_admin.get(f"/usuarios/toggle/{usuario['id']}",
                                  headers={"Referer": "https://sitio-malicioso.example/pagina"})
    assert respuesta.status_code == 403
    despues = bd.uno("SELECT activo FROM usuarios WHERE id = ?", (usuario["id"],))
    assert despues["activo"] == usuario["activo"]


def test_ruta_que_cambia_datos_sin_sesion_no_cambia_nada(app, bd):
    usuario = bd.uno("SELECT id, activo FROM usuarios WHERE identificacion = ?",
                     (USUARIOS["sin_permisos"]["identificacion"],))
    respuesta = app.test_client().get(f"/usuarios/toggle/{usuario['id']}")
    assert respuesta.status_code != 200
    assert bd.uno("SELECT activo FROM usuarios WHERE id = ?", (usuario["id"],))["activo"] == usuario["activo"]


def test_usuario_operativo_no_puede_agregar_vehiculos(cliente_operativo, bd):
    antes = bd.contar("vehiculos")
    enviar(cliente_operativo, "/admin/vehiculos/agregar", {"tipo": "Ambulancia", "placa": "HAC999"})
    assert bd.contar("vehiculos") == antes


@pytest.mark.parametrize("url", [
    "/static/uploads/archivador/../../../app.py",
    "/static/uploads/archivador/..%2F..%2F..%2Fapp.py",
    "/static/uploads/evidencias/..%2F..%2F..%2F.env",
    "/static/uploads/nomina/..%2F..%2F..%2Fdb.py",
    "/nomina/download/..%2F..%2Fapp.py",
])
def test_no_se_pueden_descargar_archivos_del_servidor(url, cliente_admin):
    respuesta = cliente_admin.get(url)
    assert sin_error_de_servidor(respuesta)
    contenido = respuesta.get_data(as_text=True)
    assert "SECRET_KEY" not in contenido and "def register_routes" not in contenido \
        and "import pymysql" not in contenido, f"{url} entregó un archivo del servidor"


def test_contrasenas_guardadas_como_hash(bd):
    filas = bd.todos("SELECT identificacion, contrasena FROM usuarios")
    for fila in filas:
        assert fila["contrasena"] and fila["contrasena"].startswith(("scrypt:", "pbkdf2:")), \
            f"La contraseña del usuario {fila['identificacion']} no está protegida con hash"


def test_cookie_de_sesion_protegida(cliente):
    from conftest import iniciar_sesion
    respuesta = iniciar_sesion(cliente, "operativo")
    cookies = respuesta.headers.getlist("Set-Cookie")
    sesion = [c for c in cookies if c.startswith("session=")]
    assert sesion, "No se creó la cookie de sesión"
    assert "HttpOnly" in sesion[0]
