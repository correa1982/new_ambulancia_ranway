import os
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from utils import login_required, admin_required
from functools import wraps
from datetime import datetime
from dateutil.relativedelta import relativedelta

def ths_soc_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
            
        formularios = session["usuario"].get("formularios_acceso", [])
        if "ths_soc" not in formularios and session["usuario"].get("rol_real") != "admin" and session["usuario"].get("rol") != "admin":
            flash("No tienes permisos para acceder a la Documentación Salud Socorristas.", "error")
            return redirect(url_for("dashboard"))
            
        return f(*args, **kwargs)
    return decorated_function

def register_routes(app):
    @app.route("/admin/ths_soc")
    @login_required
    @ths_soc_required
    def admin_ths_soc():
        conn = get_db()
        records = conn.execute("SELECT * FROM ths_soc_records ORDER BY id DESC").fetchall()
        
        # Calculate expiration for each record
        for record in records:
            for cert in ['bls', 'avvs', 'avaq']:
                fecha = record[f'{cert}_fecha']
                vigencia = record[f'{cert}_vigencia']
                unidad = record[f'{cert}_vigencia_unidad']
                
                if fecha and vigencia and unidad:
                    if isinstance(fecha, str):
                        try:
                            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
                        except:
                            fecha_obj = None
                    else:
                        fecha_obj = fecha

                    if fecha_obj:
                        if unidad == 'meses':
                            expira = fecha_obj + relativedelta(months=int(vigencia))
                        elif unidad == 'años':
                            expira = fecha_obj + relativedelta(years=int(vigencia))
                        else:
                            expira = None
                        
                        record[f'{cert}_expira'] = expira.strftime('%Y-%m-%d') if expira else 'N/A'
                        if expira:
                            record[f'{cert}_vencido'] = expira < datetime.now().date()
                        else:
                            record[f'{cert}_vencido'] = False
                else:
                    record[f'{cert}_expira'] = 'N/A'
                    record[f'{cert}_vencido'] = False
                    
        # Check if current user is superadmin (ID 1)
        is_superadmin = False
        user_info = conn.execute("SELECT id FROM usuarios WHERE identificacion = ?", (session["usuario"]["identificacion"],)).fetchone()
        if user_info and user_info["id"] == 1:
            is_superadmin = True
            
        activos = []
        inactivos = []
        for record in records:
            if record.get("activo", 1) == 1:
                activos.append(record)
            else:
                inactivos.append(record)
            
        conn.close()
        return render_template("ths_soc.html", activos=activos, inactivos=inactivos, is_superadmin=is_superadmin, usuario=session["usuario"])

    @app.route("/admin/ths_soc/agregar", methods=["POST"])
    @login_required
    @ths_soc_required
    def admin_ths_soc_agregar():
        identificacion = request.form.get("identificacion", "").strip()
        nombre_completo = request.form.get("nombre_completo", "").strip()
        
        parts = nombre_completo.split(" ", 1)
        nombres = parts[0] if len(parts) > 0 else ""
        apellidos = parts[1] if len(parts) > 1 else ""
        
        # BLS
        bls_fecha = request.form.get("bls_fecha") or None
        bls_vigencia = request.form.get("bls_vigencia") or None
        bls_vigencia_unidad = request.form.get("bls_vigencia_unidad") or None
        
        # AVVS
        avvs_fecha = request.form.get("avvs_fecha") or None
        avvs_vigencia = request.form.get("avvs_vigencia") or None
        avvs_vigencia_unidad = request.form.get("avvs_vigencia_unidad") or None
        
        # AVAQ
        avaq_fecha = request.form.get("avaq_fecha") or None
        avaq_vigencia = request.form.get("avaq_vigencia") or None
        avaq_vigencia_unidad = request.form.get("avaq_vigencia_unidad") or None
        
        # Nuevos campos
        contacto = request.form.get("contacto", "").strip()
        registro_salud = request.form.get("registro_salud", "").strip()
        hoja_vida = 1 if request.form.get("hoja_vida") else 0
        rethus = 1 if request.form.get("rethus") else 0
        acta_grado = 1 if request.form.get("acta_grado") else 0
        tarjeta_profesional = 1 if request.form.get("tarjeta_profesional") else 0
        
        action_type = request.form.get("action_type", "add")
        
        if not identificacion or not nombres or not apellidos:
            flash("Identificación, nombres y apellidos son obligatorios.", "error")
            return redirect(url_for("admin_ths_soc"))
            
        conn = get_db()
        if action_type == "edit":
            conn.execute(
                """UPDATE ths_soc_records SET 
                    nombres = ?, apellidos = ?,
                    bls_fecha = ?, bls_vigencia = ?, bls_vigencia_unidad = ?,
                    avvs_fecha = ?, avvs_vigencia = ?, avvs_vigencia_unidad = ?,
                    avaq_fecha = ?, avaq_vigencia = ?, avaq_vigencia_unidad = ?,
                    contacto = ?, registro_salud = ?, hoja_vida = ?, rethus = ?, acta_grado = ?, tarjeta_profesional = ?
                   WHERE identificacion = ?""",
                (nombres, apellidos,
                 bls_fecha, bls_vigencia, bls_vigencia_unidad,
                 avvs_fecha, avvs_vigencia, avvs_vigencia_unidad,
                 avaq_fecha, avaq_vigencia, avaq_vigencia_unidad,
                 contacto, registro_salud, hoja_vida, rethus, acta_grado, tarjeta_profesional,
                 identificacion)
            )
            flash(f"Registro de {nombres} actualizado exitosamente.", "success")
        else:
            conn.execute(
                """INSERT INTO ths_soc_records (
                    identificacion, nombres, apellidos, 
                    bls_fecha, bls_vigencia, bls_vigencia_unidad,
                    avvs_fecha, avvs_vigencia, avvs_vigencia_unidad,
                    avaq_fecha, avaq_vigencia, avaq_vigencia_unidad,
                    contacto, registro_salud, hoja_vida, rethus, acta_grado, tarjeta_profesional,
                    registrado_por
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (identificacion, nombres, apellidos,
                 bls_fecha, bls_vigencia, bls_vigencia_unidad,
                 avvs_fecha, avvs_vigencia, avvs_vigencia_unidad,
                 avaq_fecha, avaq_vigencia, avaq_vigencia_unidad,
                 contacto, registro_salud, hoja_vida, rethus, acta_grado, tarjeta_profesional,
                 session["usuario"]["nombre"])
            )
            flash(f"Persona {nombres} {apellidos} agregada correctamente.", "success")
            
        conn.commit()
        conn.close()
        return redirect(url_for("admin_ths_soc"))

    @app.route("/admin/ths_soc/eliminar/<string:identificacion>", methods=["POST"])
    @login_required
    @ths_soc_required
    def admin_ths_soc_eliminar(identificacion):
        if identificacion:
            try:
                conn = get_db()
                conn.execute("DELETE FROM ths_soc_records WHERE identificacion = ?", (identificacion,))
                conn.commit()
                conn.close()
                flash("Registro eliminado exitosamente.", "success")
            except Exception as e:
                flash(f"Error al eliminar: {e}", "error")
        
        return redirect(url_for("admin_ths_soc"))

    @app.route("/admin/ths_soc/toggle/<string:identificacion>", methods=["POST"])
    @login_required
    @ths_soc_required
    def admin_ths_soc_toggle(identificacion):
        conn = get_db()
        record = conn.execute("SELECT activo FROM ths_soc_records WHERE identificacion = ?", (identificacion,)).fetchone()
        if record:
            nuevo_estado = 0 if record["activo"] == 1 else 1
            conn.execute("UPDATE ths_soc_records SET activo = ? WHERE identificacion = ?", (nuevo_estado, identificacion))
            conn.commit()
            flash("Estado del registro actualizado.", "success")
        else:
            flash("Registro no encontrado.", "error")
        conn.close()
        return redirect(url_for("admin_ths_soc"))
