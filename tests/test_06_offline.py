"""Modo sin conexión: service worker, versiones de archivos y token para sincronizar."""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import RAIZ, cargar_modulo_app

SW = RAIZ / "static" / "sw.js"
PWA = RAIZ / "static" / "pwa-offline.js"
BASE_HTML = RAIZ / "templates" / "base.html"
LOGIN_HTML = RAIZ / "templates" / "login.html"


def _texto(ruta):
    return ruta.read_text(encoding="utf-8")


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js no está instalado")
def test_service_worker_simulado():
    """Prueba el service worker en un navegador simulado: sin conexión, señal débil, sesión vencida."""
    prueba = Path(__file__).parent / "js" / "sw.test.js"
    resultado = subprocess.run(["node", str(prueba), str(SW)], capture_output=True, text=True, timeout=120)
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr


def test_misma_version_de_pwa_offline_en_todos_lados():
    """Si base.html carga una versión y el service worker guarda otra, el modo offline queda sin su script."""
    en_base = re.findall(r"pwa-offline\.js\?v=(\d+)", _texto(BASE_HTML))
    en_sw = re.findall(r"pwa-offline\.js\?v=(\d+)", _texto(SW))
    assert en_base and en_sw
    assert set(en_base) == set(en_sw), f"base.html usa v={en_base} y sw.js guarda v={en_sw}"


def test_misma_version_del_service_worker_en_todos_lados():
    en_login = re.findall(r"sw\.js\?v=(\d+)", _texto(LOGIN_HTML))
    en_pwa = re.findall(r"sw\.js\?v=(\d+)", _texto(PWA))
    assert en_login and en_pwa
    assert set(en_login) == set(en_pwa), f"login.html registra v={en_login} y pwa-offline.js v={en_pwa}"


def test_paginas_del_service_worker_existen():
    """Cada página que el service worker guarda para uso offline debe existir en la aplicación."""
    texto = _texto(SW)
    bloque = re.search(r"const PAGINAS = \[(.*?)\];", texto, re.S).group(1)
    paginas = re.findall(r"'(/[^']*)'", bloque)
    adaptador = cargar_modulo_app().app.url_map.bind("localhost")
    inexistentes = []
    for pagina in paginas:
        try:
            adaptador.match(pagina, method="GET")
        except Exception:
            inexistentes.append(pagina)
    assert not inexistentes, f"El service worker intenta guardar páginas que no existen: {inexistentes}"


def test_token_csrf_vigente_para_sincronizar(cliente):
    """La sincronización pide el token vigente y con él puede enviar."""
    respuesta = cliente.get("/api/csrf")
    assert respuesta.status_code == 200
    assert respuesta.headers.get("Cache-Control") == "no-store"
    token = respuesta.get_json()["token"]
    assert token and token == cliente.get("/api/csrf").get_json()["token"]


def test_service_worker_no_se_guarda_en_cache_del_navegador(cliente):
    respuesta = cliente.get("/sw.js")
    assert respuesta.status_code == 200
    assert "no-cache" in respuesta.headers.get("Cache-Control", "")
