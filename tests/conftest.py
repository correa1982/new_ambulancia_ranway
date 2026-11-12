"""Configuración común de las pruebas.

Las pruebas usan una base MySQL SOLO para pruebas (por defecto `ambulancia_test`
en tu computador). Nunca la de producción: la base de pruebas se borra y se
vuelve a crear en cada corrida.

Protecciones:
- El nombre de la base debe terminar en `_test`.
- El servidor debe ser local (127.0.0.1 / localhost), salvo que se autorice
  expresamente con TEST_PERMITIR_HOST_REMOTO=1.
- Las variables de conexión se fijan ANTES de cargar la aplicación, así el
  archivo `.env` (que puede apuntar a producción) no se usa.
- No se envían correos: el envío se reemplaza por uno falso.
"""
import os
import re
import sys
import smtplib
from pathlib import Path
from urllib.parse import quote

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))


# ── 1. Configuración de la base de pruebas ─────────────────────────────────
def _leer_config():
    cfg = {}
    archivo = Path(__file__).parent / "bd_pruebas.local"
    if archivo.exists():
        for linea in archivo.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            cfg[clave.strip()] = valor.strip().strip('"').strip("'")
    for clave in ("TEST_MYSQL_HOST", "TEST_MYSQL_PORT", "TEST_MYSQL_USER",
                  "TEST_MYSQL_PASSWORD", "TEST_MYSQL_DB", "TEST_PERMITIR_HOST_REMOTO"):
        if os.environ.get(clave):
            cfg[clave] = os.environ[clave]
    return cfg


CFG = _leer_config()
HOST = CFG.get("TEST_MYSQL_HOST", "127.0.0.1")
PORT = int(CFG.get("TEST_MYSQL_PORT", "3306"))
USUARIO_BD = CFG.get("TEST_MYSQL_USER", "root")
CLAVE_BD = CFG.get("TEST_MYSQL_PASSWORD", "")
BASE = CFG.get("TEST_MYSQL_DB", "ambulancia_test")

if not re.fullmatch(r"[A-Za-z0-9_]+_test", BASE):
    pytest.exit(
        f"La base de pruebas debe llamarse algo terminado en '_test' (se recibió '{BASE}'). "
        "Las pruebas borran y recrean la base: nunca se usa la de producción.",
        returncode=2,
    )
if HOST not in ("127.0.0.1", "localhost", "::1") and CFG.get("TEST_PERMITIR_HOST_REMOTO") != "1":
    pytest.exit(
        f"El servidor de pruebas '{HOST}' no es local. Para usar un servidor remoto de pruebas "
        "agrega TEST_PERMITIR_HOST_REMOTO=1 en tests/bd_pruebas.local (nunca el de producción).",
        returncode=2,
    )

# ── 2. Variables de entorno de la aplicación (antes de importarla) ──────────
# load_dotenv() no reemplaza variables que ya existen, así que estas ganan al .env.
os.environ["DATABASE_URL"] = (
    f"mysql://{quote(USUARIO_BD, safe='')}:{quote(CLAVE_BD, safe='')}@{HOST}:{PORT}/{BASE}"
)
for prefijo in ("DB_", "MYSQL_"):
    os.environ[prefijo + "HOST"] = HOST
    os.environ[prefijo + "PORT"] = str(PORT)
    os.environ[prefijo + "USER"] = USUARIO_BD
    os.environ[prefijo + "PASSWORD"] = CLAVE_BD
os.environ["DB_NAME"] = BASE
os.environ["MYSQL_DB"] = BASE
os.environ["MYSQL_URL"] = os.environ["DATABASE_URL"]
os.environ["SECRET_KEY"] = "clave-solo-para-pruebas"
os.environ["DISABLE_SCHEDULER"] = "1"
for variable in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "BACKUP_EMAIL_DEST"):
    os.environ[variable] = ""
for variable in ("RAILWAY_ENVIRONMENT", "RENDER", "DB_USE_SSL"):
    os.environ.pop(variable, None)


# ── 3. Correo falso: nada sale de la máquina ───────────────────────────────
CORREOS_ENVIADOS = []


class _SMTPFalso:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def ehlo(self, *a, **k): pass
    def starttls(self, *a, **k): pass
    def login(self, *a, **k): pass
    def quit(self, *a, **k): pass
    def close(self, *a, **k): pass

    def send_message(self, mensaje, *a, **k):
        CORREOS_ENVIADOS.append(mensaje)
        return {}

    def sendmail(self, remitente, destinos, mensaje, *a, **k):
        CORREOS_ENVIADOS.append(mensaje)
        return {}


smtplib.SMTP = _SMTPFalso
smtplib.SMTP_SSL = _SMTPFalso


# ── 4. Usuarios de prueba ──────────────────────────────────────────────────
CLAVE = "Prueba#2026"

FORMULARIOS_OPERATIVOS = [
    "hc", "atencion_colectiva", "eventos", "calif_atencion", "segur_paciente",
    "atencion_vehiculo", "preoperacional", "tam", "tab", "avanzada", "pasb", "pasm",
    "equipos", "registros", "reporte_gasto", "reporte_actividades", "voluntariado",
]
FORMULARIOS_TODOS = FORMULARIOS_OPERATIVOS + [
    "inventarios", "nomina", "nomina_empleados", "pagos", "pagos_varios",
    "ths_sga", "ths_soc", "ths_trip", "voluntariado_admin",
]

USUARIOS = {
    "admin": dict(identificacion="9000000001", nombre="Admin Pruebas", rol="admin",
                  perfil="Administrador", formularios=FORMULARIOS_TODOS),
    "operativo": dict(identificacion="9000000002", nombre="Operativo Pruebas", rol="usuario",
                      perfil="APH", formularios=FORMULARIOS_OPERATIVOS),
    "sin_permisos": dict(identificacion="9000000003", nombre="Sin Permisos Pruebas", rol="usuario",
                         perfil="Conductor", formularios=[]),
    "inactivo": dict(identificacion="9000000004", nombre="Inactivo Pruebas", rol="usuario",
                     perfil="APH", formularios=FORMULARIOS_OPERATIVOS, activo=0),
    "cambio_clave": dict(identificacion="9000000005", nombre="Cambio Clave Pruebas", rol="usuario",
                         perfil="APH", formularios=FORMULARIOS_OPERATIVOS, requiere_cambio_clave=1),
    "dos_perfiles": dict(identificacion="9000000006", nombre="Dos Perfiles Pruebas", rol="usuario",
                         perfiles=["APH", "Conductor"], formularios=FORMULARIOS_OPERATIVOS),
}


# ── 5. Carga de la aplicación ──────────────────────────────────────────────
_MODULO_APP = None


def cargar_modulo_app():
    """Importa app.py una sola vez (no se conecta a la base al importar)."""
    global _MODULO_APP
    if _MODULO_APP is None:
        import app as modulo
        modulo.app.config.update(TESTING=True)
        _MODULO_APP = modulo
    return _MODULO_APP


def _recrear_base():
    import pymysql
    try:
        conexion = pymysql.connect(host=HOST, port=PORT, user=USUARIO_BD, password=CLAVE_BD,
                                   charset="utf8mb4", autocommit=True, connect_timeout=10)
    except Exception as error:
        pytest.exit(
            f"No se pudo conectar a MySQL en {HOST}:{PORT} con el usuario '{USUARIO_BD}': {error}\n"
            "Revisa que MySQL esté encendido y los datos de tests/bd_pruebas.local (ver tests/README.md).",
            returncode=2,
        )
    with conexion.cursor() as cursor:
        cursor.execute(f"DROP DATABASE IF EXISTS `{BASE}`")
        cursor.execute(f"CREATE DATABASE `{BASE}` CHARACTER SET utf8mb4")
    conexion.close()


def _crear_usuarios():
    import json
    from werkzeug.security import generate_password_hash
    from db import get_db

    clave_hash = generate_password_hash(CLAVE)
    conn = get_db()
    try:
        for datos in USUARIOS.values():
            perfiles = datos.get("perfiles") or [datos["perfil"]]
            accesos = {p: list(datos["formularios"]) for p in perfiles}
            conn.execute(
                """INSERT INTO usuarios (nombre, identificacion, registro_medico, rol, perfil, activo,
                       contrasena, requiere_cambio_clave, formularios_acceso, correo,
                       permiso_programacion_operativa, permiso_verificacion_pagos)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datos["nombre"], datos["identificacion"], "RM-PRUEBA", datos["rol"],
                    json.dumps(perfiles, ensure_ascii=False), datos.get("activo", 1), clave_hash,
                    datos.get("requiere_cambio_clave", 0), json.dumps(accesos, ensure_ascii=False),
                    f"{datos['identificacion']}@pruebas.local",
                    1 if datos["rol"] == "admin" else 0, 1 if datos["rol"] == "admin" else 0,
                ),
            )
        conn.execute(
            "INSERT INTO vehiculos (tipo, placa, marca, modelo, tipo_ambulancia, movil, activo) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            ("Ambulancia", "PRU123", "Marca", "2024", "TAB", "M-01"),
        )
        conn.commit()
    finally:
        conn.close()


# ── 6. Fixtures ────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def app():
    """La aplicación con una base de pruebas nueva, creada por init_db() y con usuarios de prueba."""
    modulo = cargar_modulo_app()

    # Última comprobación: la aplicación apunta a la base de pruebas.
    from db import get_pool
    parametros = get_pool()._get_params()
    if parametros.get("database") != BASE or parametros.get("host") != HOST:
        pytest.exit(f"La aplicación no apunta a la base de pruebas ({parametros.get('host')}/"
                    f"{parametros.get('database')}). Se detienen las pruebas.", returncode=2)

    _recrear_base()
    from db import init_db
    init_db()
    modulo._db_initialized = True
    modulo._scheduler_started = True
    _crear_usuarios()
    return modulo.app


@pytest.fixture(scope="session")
def modulo_app(app):
    return cargar_modulo_app()


def token_csrf(cliente):
    respuesta = cliente.get("/api/csrf")
    assert respuesta.status_code == 200, "La ruta /api/csrf no respondió"
    return respuesta.get_json()["token"]


def enviar(cliente, url, datos=None, **kwargs):
    """POST con el token CSRF vigente, como lo hace la aplicación."""
    datos = dict(datos or {})
    datos.setdefault("csrf_token", token_csrf(cliente))
    return cliente.post(url, data=datos, **kwargs)


def iniciar_sesion(cliente, rol, clave=CLAVE):
    return enviar(cliente, "/", {"identificacion": USUARIOS[rol]["identificacion"], "contrasena": clave})


def _cliente_con_sesion(app, rol):
    cliente = app.test_client()
    respuesta = iniciar_sesion(cliente, rol)
    assert respuesta.status_code in (302, 303), f"No se pudo iniciar sesión como {rol}"
    return cliente


@pytest.fixture
def cliente(app):
    """Cliente sin sesión iniciada."""
    return app.test_client()


@pytest.fixture(scope="module")
def cliente_admin(app):
    return _cliente_con_sesion(app, "admin")


@pytest.fixture(scope="module")
def cliente_operativo(app):
    return _cliente_con_sesion(app, "operativo")


@pytest.fixture(scope="module")
def cliente_sin_permisos(app):
    return _cliente_con_sesion(app, "sin_permisos")


@pytest.fixture
def bd(app):
    """Consultas directas a la base de pruebas para verificar resultados."""
    from db import get_db

    class _BD:
        def uno(self, sql, params=()):
            conn = get_db()
            try:
                return conn.execute(sql, params).fetchone()
            finally:
                conn.close()

        def todos(self, sql, params=()):
            conn = get_db()
            try:
                return conn.execute(sql, params).fetchall()
            finally:
                conn.close()

        def contar(self, tabla, where="1=1", params=()):
            return self.uno(f"SELECT COUNT(*) AS n FROM `{tabla}` WHERE {where}", params)["n"]

        def ultimo_id(self, tabla):
            fila = self.uno(f"SELECT MAX(id) AS id FROM `{tabla}`")
            return fila["id"] if fila and fila["id"] else None

    return _BD()


def sin_error_de_servidor(respuesta):
    """La respuesta no es un error interno (500) ni muestra un traceback."""
    if respuesta.status_code >= 500:
        return False
    if respuesta.mimetype == "text/html":
        texto = respuesta.get_data(as_text=True)
        if "Traceback (most recent call last)" in texto:
            return False
    return True
