from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory, Response
from datetime import date, datetime, timedelta
from functools import lru_cache
import os
import json
from constants import TIPOS_DOCUMENTO, TIPOS_AFILIACION, ASEGURADORAS
from db import get_db, init_db, close_all
from utils import calcular_edad, login_required, admin_required, get_user_info
from itsdangerous import URLSafeSerializer, BadSignature

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from flask_compress import Compress

app = Flask(__name__)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
Compress(app)

# Usamos os.urandom como respaldo seguro en caso de que falte en el .env
app.secret_key = os.getenv("SECRET_KEY", os.urandom(24))
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 86400
app.permanent_session_lifetime = timedelta(minutes=30)

serializer = URLSafeSerializer(app.secret_key)

_db_initialized = False

@app.before_request
def ensure_db_initialized():
    global _db_initialized
    if not _db_initialized:
        try:
            init_db()
            _db_initialized = True
            app.logger.info("Base de datos inicializada correctamente.")
        except Exception as exc:
            app.logger.error("No se pudo inicializar la base de datos en el arranque: %s", exc)
            app.logger.error("Verifique que las variables de entorno de MySQL/DATABASE_URL estén configuradas y que el servicio esté disponible.")
            return Response(
                "<h1>Servicio temporalmente no disponible</h1><p>La base de datos no está accesible en este momento. Intente nuevamente más tarde.</p>",
                status=503,
                mimetype='text/html'
            )

@app.after_request
def add_cache_control(response):
    if 'Cache-Control' not in response.headers:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    return response

@app.template_filter('encode_id')
def encode_id_filter(id_val):
    if not id_val:
        return ""
    return serializer.dumps(id_val)

@app.template_filter('from_json')
def from_json_filter(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except Exception:
        return []

@app.template_filter('calcular_diferencia_tiempo')
def calcular_diferencia_tiempo(fecha_inicio, fecha_fin):
    if not fecha_inicio or not fecha_fin:
        return "—"
    try:
        t1_str = str(fecha_inicio).replace('T', ' ')
        t2_str = str(fecha_fin).replace('T', ' ')
        fmt1 = "%Y-%m-%d %H:%M:%S"
        fmt2 = "%Y-%m-%d %H:%M"
        try:
            t1 = datetime.strptime(t1_str, fmt1)
        except ValueError:
            t1 = datetime.strptime(t1_str, fmt2)
        try:
            t2 = datetime.strptime(t2_str, fmt1)
        except ValueError:
            t2 = datetime.strptime(t2_str, fmt2)
        diff = t2 - t1
        total_seconds = int(diff.total_seconds())
        if total_seconds < 0:
            return "Inconsistente"
        minutes = total_seconds // 60
        hours = minutes // 60
        rem_minutes = minutes % 60
        if hours > 0:
            return f"{hours}h {rem_minutes}m"
        else:
            return f"{minutes} min"
    except Exception:
        return "—"

@app.template_filter('format_habilitacion')
def format_habilitacion_filter(value):
    if not value:
        return ""
    from markupsafe import Markup
    try:
        import json
        data = json.loads(value)
        if isinstance(data, list):
            parts = []
            for item in data:
                code = item.get("codigo", "").strip()
                desc = item.get("descripcion", "").strip()
                if code and desc:
                    parts.append(f"{code} - {desc}")
                elif code:
                    parts.append(code)
                elif desc:
                    parts.append(desc)
            return Markup("<br>").join(parts)
    except Exception:
        pass
    
    parts = [p.strip() for p in str(value).split(" | ")]
    return Markup("<br>").join(parts)


@app.after_request
def add_header(response):
    if request.path == '/static/sw.js':
        response.headers['Service-Worker-Allowed'] = '/'
    return response

@app.teardown_appcontext
def shutdown_db(exception=None):
    close_all()

@app.errorhandler(500)
def handle_internal_error(error):
    app.logger.error("Internal server error: %s", error)
    return render_template('500.html', error=error), 500

@app.route("/logo.jpg")
def serve_logo():
    return send_from_directory(os.path.dirname(__file__), "logo.jpg")

@app.route("/sw.js")
def serve_sw():
    response = send_from_directory(os.path.join(os.path.dirname(__file__), "static"), "sw.js")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response




def get_cie10_data():
    if not hasattr(app, '_cie10'):
        cie10_path = os.path.join(os.path.dirname(__file__), "data", "cie10.json")
        with open(cie10_path, encoding="utf-8") as f:
            app._cie10 = json.load(f)
    return app._cie10




def parse_habilitaciones(value=None, legacy_value=None):
    entries = []

    if isinstance(value, str):
        value = value.strip()
        if value:
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    entries = parsed
                elif isinstance(parsed, dict):
                    entries = [parsed]
            except (TypeError, ValueError):
                pass

    if not entries and isinstance(legacy_value, str):
        legacy_value = legacy_value.strip()
        if legacy_value:
            try:
                parsed = json.loads(legacy_value)
                if isinstance(parsed, list):
                    entries = parsed
                elif isinstance(parsed, dict):
                    entries = [parsed]
            except (TypeError, ValueError):
                entries = [{"codigo": legacy_value, "descripcion": ""}]

    normalized = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        codigo = str(entry.get("codigo", "") or "").strip()
        descripcion = str(entry.get("descripcion", "") or "").strip()
        if codigo:
            normalized.append({"codigo": codigo, "descripcion": descripcion})

    return normalized


def format_habilitaciones(entries):
    if not entries:
        return ""

    formatted = []
    for entry in entries:
        codigo = str(entry.get("codigo", "") or "").strip()
        descripcion = str(entry.get("descripcion", "") or "").strip()
        if codigo:
            formatted.append(f"{codigo} - {descripcion}" if descripcion else codigo)
    return " | ".join(formatted)


@lru_cache(maxsize=1)
def _load_config():
    conn = get_db()
    try:
        cursor = conn.execute("SELECT clave, valor FROM configuracion")
        config = {row["clave"]: row["valor"] for row in cursor.fetchall()}
    except Exception:
        config = {}
    conn.close()

    if "nombre_institucion" not in config:
        config["nombre_institucion"] = "Servicio de Traslado Asistencial Médica"
    if "subtitulo_institucion" not in config:
        config["subtitulo_institucion"] = "RED DE ATENCIÓN PREHOSPITALARIA Y AMBULANCIAS"
    if "nit" not in config:
        config["nit"] = "NIT: 900.123.456-7"
    if "logo" not in config:
        config["logo"] = ""
    if "nombre_sistema" not in config:
        config["nombre_sistema"] = "HC Prehospitalario"

    habilitaciones = parse_habilitaciones(config.get("habilitaciones"), config.get("habilitacion"))
    if not habilitaciones and "habilitacion" not in config:
        habilitaciones = [{"codigo": "Habilitación N°: 050010987", "descripcion": ""}]

    config["habilitaciones"] = habilitaciones
    config["habilitacion"] = format_habilitaciones(habilitaciones)
    return config

def clear_config_cache():
    _load_config.cache_clear()

app.clear_config_cache = clear_config_cache

@app.context_processor
def inject_config():
    return {"institucion": _load_config()}



# Importar registradores
from routes.routes_auth import register_routes as register_auth
from routes.routes_patients import register_routes as register_patients
from routes.routes_admin import register_routes as register_admin
from routes.routes_events import register_routes as register_events
from routes.routes_preoperacional import register_routes as register_preoperacional
from routes.routes_checklists import register_routes as register_checklists
from routes.routes_api import register_routes as register_api
from routes.routes_registros_global import register_routes as register_registros_global
from routes.routes_atencion_vehiculo import register_routes as register_atencion_vehiculo
from routes.routes_archivador import register_routes as register_archivador

# Registrar todas las rutas
register_auth(app)
register_patients(app, serializer, TIPOS_DOCUMENTO, TIPOS_AFILIACION, ASEGURADORAS)
register_admin(app)
register_events(app)
register_preoperacional(app)
register_checklists(app)
register_api(app, get_cie10_data())
register_registros_global(app, serializer)
register_atencion_vehiculo(app)
register_archivador(app)

if __name__ == "__main__":
    
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        print("\n" + "="*60)
        print(" Aplicación disponible en tu red local.")
        print(f" Ingresa desde otro dispositivo (celular/tablet) a:")
        print(f"   http://{ip}:10000")
        print("="*60 + "\n")
    except Exception:
        pass
        

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
