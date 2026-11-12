"""Inicio de sesión, perfiles, cambio de contraseña y cierre de sesión."""
from conftest import USUARIOS, enviar, iniciar_sesion, sin_error_de_servidor


def test_pagina_de_login_carga(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert 'name="identificacion"' in respuesta.get_data(as_text=True)


def test_login_correcto_lleva_al_dashboard(cliente):
    respuesta = iniciar_sesion(cliente, "operativo")
    assert respuesta.status_code == 302
    assert respuesta.headers["Location"].endswith("/dashboard")
    assert cliente.get("/dashboard").status_code == 200


def test_login_con_clave_incorrecta_no_entra(cliente):
    respuesta = iniciar_sesion(cliente, "sin_permisos", clave="clave-equivocada")
    assert respuesta.status_code == 200
    assert "Credenciales incorrectas" in respuesta.get_data(as_text=True)
    assert cliente.get("/dashboard").status_code == 302


def test_login_de_usuario_que_no_existe_da_el_mismo_mensaje(cliente):
    respuesta = enviar(cliente, "/", {"identificacion": "0000000000", "contrasena": "x"})
    assert respuesta.status_code == 200
    assert "Credenciales incorrectas" in respuesta.get_data(as_text=True)


def test_usuario_inactivo_no_entra(cliente):
    respuesta = iniciar_sesion(cliente, "inactivo")
    assert respuesta.status_code == 200
    assert "deshabilitado" in respuesta.get_data(as_text=True)
    assert cliente.get("/dashboard").status_code == 302


def test_login_sin_token_csrf_es_rechazado(cliente):
    cliente.get("/")
    respuesta = cliente.post("/", data={"identificacion": USUARIOS["admin"]["identificacion"],
                                        "contrasena": "x"})
    assert respuesta.status_code == 400


def test_usuario_con_cambio_de_clave_obligatorio_es_redirigido(cliente):
    iniciar_sesion(cliente, "cambio_clave")
    respuesta = cliente.get("/dashboard")
    assert respuesta.status_code == 302
    assert "/cambiar_contrasena" in respuesta.headers["Location"]
    assert cliente.get("/cambiar_contrasena").status_code == 200


def test_usuario_con_dos_perfiles_elige_perfil(cliente):
    respuesta = iniciar_sesion(cliente, "dos_perfiles")
    assert respuesta.status_code == 302
    assert "/seleccionar_perfil" in respuesta.headers["Location"]
    pagina = cliente.get("/seleccionar_perfil")
    assert pagina.status_code == 200
    respuesta = enviar(cliente, "/seleccionar_perfil", {"perfil": "APH"})
    assert sin_error_de_servidor(respuesta)
    assert cliente.get("/dashboard").status_code == 200


def test_cerrar_sesion(cliente):
    iniciar_sesion(cliente, "operativo")
    assert cliente.get("/dashboard").status_code == 200
    cliente.get("/logout")
    assert cliente.get("/dashboard").status_code == 302


def test_pagina_protegida_sin_sesion_va_al_login(cliente):
    respuesta = cliente.get("/formulario")
    assert respuesta.status_code == 302
    from urllib.parse import urlsplit
    assert urlsplit(respuesta.headers["Location"]).path == "/"
