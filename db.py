import os
import json
import queue
import threading
from datetime import date, datetime
import pymysql
import pymysql.cursors
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from constants import ASEGURADORAS

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

class ConnectionPool:
    def __init__(self, min_size=1, max_size=10):
        self._max = max_size
        self._size = 0
        self._lock = threading.Lock()
        self._queue = queue.Queue(maxsize=max_size)
        self._conn_params = None

    def _get_params(self):
        if self._conn_params is None:
            # Soporte para DATABASE_URL (muy común en Render/servicios en la nube)
            db_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
            if db_url and (db_url.startswith("mysql://") or db_url.startswith("mysql+pymysql://")):
                from urllib.parse import urlparse, unquote
                parsed = urlparse(db_url)
                self._conn_params = {
                    "host": parsed.hostname,
                    "user": unquote(parsed.username) if parsed.username else None,
                    "password": unquote(parsed.password) if parsed.password else None,
                    "database": parsed.path.lstrip("/"),
                    "port": parsed.port or 3306,
                }
            else:
                self._conn_params = {
                    "host": os.getenv("DB_HOST") or os.getenv("MYSQL_HOST") or "localhost",
                    "user": os.getenv("DB_USER") or os.getenv("MYSQL_USER", "root"),
                    "password": os.getenv("DB_PASSWORD") or os.getenv("MYSQL_PASSWORD", ""),
                    "database": os.getenv("DB_NAME") or os.getenv("MYSQL_DB", "ambulancia_db"),
                    "port": int(os.getenv("DB_PORT") or os.getenv("MYSQL_PORT", 3306)),
                }
        return self._conn_params

    def _connect(self):
        p = self._get_params()
        connect_kwargs = {
            "host": p["host"],
            "user": p["user"],
            "password": p["password"],
            "database": p["database"],
            "port": p["port"],
            "cursorclass": pymysql.cursors.DictCursor,
            "autocommit": False,
            "connect_timeout": 10
        }
        
        # Opcional: Soporte para SSL si la base de datos externa lo requiere en Render
        if os.getenv("DB_USE_SSL") == "true":
            connect_kwargs["ssl"] = {"ssl_mode": "VERIFY_IDENTITY"}
            
        return pymysql.connect(**connect_kwargs)

    def acquire(self):
        try:
            conn = self._queue.get_nowait()
            try:
                conn.ping()
                return conn
            except Exception:
                pass
        except queue.Empty:
            pass

        with self._lock:
            if self._size < self._max:
                self._size += 1
                return self._connect()

        conn = self._queue.get()
        try:
            conn.ping()
        except Exception:
            conn = self._connect()
        return conn

    def release(self, conn):
        try:
            self._queue.put_nowait(conn)
        except queue.Full:
            try:
                conn.close()
            except Exception:
                pass
            with self._lock:
                self._size -= 1


_pool = None
_pool_lock = threading.Lock()

def get_pool():
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ConnectionPool()
    return _pool


class MySQLConnectionWrapper:
    def __init__(self):
        self._pool = get_pool()
        self.conn = self._pool.acquire()
        self._closed = False

    def execute(self, query, params=None):
        cursor = self.conn.cursor()
        mysql_query = query.replace("?", "%s")
        cursor.execute(mysql_query, params)
        return cursor

    def commit(self):
        self.conn.commit()

    def close(self):
        if not self._closed:
            self._closed = True
            try:
                self.conn.rollback()
            except Exception:
                pass
            self._pool.release(self.conn)

    def cursor(self):
        return self.conn.cursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


_db_context = threading.local()

def get_db():
    wrapper = MySQLConnectionWrapper()
    if not hasattr(_db_context, 'connections'):
        _db_context.connections = []
    _db_context.connections.append(wrapper)
    return wrapper

def close_all():
    conns = getattr(_db_context, 'connections', [])
    for c in conns:
        try:
            c.close()
        except Exception:
            pass
    _db_context.connections = []

def init_db():
    is_render = os.getenv("RENDER") == "true"

    # ⚠️ SOLO crear BD en entorno local (NO en Render)
    if not is_render and not (os.getenv("DB_HOST") or os.getenv("MYSQL_HOST")):
        try:
            host = os.getenv("MYSQL_HOST", "localhost")
            user = os.getenv("MYSQL_USER", "root")
            password = os.getenv("MYSQL_PASSWORD", "")
            port = int(os.getenv("MYSQL_PORT", 3306))
            db_name = os.getenv("MYSQL_DB", "ambulancia_db")
            
            temp_conn = pymysql.connect(host=host, user=user, password=password, port=port)
            temp_conn.cursor().execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            temp_conn.close()
        except Exception as e:
            print("Could not create database:", e)
            pass

    conn = get_db()
    
    # Define tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            nombre TEXT NOT NULL,
            identificacion VARCHAR(255) UNIQUE NOT NULL,
            registro_medico TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS archivador (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            nombre_formulario VARCHAR(255) NOT NULL,
            consecutivo INTEGER NOT NULL,
            archivo_url TEXT NOT NULL,
            archivo_nombre TEXT NOT NULL,
            fecha_registro TEXT NOT NULL,
            registrado_por TEXT NOT NULL,
            registrado_por_identificacion TEXT NOT NULL,
            perfil_registrador TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pacientes (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            identificacion_paciente TEXT NOT NULL,
            tipo_documento TEXT NOT NULL,
            primer_apellido TEXT NOT NULL,
            segundo_apellido TEXT,
            primer_nombre TEXT NOT NULL,
            segundo_nombre TEXT,
            fecha_nacimiento TEXT NOT NULL,
            edad INTEGER,
            telefono TEXT,
            direccion TEXT,
            tipo_afiliacion TEXT,
            aseguradora TEXT,
            motivo_consulta TEXT,
            enfermedad_actual TEXT,
            analisis TEXT,
            plan TEXT,
            registrado_por TEXT,
            fecha_registro TEXT,
            fecha_inicio_atencion TEXT,
            atencion_colectiva_id INTEGER,
            finalizado INTEGER DEFAULT 1,
            pertenencia_etnica TEXT,
            discapacidad TEXT,
            habitante_calle TEXT,
            aplica_acompanante TEXT,
            acompanante_nombre TEXT,
            acompanante_tipo_doc TEXT,
            acompanante_doc TEXT,
            acompanante_telefono TEXT,
            acompanante_parentesco TEXT,
            aplica_responsable TEXT,
            responsable_nombre TEXT,
            responsable_tipo_doc TEXT,
            responsable_doc TEXT,
            responsable_telefono TEXT,
            responsable_parentesco TEXT,
            primer_respondiente TEXT,
            es_emergencia_medica TEXT,
            detalle_emergencia_medica TEXT,
            es_emergencia_traumatica TEXT,
            detalle_emergencia_traumatica TEXT,
            antecedentes_personales TEXT,
            antecedentes_quirurgicos TEXT,
            antecedentes_toxicologicos TEXT,
            antecedentes_alergicos TEXT,
            antecedentes_ginecobstetricos TEXT,
            medicamentos_actuales TEXT,
            otros_antecedentes TEXT,
            antecedentes_familiares TEXT,
            dolor TEXT,
            triage_fecha_hora TEXT,
            triage_clasificacion TEXT,
            glasgow_ocular TEXT,
            glasgow_verbal TEXT,
            glasgow_motora TEXT,
            glasgow_total TEXT,
            estado_consciencia TEXT,
            cincinnati_facial TEXT,
            cincinnati_brazo TEXT,
            cincinnati_habla TEXT,
            cincinnati_total TEXT,
            rts_total TEXT,
            evaluacion_inicial TEXT,
            examen_fisico TEXT,
            triage_mci TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            clave VARCHAR(255) PRIMARY KEY,
            valor LONGTEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha_inicio TEXT,
            hora_inicio TEXT,
            fecha_finalizacion TEXT,
            hora_finalizacion TEXT,
            tipo_evento TEXT,
            direccion TEXT,
            municipio TEXT,
            num_afectados TEXT,
            recursos_activados TEXT,
            observaciones TEXT,
            firma_coordinador_evento TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            registro_medico_registrador TEXT,
            firma_registrador TEXT,
            fecha_registro TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS atencion_vehiculo (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            consecutivo INTEGER,
            pais TEXT,
            departamento TEXT,
            municipio TEXT,
            barrio TEXT,
            direccion TEXT,
            fecha_hora_despacho TEXT,
            fecha_hora_salida TEXT,
            fecha_hora_llegada TEXT,
            comandante_incidente TEXT,
            integrantes_tripulacion TEXT,
            tipo TEXT,
            subtipo TEXT,
            descripcion TEXT,
            fecha_hora_finalizacion TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            registro_medico_registrador TEXT,
            firma_registrador TEXT,
            fecha_registro TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS atencion_colectiva (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha_inicio TEXT NOT NULL,
            hora_inicio TEXT,
            fecha_finalizacion TEXT,
            hora_finalizacion TEXT,
            lugar TEXT,
            tipo_incidente TEXT,
            recursos_desplegados TEXT,
            coordinador TEXT,
            observaciones TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            registro_medico_registrador TEXT,
            firma_registrador TEXT,
            fecha_registro TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS preoperacional (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT,
            placa_vehiculo TEXT,
            tipo_vehiculo TEXT,
            tipo_ambulancia TEXT,
            movil TEXT,
            marca TEXT,
            serie TEXT,
            modelo TEXT,
            soat_vigencia TEXT,
            rtm_vigencia TEXT,
            nombre_conductor TEXT,
            kilometraje TEXT,
            proximo_aceite TEXT,
            frenos TEXT, direccion_vehiculo TEXT, luces_emergencia TEXT,
            luces_normales TEXT, sirena TEXT, senalizacion TEXT, llantas TEXT,
            carroceria TEXT, espejos TEXT, documentos_vehiculo TEXT,
            botiquin TEXT, oxigeno TEXT, camilla TEXT, inmovilizadores TEXT,
            desfibrilador TEXT, comunicaciones TEXT,
            observaciones TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            firma_registrador TEXT,
            fecha_registro TEXT,
            evidencia TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checklist_tam (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT,
            placa TEXT,
            turno TEXT,
            monitor_desfibrilador TEXT, ventilador TEXT, bomba_infusion TEXT,
            laringoscopio TEXT, tubos_et TEXT, agujas_descompresion TEXT,
            capnografo TEXT, glucometro TEXT, oxigeno_lleno TEXT,
            aspirador TEXT, desa TEXT,
            adrenalina TEXT, atropina TEXT, amiodarona TEXT, furosemida TEXT,
            morfina TEXT, midazolam TEXT, soluciones TEXT,
            epp TEXT, guantes TEXT, mascarillas_n95 TEXT,
            observaciones TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            firma_registrador TEXT,
            fecha_registro TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checklist_tab (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT,
            placa TEXT,
            turno TEXT,
            oxigeno_lleno TEXT, mascarillas_o2 TEXT, canulas_nasales TEXT,
            bvm TEXT, collar_cervical TEXT, tabla_espinal TEXT,
            inmovilizadores_cabeza TEXT, camilla TEXT, silla_ruedas TEXT,
            glucometro TEXT, oximetro TEXT, tensiometro TEXT,
            gasas TEXT, vendas TEXT, antisepticos TEXT, jeringas TEXT,
            soluciones_tab TEXT,
            epp TEXT, guantes TEXT, mascarillas TEXT,
            observaciones TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            firma_registrador TEXT,
            fecha_registro TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checklist_avanzada (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT,
            evento TEXT,
            botiquin TEXT,
            observaciones TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            firma_registrador TEXT,
            fecha_registro TEXT,
            datos_json TEXT,
            finalizado INTEGER DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checklist_pasb (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT,
            ubicacion TEXT,
            carpas TEXT, camillas TEXT, sillas TEXT, iluminacion TEXT,
            oxigeno TEXT, material_curacion TEXT, medicamentos_basicos TEXT,
            glucometro TEXT, oximetro TEXT,
            comunicaciones TEXT, agua_saneamiento TEXT, senalizacion TEXT,
            personal_aph TEXT,
            estado_operativo TEXT,
            observaciones TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            firma_registrador TEXT,
            fecha_registro TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checklist_pasm (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT,
            ubicacion TEXT,
            carpas TEXT, camillas TEXT, sillas TEXT, iluminacion TEXT,
            monitor_desfibrilador TEXT, ventilador TEXT, bomba_infusion TEXT,
            oxigeno TEXT, material_curacion TEXT, medicamentos_ava TEXT,
            glucometro TEXT, oximetro TEXT,
            comunicaciones TEXT, agua_saneamiento TEXT, senalizacion TEXT,
            personal_medico TEXT, personal_enfermeria TEXT, personal_aph TEXT,
            estado_operativo TEXT,
            observaciones TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            firma_registrador TEXT,
            fecha_registro TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checklist_equipos (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT,
            grupo_equipos TEXT,
            observaciones TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            firma_registrador TEXT,
            fecha_registro TEXT,
            datos_json TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS calif_atencion (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT,
            primer_nombre TEXT,
            primer_apellido TEXT,
            tipo_documento TEXT,
            identificacion TEXT,
            datos_json TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            firma_registrador TEXT,
            firma_paciente TEXT,
            responsable_nombre TEXT,
            responsable_apellido TEXT,
            responsable_tipo_doc TEXT,
            responsable_identificacion TEXT,
            finalizado INTEGER DEFAULT 1,
            fecha_registro TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS segur_paciente (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT,
            primer_nombre TEXT,
            primer_apellido TEXT,
            tipo_documento TEXT,
            identificacion TEXT,
            nombre_reporte TEXT,
            descripcion TEXT,
            datos_json TEXT,
            registrado_por TEXT,
            registrado_por_identificacion TEXT,
            perfil_registrador TEXT,
            firma_registrador TEXT,
            finalizado INTEGER DEFAULT 1,
            fecha_registro TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checklist_items (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            tipo_checklist TEXT NOT NULL,
            categoria TEXT NOT NULL,
            identificador TEXT NOT NULL,
            nombre TEXT NOT NULL,
            activo INTEGER DEFAULT 1,
            cantidad INTEGER DEFAULT NULL
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS checklist_categorias (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            tipo_checklist TEXT NOT NULL,
            nombre TEXT NOT NULL,
            activo INTEGER DEFAULT 1
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vehiculos (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            tipo TEXT NOT NULL,
            placa VARCHAR(255) NOT NULL UNIQUE,
            marca TEXT,
            serie TEXT,
            modelo TEXT,
            tipo_ambulancia TEXT,
            movil TEXT,
            soat_vigencia DATE,
            rtm_vigencia DATE,
            activo INTEGER DEFAULT 1
        )
    """)
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS aseguradoras (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            nombre VARCHAR(255) NOT NULL UNIQUE,
            activo INTEGER DEFAULT 1
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS aseguradoras_soat (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            nombre VARCHAR(255) NOT NULL UNIQUE,
            activo INTEGER DEFAULT 1
        )
    """)
    
    # Dynamic schema migration for usuarios
    cursor = conn.cursor()
    cursor.execute("DESCRIBE usuarios")
    columns = [row["Field"] for row in cursor.fetchall()]
    
    if "rol" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN rol VARCHAR(50) DEFAULT 'usuario'")
    if "perfil" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN perfil TEXT")
    if "activo" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN activo INTEGER DEFAULT 1")
    if "firma" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN firma TEXT")
    if "contrasena" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN contrasena TEXT")
    if "requiere_cambio_clave" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN requiere_cambio_clave INTEGER DEFAULT 1")
    if "formularios_acceso" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN formularios_acceso TEXT")
    if "correo" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN correo TEXT")
    if "ultima_latitud" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN ultima_latitud TEXT")
    if "ultima_longitud" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN ultima_longitud TEXT")
    if "ultima_actualizacion_gps" not in columns:
        conn.execute("ALTER TABLE usuarios ADD COLUMN ultima_actualizacion_gps TEXT")

    # Migrate perfil from plain text to JSON array
    all_users = conn.execute("SELECT id, perfil FROM usuarios").fetchall()
    for u in all_users:
        perfil_val = u["perfil"]
        if perfil_val:
            try:
                parsed = json.loads(perfil_val)
                if not isinstance(parsed, list):
                    conn.execute("UPDATE usuarios SET perfil = ? WHERE id = ?", (json.dumps([perfil_val]), u["id"]))
            except (json.JSONDecodeError, TypeError):
                conn.execute("UPDATE usuarios SET perfil = ? WHERE id = ?", (json.dumps([perfil_val]), u["id"]))

    # Migrate formularios_acceso from list to dict mapped by perfiles
    all_users_access = conn.execute("SELECT id, perfil, formularios_acceso FROM usuarios").fetchall()
    for u in all_users_access:
        acc_val = u["formularios_acceso"]
        if acc_val:
            try:
                parsed_acc = json.loads(acc_val)
                if isinstance(parsed_acc, list):
                    new_acc = {}
                    try:
                        perfiles = json.loads(u["perfil"])
                    except:
                        perfiles = [u["perfil"]] if u["perfil"] else []
                    for p in perfiles:
                        new_acc[p] = parsed_acc
                    conn.execute("UPDATE usuarios SET formularios_acceso = ? WHERE id = ?", (json.dumps(new_acc), u["id"]))
            except (json.JSONDecodeError, TypeError):
                pass
        
    # Dynamic schema migration for pacientes
    cursor.execute("DESCRIBE pacientes")
    pacientes_columns = [row["Field"] for row in cursor.fetchall()]
    
    if "registrado_por_identificacion" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN registrado_por_identificacion TEXT")
    if "registro_medico_registrador" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN registro_medico_registrador TEXT")
    if "perfil_registrador" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN perfil_registrador TEXT")
    if "firma_registrador" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN firma_registrador TEXT")
    if "fecha_finalizacion_registro" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN fecha_finalizacion_registro TEXT")
    if "fecha_inicio_atencion" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN fecha_inicio_atencion TEXT")
    if "hora_despacho" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN hora_despacho TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN hora_arribo TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN sexo_biologico TEXT")
    if "identidad_genero" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN identidad_genero TEXT")
    if "estado_civil" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN estado_civil TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN ocupacion TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN nacionalidad TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN correo_electronico TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN departamento_residencia TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN municipio_residencia TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN barrio_residencia TEXT")
    if "antecedentes_personales" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN antecedentes_personales TEXT")
    if "antecedentes_quirurgicos" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN antecedentes_quirurgicos TEXT")
    if "antecedentes_toxicologicos" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN antecedentes_toxicologicos TEXT")
    if "antecedentes_alergicos" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN antecedentes_alergicos TEXT")
    if "antecedentes_ginecobstetricos" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN antecedentes_ginecobstetricos TEXT")
    if "medicamentos_actuales" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN medicamentos_actuales TEXT")
    if "otros_antecedentes" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN otros_antecedentes TEXT")
    if "antecedentes_familiares" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN antecedentes_familiares TEXT")
    if "presion_arterial" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN presion_arterial TEXT")
    if "saturacion_oxigeno" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN saturacion_oxigeno TEXT")
    if "frecuencia_cardiaca" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN frecuencia_cardiaca TEXT")
    if "frecuencia_respiratoria" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN frecuencia_respiratoria TEXT")
    if "glicemia" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN glicemia TEXT")
    if "dolor" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN dolor TEXT")
    if "diagnostico_cie10" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN diagnostico_cie10 TEXT")
    if "datos_complementarios" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN datos_complementarios LONGTEXT")
    if "atencion_colectiva_id" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN atencion_colectiva_id INTEGER")
    if "finalizado" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN finalizado INTEGER DEFAULT 1")
    if "pertenencia_etnica" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN pertenencia_etnica TEXT")
    if "discapacidad" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN discapacidad TEXT")
    if "habitante_calle" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN habitante_calle TEXT")
    if "aplica_acompanante" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN aplica_acompanante TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN acompanante_nombre TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN acompanante_tipo_doc TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN acompanante_doc TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN acompanante_telefono TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN acompanante_parentesco TEXT")
    if "aplica_responsable" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN aplica_responsable TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN responsable_nombre TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN responsable_tipo_doc TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN responsable_doc TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN responsable_telefono TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN responsable_parentesco TEXT")
    if "primer_respondiente" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN primer_respondiente TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN es_emergencia_medica TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN detalle_emergencia_medica TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN es_emergencia_traumatica TEXT")
        conn.execute("ALTER TABLE pacientes ADD COLUMN detalle_emergencia_traumatica TEXT")
    if "triage_fecha_hora" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN triage_fecha_hora TEXT")
    if "triage_clasificacion" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN triage_clasificacion TEXT")
    if "glasgow_ocular" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN glasgow_ocular TEXT")
    if "glasgow_verbal" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN glasgow_verbal TEXT")
    if "glasgow_motora" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN glasgow_motora TEXT")
    if "glasgow_total" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN glasgow_total TEXT")
    if "estado_consciencia" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN estado_consciencia TEXT")
    if "cincinnati_facial" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN cincinnati_facial TEXT")
    if "cincinnati_brazo" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN cincinnati_brazo TEXT")
    if "cincinnati_habla" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN cincinnati_habla TEXT")
    if "cincinnati_total" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN cincinnati_total TEXT")
    if "rts_total" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN rts_total TEXT")
    if "evaluacion_inicial" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN evaluacion_inicial TEXT")
    if "examen_fisico" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN examen_fisico TEXT")
    if "triage_mci" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN triage_mci TEXT")
    if "soat_aseguradora" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN soat_aseguradora TEXT")
    if "soat_vigencia" not in pacientes_columns:
        conn.execute("ALTER TABLE pacientes ADD COLUMN soat_vigencia TEXT")

    # Add indexes for pacientes query performance
    cursor.execute("SHOW INDEX FROM pacientes")
    pacientes_indexes = [row["Key_name"] for row in cursor.fetchall()]
    pacientes_index_map = {
        "idx_pacientes_fecha_registro": "CREATE INDEX idx_pacientes_fecha_registro ON pacientes(fecha_registro(255))",
        "idx_pacientes_registrado_por_id": "CREATE INDEX idx_pacientes_registrado_por_id ON pacientes(registrado_por_identificacion(255))",
        "idx_pacientes_finalizado": "CREATE INDEX idx_pacientes_finalizado ON pacientes(finalizado)",
        "idx_pacientes_atencion_colectiva_id": "CREATE INDEX idx_pacientes_atencion_colectiva_id ON pacientes(atencion_colectiva_id)",
        "idx_pacientes_identificacion_paciente": "CREATE INDEX idx_pacientes_identificacion_paciente ON pacientes(identificacion_paciente(255))",
        "idx_pacientes_fecha_inicio_atencion": "CREATE INDEX idx_pacientes_fecha_inicio_atencion ON pacientes(fecha_inicio_atencion(255))",
    }
    for idx_name, idx_sql in pacientes_index_map.items():
        if idx_name not in pacientes_indexes:
            try:
                conn.execute(idx_sql)
            except Exception as e:
                print(f"Index creation error ({idx_name}):", e)
 
    # Migration for atencion_colectiva new date fields
    try:
        cursor.execute("DESCRIBE atencion_colectiva")
        ac_columns = [row["Field"] for row in cursor.fetchall()]
        if "fecha_inicio" not in ac_columns:
            conn.execute("ALTER TABLE atencion_colectiva ADD COLUMN fecha_inicio TEXT")
        if "hora_inicio" not in ac_columns:
            conn.execute("ALTER TABLE atencion_colectiva ADD COLUMN hora_inicio TEXT")
        if "fecha_finalizacion" not in ac_columns:
            conn.execute("ALTER TABLE atencion_colectiva ADD COLUMN fecha_finalizacion TEXT")
        if "hora_finalizacion" not in ac_columns:
            conn.execute("ALTER TABLE atencion_colectiva ADD COLUMN hora_finalizacion TEXT")
        
        if "fecha" in ac_columns:
            conn.execute("UPDATE atencion_colectiva SET fecha_inicio = fecha WHERE fecha_inicio IS NULL OR fecha_inicio = ''")
        if "hora" in ac_columns:
            conn.execute("UPDATE atencion_colectiva SET hora_inicio = hora WHERE hora_inicio IS NULL OR hora_inicio = ''")
            
        if "fecha" in ac_columns:
            conn.execute("ALTER TABLE atencion_colectiva DROP COLUMN fecha")
        if "hora" in ac_columns:
            conn.execute("ALTER TABLE atencion_colectiva DROP COLUMN hora")
        if "finalizado" not in ac_columns:
            conn.execute("ALTER TABLE atencion_colectiva ADD COLUMN finalizado INTEGER DEFAULT 0")
    except Exception as e:
        print("Migration error:", e)
 
    # Migration for eventos new fields
    try:
        cursor.execute("DESCRIBE eventos")
        ev_columns = [row["Field"] for row in cursor.fetchall()]
        for col in ["fecha_inicio", "hora_inicio", "fecha_finalizacion", "hora_finalizacion", "firma_coordinador_evento"]:
            if col not in ev_columns:
                conn.execute(f"ALTER TABLE eventos ADD COLUMN {col} TEXT")
    except Exception:
        pass
        
    # Migration for configuracion valor to LONGTEXT
    try:
        conn.execute("ALTER TABLE configuracion MODIFY COLUMN valor LONGTEXT")
    except Exception as e:
        print("Migration configuracion valor error:", e)
        pass

    # Migration for edad to VARCHAR
    try:
        conn.execute("ALTER TABLE pacientes MODIFY COLUMN edad VARCHAR(50)")
    except Exception as e:
        print("Migration edad error:", e)
        pass

 
    conn.execute("UPDATE usuarios SET contrasena = identificacion WHERE contrasena IS NULL OR contrasena = ''")
    
    # Migrar contraseñas en texto plano a hashes seguros
    usuarios_plain = conn.execute("SELECT id, contrasena FROM usuarios WHERE contrasena NOT LIKE 'scrypt:%' AND contrasena NOT LIKE 'pbkdf2:%'").fetchall()
    for u in usuarios_plain:
        hashed_pw = generate_password_hash(u["contrasena"])
        conn.execute("UPDATE usuarios SET contrasena = ? WHERE id = ?", (hashed_pw, u["id"]))
        
    admin_exists = conn.execute("SELECT * FROM usuarios WHERE identificacion = 'admin'").fetchone()
    admin_pass = 'admin'
    admin_pass_hashed = generate_password_hash(admin_pass)
    if not admin_exists:
        conn.execute("""
            INSERT INTO usuarios (nombre, identificacion, registro_medico, rol, perfil, activo, firma, contrasena, requiere_cambio_clave, correo)
            VALUES ('Administrador', 'admin', 'admin', 'admin', ?, 1, '', ?, 0, '')
        """, (json.dumps(["Administrador"]), admin_pass_hashed))
    else:
        # Asegurarnos de que el administrador tenga rol y perfil correctos. 
        # (Se omite sobreescribir la contraseña si ya existe, a menos que queramos forzarla a 'admin' siempre.
        # Anteriormente se forzaba, lo dejaremos igual pero cifrada, aunque sería mejor no sobreescribirla siempre.
        # Si el usuario cambia la clave, esto se la resetearía cada reinicio, lo mejor es no sobreescribir contrasena.)
        conn.execute("""
            UPDATE usuarios
            SET rol = 'admin', perfil = ?
            WHERE identificacion = 'admin'
        """, (json.dumps(["Administrador"]),))
        
    cursor.execute("DESCRIBE pacientes")
    pacientes_cols = [row["Field"] for row in cursor.fetchall()]
    new_paciente_cols = [
        "soat_aseguradora", "soat_vigencia",
        "hora_despacho", "hora_arribo", "nombre_evento", "tipo_servicio",
        "departamento", "municipio", "barrio", "direccion_atencion",
        "ambito_territorial", "entorno_atencion", "clasificacion",
        "causa_motiva_atencion", "tipo_traslado", "entorno_otro",
        "inmovilizacion", "otros_procedimientos", "ventilacion_mecanica", "torniquete",
        "x_items", "a_items", "b_items", "c_items", "d_items", "e_items", "datos_complementarios"
    ]
    for col in new_paciente_cols:
        if col not in pacientes_cols:
            try:
                conn.execute(f"ALTER TABLE pacientes ADD COLUMN {col} TEXT")
            except Exception as e:
                print(f"Error adding {col} to pacientes:", e)
        
    cursor.execute("DESCRIBE checklist_tam")
    if "datos_json" not in [row["Field"] for row in cursor.fetchall()]:
        try:
            conn.execute("ALTER TABLE checklist_tam ADD COLUMN datos_json TEXT")
        except Exception:
            pass
            
    cursor.execute("DESCRIBE checklist_tab")
    if "datos_json" not in [row["Field"] for row in cursor.fetchall()]:
        try:
            conn.execute("ALTER TABLE checklist_tab ADD COLUMN datos_json TEXT")
        except Exception:
            pass
 
    cursor.execute("DESCRIBE checklist_pasb")
    pasb_cols = [row["Field"] for row in cursor.fetchall()]
    if "datos_json" not in pasb_cols:
        try:
            conn.execute("ALTER TABLE checklist_pasb ADD COLUMN datos_json TEXT")
        except Exception:
            pass
    if "pasb_numero" not in pasb_cols:
        try:
            conn.execute("ALTER TABLE checklist_pasb ADD COLUMN pasb_numero TEXT")
        except Exception:
            pass
 
    cursor.execute("DESCRIBE checklist_pasm")
    pasm_cols = [row["Field"] for row in cursor.fetchall()]
    if "datos_json" not in pasm_cols:
        try:
            conn.execute("ALTER TABLE checklist_pasm ADD COLUMN datos_json TEXT")
        except Exception:
            pass
    if "pasm_numero" not in pasm_cols:
        try:
            conn.execute("ALTER TABLE checklist_pasm ADD COLUMN pasm_numero TEXT")
        except Exception:
            pass
 
    cursor.execute("DESCRIBE preoperacional")
    preop_cols = [row["Field"] for row in cursor.fetchall()]
    if "datos_json" not in preop_cols:
        try:
            conn.execute("ALTER TABLE preoperacional ADD COLUMN datos_json TEXT")
        except Exception:
            pass
            
    if "evidencia" not in preop_cols:
        try:
            conn.execute("ALTER TABLE preoperacional ADD COLUMN evidencia TEXT")
        except Exception:
            pass
            
    if "finalizado" not in preop_cols:
        try:
            conn.execute("ALTER TABLE preoperacional ADD COLUMN finalizado INTEGER DEFAULT 1")
        except Exception:
            pass
            
    for col in ("tipo_vehiculo", "tipo_ambulancia", "movil", "marca", "serie", "modelo", "soat_vigencia", "rtm_vigencia", "proximo_aceite"):
        if col not in preop_cols:
            try:
                conn.execute(f"ALTER TABLE preoperacional ADD COLUMN {col} TEXT")
            except Exception:
                pass

    # ── Checklist tables: add finalizado column if missing ──────────────────────
    for _cl_table in ("checklist_tam", "checklist_tab", "checklist_pasb", "checklist_pasm", "checklist_equipos", "checklist_avanzada"):
        try:
            cursor = conn.execute(f"SHOW COLUMNS FROM {_cl_table}")
            _cl_cols = [row["Field"] for row in cursor.fetchall()]
            if "finalizado" not in _cl_cols:
                conn.execute(f"ALTER TABLE {_cl_table} ADD COLUMN finalizado INTEGER DEFAULT 1")
        except Exception:
            pass

    # ── Checklist avanzada: add evento and botiquin columns if missing ──────────
    try:
        cursor = conn.execute("SHOW COLUMNS FROM checklist_avanzada")
        _avanzada_cols = [row["Field"] for row in cursor.fetchall()]
        for col in ("evento", "botiquin"):
            if col not in _avanzada_cols:
                conn.execute(f"ALTER TABLE checklist_avanzada ADD COLUMN {col} TEXT")
    except Exception:
        pass

    # Migration for calif_atencion responsable fields
    try:
        cursor.execute("DESCRIBE calif_atencion")
        calif_cols = [row["Field"] for row in cursor.fetchall()]
        if "responsable_nombre" not in calif_cols:
            conn.execute("ALTER TABLE calif_atencion ADD COLUMN responsable_nombre TEXT")
        if "responsable_apellido" not in calif_cols:
            conn.execute("ALTER TABLE calif_atencion ADD COLUMN responsable_apellido TEXT")
        if "responsable_tipo_doc" not in calif_cols:
            conn.execute("ALTER TABLE calif_atencion ADD COLUMN responsable_tipo_doc TEXT")
        if "responsable_identificacion" not in calif_cols:
            conn.execute("ALTER TABLE calif_atencion ADD COLUMN responsable_identificacion TEXT")
    except Exception:
        pass
            
    seed_preop = [
        ('Mecánica', 'frenos', 'Frenos (servicio y parqueo)'),
        ('Mecánica', 'direccion_vehiculo', 'Dirección'),
        ('Mecánica', 'luces_emergencia', 'Luces de emergencia (estrobos/sirena)'),
        ('Mecánica', 'luces_normales', 'Luces normales (alto, bajo, direccionales)'),
        ('Mecánica', 'sirena', 'Sirena y altavoz'),
        ('Mecánica', 'senalizacion', 'Señalización externa (conos, triángulos)'),
        ('Mecánica', 'llantas', 'Llantas (presión y estado)'),
        ('Mecánica', 'carroceria', 'Carrocería sin daños'),
        ('Mecánica', 'espejos', 'Espejos retrovisores'),
        ('Mecánica', 'documentos_vehiculo', 'Documentos del vehículo (SOAT, tecno)'),
        ('Mecánica', 'comunicaciones', 'Radio comunicaciones'),
        ('Médica', 'botiquin', 'Botiquín médico completo'),
        ('Médica', 'oxigeno', 'Cilindro de oxígeno (lleno)'),
        ('Médica', 'camilla', 'Camilla en buen estado'),
        ('Médica', 'inmovilizadores', 'Inmovilizadores (collarín, tabla espinal)'),
        ('Médica', 'desfibrilador', 'Desfibrilador / DEA (cargado)')
    ]
    for cat, ident, name in seed_preop:
        exists = conn.execute("SELECT id FROM checklist_items WHERE tipo_checklist = 'preoperacional' AND identificador = ?", (ident,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO checklist_items (tipo_checklist, categoria, identificador, nombre, activo) VALUES ('preoperacional', ?, ?, ?, 1)",
                (cat, ident, name)
            )

    seed_equipos = [
        ('Monitor Desfibrilador', 'mon_carcasa', 'Carcasa y pantalla limpias y sin grietas'),
        ('Monitor Desfibrilador', 'mon_cables', 'Cables de paciente (ECG, SpO2, NIBP) en buen estado'),
        ('Monitor Desfibrilador', 'mon_bateria', 'Batería cargada e indicación de carga correcta'),
        ('Monitor Desfibrilador', 'mon_paletas', 'Paletas externas limpias y bien conectadas'),
        ('Monitor Desfibrilador', 'mon_gel', 'Gel conductor disponible'),
        ('Monitor Desfibrilador', 'mon_papel', 'Papel de registro termo-sensible instalado'),
        
        ('Ventilador Mecánico', 'vent_limpieza', 'Limpieza externa general y estado físico'),
        ('Ventilador Mecánico', 'vent_circuitos', 'Circuitos de paciente limpios y sin fugas'),
        ('Ventilador Mecánico', 'vent_mangueras', 'Mangueras de gases medicinales conectadas y seguras'),
        ('Ventilador Mecánico', 'vent_bateria', 'Batería interna cargada y conexión eléctrica'),
        ('Ventilador Mecánico', 'vent_alarmas', 'Prueba de alarmas funcional'),
        
        ('Bomba de Infusión', 'bomba_carcasa', 'Carcasa y pinza de sujeción (clamp) en buen estado'),
        ('Bomba de Infusión', 'bomba_cable', 'Cable de alimentación y enchufe sin daños'),
        ('Bomba de Infusión', 'bomba_bateria', 'Batería operativa (mantiene carga)'),
        ('Bomba de Infusión', 'bomba_sensor', 'Sensor de gotas y de aire operativos'),
        
        ('Aspirador de Secreciones', 'asp_frasco', 'Frasco recolector limpio y con tapa sellada'),
        ('Aspirador de Secreciones', 'asp_mangueras', 'Mangueras de succión y filtros limpios y sin obstrucción'),
        ('Aspirador de Secreciones', 'asp_vacio', 'Nivel de vacío y succión funcional'),
        ('Aspirador de Secreciones', 'asp_bateria', 'Batería / Conexión eléctrica funcional'),
        
        ('Glucómetro', 'gluc_pantalla', 'Pantalla y encendido correcto del equipo'),
        ('Glucómetro', 'gluc_tiras', 'Tiras reactivas vigentes y disponibles en el stock'),
        ('Glucómetro', 'gluc_lancetas', 'Lancetas y dispositivo punzón listos para uso')
    ]
    for cat, ident, name in seed_equipos:
        exists = conn.execute("SELECT id FROM checklist_items WHERE tipo_checklist = 'equipos' AND identificador = ?", (ident,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO checklist_items (tipo_checklist, categoria, identificador, nombre, activo) VALUES ('equipos', ?, ?, ?, 1)",
                (cat, ident, name)
            )
 
    if "datos_json" not in preop_cols:
        old_records = conn.execute("SELECT * FROM preoperacional").fetchall()
        for rec in old_records:
            datos = {}
            for cat, ident, name in seed_preop:
                try:
                    val = rec[ident]
                except Exception:
                    val = ""
                datos[ident] = {
                    "nombre": name,
                    "categoria": cat,
                    "valor": val if val else ""
                }
            conn.execute("UPDATE preoperacional SET datos_json = ? WHERE id = ?", (json.dumps(datos, ensure_ascii=False), rec["id"]))
 
    existing_cats = conn.execute("SELECT DISTINCT tipo_checklist, categoria FROM checklist_items").fetchall()
    for row in existing_cats:
        tipo = row["tipo_checklist"]
        cat = row["categoria"]
        cat_exists = conn.execute("SELECT id FROM checklist_categorias WHERE tipo_checklist = ? AND nombre = ?", (tipo, cat)).fetchone()
        if not cat_exists:
            conn.execute("INSERT INTO checklist_categorias (tipo_checklist, nombre, activo) VALUES (?, ?, 1)", (tipo, cat))
 
    count_aseguradoras = conn.execute("SELECT COUNT(*) as count FROM aseguradoras").fetchone()["count"]
    if count_aseguradoras == 0:
        for a in ASEGURADORAS:
            conn.execute("INSERT IGNORE INTO aseguradoras (nombre, activo) VALUES (?, 1)", (a,))

    # Dynamic migration for usuarios table
    try:
        cursor = conn.cursor()
        cursor.execute("DESCRIBE usuarios")
        usuarios_cols = [row["Field"] for row in cursor.fetchall()]
        if "fecha_validez" not in usuarios_cols:
            conn.execute("ALTER TABLE usuarios ADD COLUMN fecha_validez DATE DEFAULT NULL")
    except Exception as e:
        print("Error al migrar la tabla usuarios:", e)

    # Dynamic migration for vehiculos table
    try:
        cursor.execute("DESCRIBE vehiculos")
        vehiculos_cols = [row["Field"] for row in cursor.fetchall()]
        if "marca" not in vehiculos_cols:
            conn.execute("ALTER TABLE vehiculos ADD COLUMN marca TEXT")
        if "serie" not in vehiculos_cols:
            conn.execute("ALTER TABLE vehiculos ADD COLUMN serie TEXT")
        if "modelo" not in vehiculos_cols:
            conn.execute("ALTER TABLE vehiculos ADD COLUMN modelo TEXT")
        if "tipo_ambulancia" not in vehiculos_cols:
            conn.execute("ALTER TABLE vehiculos ADD COLUMN tipo_ambulancia TEXT")
        if "soat_vigencia" not in vehiculos_cols:
            conn.execute("ALTER TABLE vehiculos ADD COLUMN soat_vigencia DATE")
        if "rtm_vigencia" not in vehiculos_cols:
            conn.execute("ALTER TABLE vehiculos ADD COLUMN rtm_vigencia DATE")
        if "movil" not in vehiculos_cols:
            conn.execute("ALTER TABLE vehiculos ADD COLUMN movil TEXT")
    except Exception as e:
        print("Error al migrar la tabla vehiculos:", e)

    # Dynamic migration for atencion_vehiculo table
    try:
        cursor = conn.cursor()
        cursor.execute("DESCRIBE atencion_vehiculo")
        atencion_vehiculo_cols = [row["Field"] for row in cursor.fetchall()]
        if "equipos_json" not in atencion_vehiculo_cols:
            conn.execute("ALTER TABLE atencion_vehiculo ADD COLUMN equipos_json TEXT")
        if "finalizado" not in atencion_vehiculo_cols:
            conn.execute("ALTER TABLE atencion_vehiculo ADD COLUMN finalizado INTEGER DEFAULT 1")
    except Exception as e:
        print("Error al migrar la tabla atencion_vehiculo:", e)

    # Dynamic migration for checklist_items table
    try:
        cursor = conn.cursor()
        cursor.execute("DESCRIBE checklist_items")
        checklist_items_cols = [row["Field"] for row in cursor.fetchall()]
        if "cantidad" not in checklist_items_cols:
            conn.execute("ALTER TABLE checklist_items ADD COLUMN cantidad INT DEFAULT NULL")
    except Exception as e:
        print("Error al migrar la tabla checklist_items:", e)

    # Dynamic migration for archivador table
    try:
        cursor = conn.cursor()
        cursor.execute("DESCRIBE archivador")
        archivador_cols = [row["Field"] for row in cursor.fetchall()]
        if "categoria" not in archivador_cols:
            conn.execute("ALTER TABLE archivador ADD COLUMN categoria TEXT")
        if "descripcion" not in archivador_cols:
            conn.execute("ALTER TABLE archivador ADD COLUMN descripcion TEXT")
        if "fecha_documento" not in archivador_cols:
            conn.execute("ALTER TABLE archivador ADD COLUMN fecha_documento TEXT")
    except Exception as e:
        print("Error al migrar la tabla archivador:", e)

    # ── archivador_categorias table ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS archivador_categorias (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            nombre VARCHAR(255) NOT NULL UNIQUE,
            activo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i:%s'))
        )
    """)
    cat_count = conn.execute("SELECT COUNT(*) as count FROM archivador_categorias").fetchone()["count"]
    if cat_count == 0:
        default_categorias = [
            "Administrativo", "Médico", "Legal",
            "Operativo", "Capacitación", "Mantenimiento", "Otro"
        ]
        for c in default_categorias:
            try:
                conn.execute("INSERT INTO archivador_categorias (nombre, activo) VALUES (?, 1)", (c,))
            except Exception:
                pass

    # ── archivador_formularios table ──
    conn.execute("""
        CREATE TABLE IF NOT EXISTS archivador_formularios (
            id INTEGER PRIMARY KEY AUTO_INCREMENT,
            nombre VARCHAR(255) NOT NULL UNIQUE,
            activo INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i:%s'))
        )
    """)
    frm_count = conn.execute("SELECT COUNT(*) as count FROM archivador_formularios").fetchone()["count"]
    if frm_count == 0:
        default_formularios = [
            "Calif. Atención", "Seguridad del Paciente", "Historia Clínica Individual",
            "Atención Vehículo de Intervención", "Preoperacional Conductores",
            "Check List TAM", "Check List TAB", "Check List Avanzada",
            "Check List PASB", "Check List PASM", "Preoperacional de Equipos",
            "Formulario de Eventos", "Atención Colectiva"
        ]
        for f in default_formularios:
            try:
                conn.execute("INSERT INTO archivador_formularios (nombre, activo) VALUES (?, 1)", (f,))
            except Exception:
                pass

    # Dynamic migration: add categoria_id to archivador_formularios
    try:
        cursor = conn.cursor()
        cursor.execute("DESCRIBE archivador_formularios")
        af_cols = [row["Field"] for row in cursor.fetchall()]
        if "categoria_id" not in af_cols:
            conn.execute("ALTER TABLE archivador_formularios ADD COLUMN categoria_id INTEGER DEFAULT NULL")
    except Exception as e:
        print("Error al migrar archivador_formularios:", e)

    # ── Additional indexes for query performance ──
    cursor.execute("SHOW INDEX FROM preoperacional")
    preop_idx = [row["Key_name"] for row in cursor.fetchall()]
    for name, sql in {
        "idx_preop_fecha_registro": "CREATE INDEX idx_preop_fecha_registro ON preoperacional(fecha_registro(255))",
        "idx_preop_registrado_por": "CREATE INDEX idx_preop_registrado_por ON preoperacional(registrado_por_identificacion(255))",
        "idx_preop_placa": "CREATE INDEX idx_preop_placa ON preoperacional(placa_vehiculo(255))",
    }.items():
        if name not in preop_idx:
            try: conn.execute(sql)
            except: pass

    cursor.execute("SHOW INDEX FROM eventos")
    ev_idx = [row["Key_name"] for row in cursor.fetchall()]
    for name, sql in {
        "idx_eventos_fecha_registro": "CREATE INDEX idx_eventos_fecha_registro ON eventos(fecha_registro(255))",
        "idx_eventos_registrado_por": "CREATE INDEX idx_eventos_registrado_por ON eventos(registrado_por_identificacion(255))",
    }.items():
        if name not in ev_idx:
            try: conn.execute(sql)
            except: pass

    cursor.execute("SHOW INDEX FROM atencion_vehiculo")
    av_idx = [row["Key_name"] for row in cursor.fetchall()]
    for name, sql in {
        "idx_av_fecha_registro": "CREATE INDEX idx_av_fecha_registro ON atencion_vehiculo(fecha_registro(255))",
        "idx_av_registrado_por": "CREATE INDEX idx_av_registrado_por ON atencion_vehiculo(registrado_por_identificacion(255))",
    }.items():
        if name not in av_idx:
            try: conn.execute(sql)
            except: pass

    cursor.execute("SHOW INDEX FROM atencion_colectiva")
    ac_idx = [row["Key_name"] for row in cursor.fetchall()]
    for name, sql in {
        "idx_ac_fecha_registro": "CREATE INDEX idx_ac_fecha_registro ON atencion_colectiva(fecha_registro(255))",
        "idx_ac_registrado_por": "CREATE INDEX idx_ac_registrado_por ON atencion_colectiva(registrado_por_identificacion(255))",
        "idx_ac_finalizado": "CREATE INDEX idx_ac_finalizado ON atencion_colectiva(finalizado)",
    }.items():
        if name not in ac_idx:
            try: conn.execute(sql)
            except: pass

    cursor.execute("SHOW INDEX FROM vehiculos")
    veh_idx = [row["Key_name"] for row in cursor.fetchall()]
    for name, sql in {
        "idx_vehiculos_placa": "CREATE INDEX idx_vehiculos_placa ON vehiculos(placa(255))",
        "idx_vehiculos_tipo": "CREATE INDEX idx_vehiculos_tipo ON vehiculos(tipo(255))",
    }.items():
        if name not in veh_idx:
            try: conn.execute(sql)
            except: pass

    conn.commit()
    conn.close()
