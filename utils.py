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

def send_recovery_email(to_email, temp_password):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", 587))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    
    if not host or not user or not password:
        print("SMTP no configurado.")
        return False
        
    msg = EmailMessage()
    msg['Subject'] = 'Recuperación de Contraseña - HC Prehospitalario'
    msg['From'] = user
    msg['To'] = to_email
    
    msg.set_content(f"Hola,\n\nSe ha solicitado la recuperación de contraseña para tu cuenta.\nTu nueva contraseña temporal es: {temp_password}\n\nPor favor, inicia sesión con esta contraseña y cámbiala inmediatamente.\n\nSaludos,\nEl equipo de HC Prehospitalario.")

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as e:
        print("Error sending email:", e)
        return False
