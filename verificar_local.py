"""
Verificacion local del proyecto contra MySQL de XAMPP.

Uso (con XAMPP -> MySQL encendido):
    python verificar_local.py

Crea una base TEMPORAL llamada 'ambulancia_verificacion', inicializa las
tablas, entra como administrador, abre todas las paginas GET sin parametros,
prueba que el pool de conexiones se recupere si MySQL corta las conexiones
(lo que pasa en el parche de Railway) y al final BORRA la base temporal.
No toca tu base local habitual ni la de Railway.

Si tu MySQL de XAMPP tiene usuario/clave distintos a root sin clave:
    set LOCAL_DB_USER=root
    set LOCAL_DB_PASSWORD=miclave
    set LOCAL_DB_PORT=3306
"""
import os
import sys
import traceback

DB_NAME = "ambulancia_verificacion"
HOST = os.getenv("LOCAL_DB_HOST", "127.0.0.1")
PORT = int(os.getenv("LOCAL_DB_PORT", "3306"))
USER = os.getenv("LOCAL_DB_USER", "root")
PASSWORD = os.getenv("LOCAL_DB_PASSWORD", "")

# Forzar la base local ANTES de importar la app, para que el .env
# (que puede apuntar a Railway) no se use. load_dotenv no pisa variables
# que ya existen.
os.environ["DATABASE_URL"] = f"mysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DB_NAME}"
os.environ["DISABLE_SCHEDULER"] = "1"  # que no envie correos de backup
os.environ.setdefault("SECRET_KEY", "verificacion-local")
for var in ("MYSQL_URL", "DB_HOST", "MYSQL_HOST"):
    os.environ.pop(var, None)

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)
sys.path.insert(0, BASE)

import pymysql

OK, FALLA = "[OK]   ", "[FALLA]"
fallas = []


def admin_conn(db=None):
    return pymysql.connect(host=HOST, port=PORT, user=USER, password=PASSWORD,
                           database=db, autocommit=True, connect_timeout=5)


# 1. Conexion y base temporal -------------------------------------------------
print(f"\n1) Conectando a MySQL en {HOST}:{PORT} como '{USER}'...")
try:
    c = admin_conn()
except Exception as e:
    print(f"{FALLA} No se pudo conectar: {e}")
    print("        Verifica que MySQL este encendido en el panel de XAMPP.")
    sys.exit(1)
with c.cursor() as cur:
    cur.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
    cur.execute(f"CREATE DATABASE {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
c.close()
print(f"{OK} Base temporal '{DB_NAME}' creada")

try:
    # 2. Importar app e inicializar tablas -----------------------------------
    print("\n2) Cargando la app e inicializando tablas...")
    import app as app_module
    from db import init_db, get_pool
    app = app_module.app
    app.config["TESTING"] = True
    with app.app_context():
        init_db()
    print(f"{OK} init_db() creo las tablas")

    c = admin_conn(DB_NAME)
    with c.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute("SHOW TABLES")
        n_tablas = len(cur.fetchall())
        cur.execute("SELECT * FROM usuarios WHERE identificacion='admin'")
        admin = cur.fetchone()
    c.close()
    print(f"{OK} {n_tablas} tablas en la base")
    if not admin:
        print(f"{FALLA} No se creo el usuario admin")
        sys.exit(1)

    client = app.test_client()

    # 3. Login real con el formulario -----------------------------------------
    print("\n3) Probando login...")
    r = client.get("/login")
    token = None
    try:
        import re
        m = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', r.data) or \
            re.search(rb'value="([^"]+)"[^>]*name="csrf_token"', r.data)
        token = m.group(1).decode() if m else None
    except Exception:
        pass
    print(f"{OK if r.status_code == 200 else FALLA} GET /login -> {r.status_code}")
    r = client.post("/login", data={"x": "1"})
    print(f"{OK if r.status_code == 400 else FALLA} POST /login sin token CSRF -> {r.status_code} (esperado 400)")

    # Sesion de administrador directa (independiente de la clave que tenga admin)
    with client.session_transaction() as s:
        s["usuario"] = {
            "id": admin["id"], "nombre": admin["nombre"],
            "identificacion": admin["identificacion"],
            "registro_medico": admin["registro_medico"],
            "rol": "admin", "rol_real": "admin", "perfil": "Administrador",
            "requiere_cambio_clave": False, "formularios_acceso": [],
            "permiso_ths_sga": 1, "permiso_programacion_operativa": 1,
        }

    # 4. Todas las paginas GET sin parametros ---------------------------------
    print("\n4) Abriendo todas las paginas GET como administrador...")
    omitir = {"/logout", "/static/<path:filename>"}
    rutas = sorted({r.rule for r in app.url_map.iter_rules()
                    if "GET" in r.methods and not r.arguments and r.rule not in omitir})
    for ruta in rutas:
        try:
            resp = client.get(ruta)
            code = resp.status_code
            if code >= 500:
                fallas.append((ruta, f"HTTP {code}"))
                print(f"{FALLA} {ruta} -> {code}")
        except Exception as e:
            fallas.append((ruta, "".join(traceback.format_exception_only(type(e), e)).strip()))
            print(f"{FALLA} {ruta} -> {type(e).__name__}: {e}")
            traceback.print_exc(limit=3)
    print(f"{OK} {len(rutas) - len(fallas)} de {len(rutas)} paginas respondieron sin error")

    # 5. Recuperacion del pool cuando MySQL corta las conexiones ---------------
    print("\n5) Simulando reinicio de MySQL (se matan las conexiones del pool)...")
    pool = get_pool()
    vivas = []
    while True:
        try:
            vivas.append(pool._queue.get_nowait())
        except Exception:
            break
    ids = [x.thread_id() for x in vivas]
    for x in vivas:
        pool._queue.put_nowait(x)
    c = admin_conn()
    with c.cursor() as cur:
        for tid in ids:
            try:
                cur.execute(f"KILL {tid}")
            except Exception:
                pass
    c.close()
    print(f"        {len(ids)} conexiones cortadas")
    errores_pool = 0
    for _ in range(15):
        resp = client.get("/dashboard")
        if resp.status_code >= 500:
            errores_pool += 1
    if errores_pool:
        fallas.append(("pool", f"{errores_pool} errores tras cortar conexiones"))
        print(f"{FALLA} {errores_pool}/15 peticiones fallaron tras cortar conexiones")
    else:
        print(f"{OK} 15/15 peticiones funcionaron tras cortar las conexiones")
    print(f"        Tamano del pool: {pool._size} (maximo {pool._max})")

finally:
    # 6. Limpieza --------------------------------------------------------------
    try:
        from db import close_all
        close_all()
    except Exception:
        pass
    try:
        c = admin_conn()
        with c.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
        c.close()
        print(f"\n6) Base temporal '{DB_NAME}' eliminada")
    except Exception as e:
        print(f"\nNo se pudo borrar '{DB_NAME}': {e}")

print("\n" + "=" * 60)
if fallas:
    print(f"RESULTADO: {len(fallas)} problema(s):")
    for ruta, err in fallas:
        print(f"  - {ruta}: {err}")
    sys.exit(1)
print("RESULTADO: todo OK")
