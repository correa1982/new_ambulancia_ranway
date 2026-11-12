"""Recorre TODAS las páginas de la aplicación con cada tipo de usuario.

La lista de páginas no está escrita a mano: se toma de la aplicación misma
(todas las rutas que responden a GET). Si se agrega una página nueva, entra
sola en el recorrido.

Para cada página se revisa:
- Administrador y usuario operativo: que no haya error interno (500).
- Usuario operativo: que no pueda ver las páginas solo de administrador.
- Sin sesión: que solo se vean las páginas públicas; el resto lleva al login.

No se recorren las rutas GET que cambian datos (eliminar, activar/desactivar,
restablecer clave, cerrar sesión...): se prueban en test_05_seguridad.py.
"""
import re

import pytest

from conftest import cargar_modulo_app, sin_error_de_servidor

# Páginas que se pueden abrir sin iniciar sesión (a propósito).
PUBLICAS = {
    "login", "recuperar_contrasena", "serve_sw", "api_csrf", "serve_logo",
    "imagen_institucional", "calcular_edad_endpoint", "nomina.nomina_consulta",
    "cambiar_contrasena", "seleccionar_perfil",
}

# Si el nombre de la ruta contiene una de estas palabras, la ruta cambia datos.
PALABRAS_QUE_MODIFICAN = ("eliminar", "toggle", "reset", "mover", "descartar", "anular",
                          "clear_import", "logout", "delete")

# Tabla de la que se toma un registro real para las páginas que reciben un id.
TABLA_POR_RUTA = {
    "ver_atencion_colectiva": "atencion_colectiva",
    "editar_atencion_vehiculo": "atencion_vehiculo",
    "ver_atencion_vehiculo": "atencion_vehiculo",
    "ver_evento": "eventos",
    "ver_preoperacional": "preoperacional",
    "imprimir_reporte": "reporte_actividades",
    "programacion_operativa_editar": "programacion_operativa",
    "programacion_operativa_imprimir": "programacion_operativa",
    "ver_reporte_gasto": "reporte_gasto",
    "editar_usuario": "usuarios",
    "voluntariado.imprimir_voluntariado": "registro_voluntariado",
    "archivador_editar": "archivador",
}

_PARAMETRO = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")


def _tipos_checklist():
    from constants import CHECKLIST_CONFIG
    return list(CHECKLIST_CONFIG)


def _es_solo_administrador(vista):
    """True si la vista tiene el decorador admin_required (en cualquier nivel)."""
    from utils import admin_required
    codigo_admin = admin_required(lambda: None).__code__
    funcion = vista
    while funcion is not None:
        if funcion.__code__ is codigo_admin:
            return True
        funcion = getattr(funcion, "__wrapped__", None)
    return False


def _casos():
    modulo = cargar_modulo_app()
    casos = []
    for regla in sorted(modulo.app.url_map.iter_rules(), key=lambda r: r.rule):
        if regla.endpoint == "static" or "GET" not in regla.methods:
            continue
        if any(palabra in regla.endpoint for palabra in PALABRAS_QUE_MODIFICAN):
            continue
        if "tipo" in regla.arguments:
            for tipo in _tipos_checklist():
                casos.append(pytest.param(regla.endpoint, regla.rule, {"tipo": tipo},
                                          id=f"{regla.rule}[{tipo}]"))
        else:
            casos.append(pytest.param(regla.endpoint, regla.rule, {}, id=regla.rule))
    return casos


CASOS = _casos()


def _construir_url(endpoint, regla, fijos, bd, modulo):
    from constants import CHECKLIST_CONFIG
    valores = dict(fijos)
    for nombre in _PARAMETRO.findall(regla):
        if nombre in valores:
            continue
        if nombre == "token":
            valores[nombre] = modulo.serializer.dumps(bd.ultimo_id("pacientes") or 999999)
        elif nombre == "filename":
            valores[nombre] = "no_existe.png"
        elif nombre == "record_id" and "tipo" in valores:
            valores[nombre] = bd.ultimo_id(CHECKLIST_CONFIG[valores["tipo"]]["table"]) or 999999
        elif endpoint in TABLA_POR_RUTA:
            valores[nombre] = bd.ultimo_id(TABLA_POR_RUTA[endpoint]) or 999999
        else:
            pytest.fail(f"Ruta nueva: indicar en TABLA_POR_RUTA qué valor usar para <{nombre}> en {regla}")
    return _PARAMETRO.sub(lambda m: str(valores[m.group(1)]), regla)


@pytest.mark.parametrize("endpoint,regla,fijos", CASOS)
def test_pagina_como_administrador(endpoint, regla, fijos, cliente_admin, bd, modulo_app):
    url = _construir_url(endpoint, regla, fijos, bd, modulo_app)
    respuesta = cliente_admin.get(url)
    assert sin_error_de_servidor(respuesta), f"{url} respondió {respuesta.status_code}"


@pytest.mark.parametrize("endpoint,regla,fijos", CASOS)
def test_pagina_como_usuario_operativo(endpoint, regla, fijos, cliente_operativo, bd, modulo_app):
    url = _construir_url(endpoint, regla, fijos, bd, modulo_app)
    respuesta = cliente_operativo.get(url)
    assert sin_error_de_servidor(respuesta), f"{url} respondió {respuesta.status_code}"
    if _es_solo_administrador(modulo_app.app.view_functions[endpoint]):
        assert respuesta.status_code != 200, f"{url} es solo de administrador y el usuario operativo pudo verla"


@pytest.mark.parametrize("endpoint,regla,fijos", CASOS)
def test_pagina_sin_sesion(endpoint, regla, fijos, app, bd, modulo_app):
    cliente = app.test_client()
    url = _construir_url(endpoint, regla, fijos, bd, modulo_app)
    respuesta = cliente.get(url)
    assert sin_error_de_servidor(respuesta), f"{url} respondió {respuesta.status_code}"
    if endpoint not in PUBLICAS:
        assert respuesta.status_code != 200, f"{url} se puede ver sin iniciar sesión"


def test_usuario_sin_permisos_no_ve_nomina(cliente_sin_permisos):
    respuesta = cliente_sin_permisos.get("/nomina")
    assert respuesta.status_code != 200
