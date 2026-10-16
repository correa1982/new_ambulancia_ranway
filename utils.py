from datetime import date, datetime
from functools import wraps
from flask import session, redirect, url_for, flash, request
import os
import smtplib
from email.message import EmailMessage
import zoneinfo

COL_TZ = zoneinfo.ZoneInfo("America/Bogota")

def ahora():
    return datetime.now(COL_TZ)

def get_configuracion(conn=None):
    close_after = False
    if conn is None:
        from db import get_db
        conn = get_db()
        close_after = True
    try:
        cursor = conn.execute("SELECT clave, valor FROM configuracion")
        rows = cursor.fetchall()
        cfg = {}
        for row in rows:
            if isinstance(row, dict):
                cfg[row['clave']] = row['valor']
            else:
                cfg[row[0]] = row[1]

        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if not cfg.get("logo"):
            for ext in ['png', 'jpg', 'jpeg']:
                if os.path.exists(os.path.join(base_dir, 'static', 'uploads', f'logo_institucion.{ext}')):
                    cfg["logo"] = f"/static/uploads/logo_institucion.{ext}"
                    break
        cfg['logo_url'] = cfg.get('logo')

        if not cfg.get("marca_agua"):
            for ext in ['jpg', 'png', 'jpeg']:
                if os.path.exists(os.path.join(base_dir, 'static', 'uploads', f'marca_agua_institucion.{ext}')):
                    cfg["marca_agua"] = f"/static/uploads/marca_agua_institucion.{ext}"
                    break
        if not cfg.get("nombre_sistema") or cfg.get("nombre_sistema") == "HC Prehospitalario":
            cfg["nombre_sistema"] = "Gestion Institucional y Operativa"
        return cfg
    except Exception:
        return {}
    finally:
        if close_after:
            try:
                conn.close()
            except Exception:
                pass


def hoy():
    return ahora().date()

def calcular_edad(fecha_nac_str):
    try:
        fecha_nac = datetime.strptime(fecha_nac_str, "%Y-%m-%d").date()
    except Exception:
        return ""
    fecha_hoy = hoy()
    
    dias_totales = (fecha_hoy - fecha_nac).days
    if dias_totales < 0:
        return "0 días"
        
    años = fecha_hoy.year - fecha_nac.year - ((fecha_hoy.month, fecha_hoy.day) < (fecha_nac.month, fecha_nac.day))
    if años >= 1:
        return f"{años} años"
        
    # Calculate months
    meses = (fecha_hoy.year - fecha_nac.year) * 12 + fecha_hoy.month - fecha_nac.month
    if fecha_hoy.day < fecha_nac.day:
        meses -= 1
        
    if meses >= 1:
        return f"{meses} meses"
        
    return f"{dias_totales} días"


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session:
            if request.form.get("_offline_sync") == "1":
                from flask import jsonify
                return jsonify({"status": "error", "message": "No autenticado"}), 401
            return redirect(url_for("login"))
        # Force password change if required
        if session["usuario"].get("requiere_cambio_clave") == 1:
            if request.endpoint not in ("cambiar_contrasena", "logout", "static"):
                flash("Debe cambiar su contraseña antes de continuar.", "error")
                return redirect(url_for("cambiar_contrasena"))
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "usuario" not in session or session["usuario"].get("rol") != "admin":
            flash("Acceso no autorizado. Debe ser administrador.", "error")
            return redirect(url_for("formulario"))
        return f(*args, **kwargs)

    return decorated


def get_user_info(conn, identificacion):
    """Helper: fetch registrador info from DB."""
    u = conn.execute("SELECT * FROM usuarios WHERE identificacion = ?", (identificacion,)).fetchone()
    if u:
        active_perfil = session["usuario"].get("perfil", "") if "usuario" in session else u["perfil"]
        return u["firma"], active_perfil, u["registro_medico"]
    return "", "", ""

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {
    "pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "txt", "csv", "odt", "ods", "rtf", "zip",
}


def validar_upload_imagen(file_obj, max_size_mb=5):
    """Valida que el archivo sea una imagen (extensión + firma/magic bytes) permitida.
    Devuelve la extensión minúscula validada, o None si no es válido."""
    if file_obj is None:
        return None
    filename = (file_obj.filename or "").strip()
    if not filename or "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None

    header = file_obj.stream.read(16)
    file_obj.stream.seek(0)
    magic_ok = (
        (ext == "jpeg" or ext == "jpg") and header[:3] == b"\xff\xd8\xff" or
        ext == "png" and header[:8] == b"\x89PNG\r\n\x1a\n" or
        ext == "gif" and header[:6] in (b"GIF87a", b"GIF89a") or
        ext == "webp" and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    )
    if not magic_ok:
        return None

    file_obj.stream.seek(0, os.SEEK_END)
    size = file_obj.stream.tell()
    file_obj.stream.seek(0)
    if size > max_size_mb * 1024 * 1024:
        return None
    return ext


def validar_upload_documento(file_obj, max_size_mb=25):
    """Valida uploads de documentos/papelería (archivador) por extensión permitida y tamaño."""
    if file_obj is None:
        return False
    filename = (file_obj.filename or "").strip()
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        return False

    file_obj.stream.seek(0, os.SEEK_END)
    size = file_obj.stream.tell()
    file_obj.stream.seek(0)
    if size > max_size_mb * 1024 * 1024:
        return False
    return True


def validar_upload_excel(file_obj, max_size_mb=10):
    """Valida que el archivo sea un Excel (.xls/.xlsx) por extensión y firma.
    Devuelve la extensión minúscula validada o None."""
    if file_obj is None:
        return None
    filename = (file_obj.filename or "").strip()
    if not filename or "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[1].lower()
    if ext not in ("xls", "xlsx", "csv"):
        return None

    header = file_obj.stream.read(8)
    file_obj.stream.seek(0)
    magic_ok = (
        ext == "xls" and header[:4] == b"\xd0\xcf\x11\xe0" or
        ext == "xlsx" and header[:2] == b"PK" or
        ext == "csv"
    )
    if not magic_ok:
        return None

    file_obj.stream.seek(0, os.SEEK_END)
    size = file_obj.stream.tell()
    file_obj.stream.seek(0)
    if size > max_size_mb * 1024 * 1024:
        return None
    return ext


def send_recovery_email(to_email, temp_password):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    
    if not host or not user or not password:
        print("SMTP no configurado.")
        return False
        
    msg = EmailMessage()
    msg['Subject'] = 'Recuperación de Contraseña - Gestion Institucional y Operativa'
    msg['From'] = user
    msg['To'] = to_email
    
    msg.set_content(f"Hola,\n\nSe ha solicitado la recuperación de contraseña para tu cuenta.\nTu nueva contraseña temporal es: {temp_password}\n\nPor favor, inicia sesión con esta contraseña y cámbiala inmediatamente.\n\nSaludos,\nEl equipo de S G A - Gestion Institucional y Operativa.")

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as e:
        print("Error sending email:", e)
        return False
