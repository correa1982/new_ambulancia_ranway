import os
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from utils import login_required, admin_required
from functools import wraps
from datetime import datetime
from dateutil.relativedelta import relativedelta

def ths_trip_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
            
        formularios = session["usuario"].get("formularios_acceso", [])
        if "ths_trip" not in formularios and session["usuario"].get("rol_real") != "admin" and session["usuario"].get("rol") != "admin":
            flash("No tienes permisos para acceder a la Documentación THS Tripulantes.", "error")
            return redirect(url_for("dashboard"))
            
        return f(*args, **kwargs)
    return decorated_function

def register_routes(app):
    @app.route("/admin/ths_trip")
    @login_required
    @ths_trip_required
    def admin_ths_trip():
        conn = get_db()
        records = conn.execute("SELECT * FROM ths_trip_records ORDER BY id DESC").fetchall()
        
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
                        try:
                            v_int = int(vigencia)
                            if unidad == 'meses':
                                expira = fecha_obj + relativedelta(months=v_int)
                            elif unidad == 'años':
                                expira = fecha_obj + relativedelta(years=v_int)
                            else:
                                expira = None
                        except ValueError:
                            expira = None
                        except TypeError:
                            expira = None
                        
                        record[f'{cert}_expira'] = expira.strftime('%Y-%m-%d') if expira else 'N/A'
                        if expira:
                            days_left = (expira - datetime.now().date()).days
                            record[f'{cert}_dias_restantes'] = days_left
                            record[f'{cert}_alerta_15'] = 0 <= days_left <= 15
                            record[f'{cert}_vencido'] = days_left < 0
                            record[f'{cert}_dias_vencido'] = abs(days_left) if days_left < 0 else 0
                        else:
                            record[f'{cert}_vencido'] = False
                            record[f'{cert}_alerta_15'] = False
                else:
                    record[f'{cert}_expira'] = 'N/A'
                    record[f'{cert}_vencido'] = False
                    record[f'{cert}_alerta_15'] = False
            
            # Examen Médico
            examen_fecha = record.get('examen_fecha')
            if examen_fecha:
                if isinstance(examen_fecha, str):
                    try:
                        ef_obj = datetime.strptime(examen_fecha, '%Y-%m-%d').date()
                    except:
                        ef_obj = None
                else:
                    ef_obj = examen_fecha
                
                if ef_obj:
                    expira_examen = ef_obj + relativedelta(years=1)
                    record['examen_expira'] = expira_examen.strftime('%Y-%m-%d')
                    days_left = (expira_examen - datetime.now().date()).days
                    record['examen_dias_restantes'] = days_left
                    record['examen_alerta_15'] = 0 <= days_left <= 15
                    record['examen_vencido'] = days_left < 0
                    record['examen_dias_vencido'] = abs(days_left) if days_left < 0 else 0
                else:
                    record['examen_expira'] = 'N/A'
            else:
                record['examen_expira'] = 'N/A'
                    
        # Check if current user is superadmin (ID 1)
        is_superadmin = False
        user_info = conn.execute("SELECT id FROM usuarios WHERE identificacion = ?", (session["usuario"]["identificacion"],)).fetchone()
        if user_info and user_info["id"] == 1:
            is_superadmin = True
        
        # Get licenses
        licencias = conn.execute("SELECT * FROM ths_licencias_conduccion").fetchall()
        licencias_by_id = {}
        for lic in licencias:
            if lic['identificacion'] not in licencias_by_id:
                licencias_by_id[lic['identificacion']] = []
            
            try:
                if isinstance(lic['fecha_vencimiento'], str):
                    fecha_v = datetime.strptime(lic['fecha_vencimiento'], '%Y-%m-%d').date()
                else:
                    fecha_v = lic['fecha_vencimiento']
                
                if fecha_v:
                    days_left = (fecha_v - datetime.now().date()).days
                    lic['dias_restantes'] = days_left
                    lic['alerta_15'] = 0 <= days_left <= 15
                    lic['vencida'] = days_left < 0
                    lic['dias_vencido'] = abs(days_left) if days_left < 0 else 0
                else:
                    lic['vencida'] = False
                    lic['alerta_15'] = False
            except:
                lic['vencida'] = False
                lic['alerta_15'] = False
            
            licencias_by_id[lic['identificacion']].append(lic)

        # Get vaccines
        vacunas = conn.execute("SELECT * FROM ths_vacunas").fetchall()
        vacunas_by_id = {}
        for vac in vacunas:
            if vac['identificacion'] not in vacunas_by_id:
                vacunas_by_id[vac['identificacion']] = []
            vacunas_by_id[vac['identificacion']].append(vac)

        # Get adicionales
        cert_adic = conn.execute("SELECT * FROM ths_certificados_adicionales").fetchall()
        cert_adic_by_id = {}
        for ca in cert_adic:
            _id = ca['identificacion']
            if _id not in cert_adic_by_id:
                cert_adic_by_id[_id] = []
                
            fecha = ca['fecha_realizacion']
            vigencia = ca['vigencia']
            unidad = ca['unidad_vigencia']
            
            if fecha and vigencia and unidad:
                if isinstance(fecha, str):
                    try:
                        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
                    except:
                        fecha_obj = None
                else:
                    fecha_obj = fecha
                    
                if fecha_obj:
                    try:
                        v_int = int(vigencia)
                        if unidad == 'meses':
                            expira = fecha_obj + relativedelta(months=v_int)
                        elif unidad == 'años':
                            expira = fecha_obj + relativedelta(years=v_int)
                        else:
                            expira = None
                    except:
                        expira = None
                        
                    ca['expira'] = expira.strftime('%Y-%m-%d') if expira else 'N/A'
                    if expira:
                        days_left = (expira - datetime.now().date()).days
                        ca['dias_restantes'] = days_left
                        ca['alerta_15'] = 0 <= days_left <= 15
                        ca['vencido'] = days_left < 0
                        ca['dias_vencido'] = abs(days_left) if days_left < 0 else 0
                    else:
                        ca['vencido'] = False
                        ca['alerta_15'] = False
                else:
                    ca['expira'] = 'N/A'
                    ca['vencido'] = False
                    ca['alerta_15'] = False
            else:
                ca['expira'] = 'N/A'
                ca['vencido'] = False
                ca['alerta_15'] = False

            cert_adic_by_id[_id].append(ca)

        # Get contratos
        contratos = conn.execute("SELECT * FROM ths_contratos ORDER BY fecha_inicio ASC").fetchall()
        contratos_by_id = {}
        for c in contratos:
            if c['identificacion'] not in contratos_by_id:
                contratos_by_id[c['identificacion']] = []
            
            # Check alert 45 days (only for Definido)
            c['alerta_45'] = False
            c['vencido'] = False
            c['dias_restantes'] = 0
            c['dias_vencido'] = 0
            
            if c.get('tipo_contrato') != 'Indefinido':
                try:
                    if isinstance(c['fecha_fin'], str) and c['fecha_fin']:
                        ff = datetime.strptime(c['fecha_fin'], '%Y-%m-%d').date()
                    else:
                        ff = c['fecha_fin']
                    
                    if ff:
                        days_left = (ff - datetime.now().date()).days
                        c['dias_restantes'] = days_left
                        c['alerta_45'] = 0 <= days_left <= 45
                        c['vencido'] = days_left < 0
                        c['dias_vencido'] = abs(days_left) if days_left < 0 else 0
                except:
                    pass
            contratos_by_id[c['identificacion']].append(c)

        for record in records:
            record['licencias'] = licencias_by_id.get(record['identificacion'], [])
            record['vacunas'] = vacunas_by_id.get(record['identificacion'], [])
            record['cert_adicionales'] = cert_adic_by_id.get(record['identificacion'], [])
            
            recs_contratos = contratos_by_id.get(record['identificacion'], [])
            record['contratos'] = recs_contratos
            # Determine global alert from the most recent contract
            record['contrato_alerta'] = False
            record['contrato_vencido'] = False
            if recs_contratos:
                last_c = recs_contratos[-1]
                record['contrato_alerta'] = last_c['alerta_45']
                record['contrato_vencido'] = last_c['vencido']

        activos = [r for r in records if r["activo"] == 1]
        inactivos = [r for r in records if r["activo"] == 0]
                
        conn.close()
        return render_template("ths_trip.html", activos=activos, inactivos=inactivos, is_superadmin=is_superadmin, usuario=session["usuario"])

    @app.route("/admin/ths_trip/agregar", methods=["POST"])
    @login_required
    @ths_trip_required
    def admin_ths_trip_agregar():
        identificacion = request.form.get("identificacion", "").strip()
        nombre_completo = request.form.get("nombre_completo", "").strip()
        perfil = request.form.get("perfil", "")
        
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
        cedula_150 = 1 if request.form.get("cedula_150") else 0
        
        # Certificados adicionales
        cert_bancario = 1 if request.form.get("cert_bancario") else 0
        banco_nombre = request.form.get("banco_nombre", "").strip() if cert_bancario else ""
        banco_cuenta = request.form.get("banco_cuenta", "").strip() if cert_bancario else ""
        
        cert_pension = 1 if request.form.get("cert_pension") else 0
        pension_nombre = request.form.get("pension_nombre", "").strip() if cert_pension else ""
        
        cert_eps = 1 if request.form.get("cert_eps") else 0
        eps_nombre = request.form.get("eps_nombre", "").strip() if cert_eps else ""
        
        # Examen médico
        examen_fecha = request.form.get("examen_fecha") or None
        
        action_type = request.form.get("action_type", "add")
        
        if not identificacion or not nombres or not apellidos:
            flash("Identificación, nombres y apellidos son obligatorios.", "error")
            return redirect(url_for("admin_ths_trip"))
            
        conn = get_db()
        if action_type == "edit":
            conn.execute(
                """UPDATE ths_trip_records SET 
                    nombres = ?, apellidos = ?,
                    perfil = ?,
                    bls_fecha = ?, bls_vigencia = ?, bls_vigencia_unidad = ?,
                    avvs_fecha = ?, avvs_vigencia = ?, avvs_vigencia_unidad = ?,
                    avaq_fecha = ?, avaq_vigencia = ?, avaq_vigencia_unidad = ?,
                    contacto = ?, registro_salud = ?, hoja_vida = ?, rethus = ?, acta_grado = ?, tarjeta_profesional = ?, cedula_150 = ?,
                    cert_bancario = ?, banco_nombre = ?, banco_cuenta = ?, cert_pension = ?, pension_nombre = ?, cert_eps = ?, eps_nombre = ?,
                    examen_fecha = ?
                   WHERE identificacion = ?""",
                (nombres, apellidos, perfil,
                 bls_fecha, bls_vigencia, bls_vigencia_unidad,
                 avvs_fecha, avvs_vigencia, avvs_vigencia_unidad,
                 avaq_fecha, avaq_vigencia, avaq_vigencia_unidad,
                 contacto, registro_salud, hoja_vida, rethus, acta_grado, tarjeta_profesional, cedula_150,
                 cert_bancario, banco_nombre, banco_cuenta, cert_pension, pension_nombre, cert_eps, eps_nombre,
                 examen_fecha,
                 identificacion)
            )
            # Eliminar licencias existentes para actualizar
            conn.execute("DELETE FROM ths_licencias_conduccion WHERE identificacion = ?", (identificacion,))
            # Eliminar vacunas existentes para actualizar
            conn.execute("DELETE FROM ths_vacunas WHERE identificacion = ?", (identificacion,))
            # Eliminar contratos existentes para actualizar
            conn.execute("DELETE FROM ths_contratos WHERE identificacion = ?", (identificacion,))
            # Eliminar certificados adicionales existentes
            conn.execute("DELETE FROM ths_certificados_adicionales WHERE identificacion = ?", (identificacion,))
            flash(f"Registro de {nombres} actualizado exitosamente.", "success")
        else:
            conn.execute(
                """INSERT INTO ths_trip_records (
                    identificacion, nombres, apellidos, perfil,
                    bls_fecha, bls_vigencia, bls_vigencia_unidad,
                    avvs_fecha, avvs_vigencia, avvs_vigencia_unidad,
                    avaq_fecha, avaq_vigencia, avaq_vigencia_unidad,
                    contacto, registro_salud, hoja_vida, rethus, acta_grado, tarjeta_profesional, cedula_150,
                    cert_bancario, banco_nombre, banco_cuenta, cert_pension, pension_nombre, cert_eps, eps_nombre,
                    examen_fecha,
                    registrado_por
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (identificacion, nombres, apellidos, perfil,
                 bls_fecha, bls_vigencia, bls_vigencia_unidad,
                 avvs_fecha, avvs_vigencia, avvs_vigencia_unidad,
                 avaq_fecha, avaq_vigencia, avaq_vigencia_unidad,
                 contacto, registro_salud, hoja_vida, rethus, acta_grado, tarjeta_profesional, cedula_150,
                 cert_bancario, banco_nombre, banco_cuenta, cert_pension, pension_nombre, cert_eps, eps_nombre,
                 examen_fecha,
                 session["usuario"]["nombre"])
            )
            flash(f"Persona {nombres} {apellidos} agregada correctamente.", "success")
            
        # Procesar Licencias de conducción (solo si es CONDUCTOR o CONDUCTOR APH, pero se controla por frontend)
        categorias = request.form.getlist("licencia_categoria[]")
        fechas = request.form.getlist("licencia_fecha_vencimiento[]")
        
        for cat, fec in zip(categorias, fechas):
            if cat.strip() and fec.strip():
                conn.execute(
                    "INSERT INTO ths_licencias_conduccion (identificacion, categoria, fecha_vencimiento) VALUES (?, ?, ?)",
                    (identificacion, cat.strip(), fec.strip())
                )
                
        # Procesar Vacunas
        vacunas_nombres = request.form.getlist("vacuna_nombre[]")
        vacunas_dosis = request.form.getlist("vacuna_dosis[]")
        vacunas_fechas = request.form.getlist("vacuna_fecha[]")
        
        for vn, vd, vf in zip(vacunas_nombres, vacunas_dosis, vacunas_fechas):
            if vn.strip() and vd.strip() and vf.strip():
                conn.execute(
                    "INSERT INTO ths_vacunas (identificacion, vacuna, dosis, fecha_aplicacion) VALUES (?, ?, ?, ?)",
                    (identificacion, vn.strip(), vd.strip(), vf.strip())
                )
                
        # Procesar Contratos
        contratos_tipos = request.form.getlist("contrato_tipo[]")
        contratos_duraciones = request.form.getlist("contrato_duracion[]")
        contratos_inicios = request.form.getlist("contrato_inicio[]")
        contratos_fines = request.form.getlist("contrato_fin[]")
        
        # Ensure we have defaults if lists don't match
        max_len = max(len(contratos_inicios), len(contratos_tipos))
        contratos_tipos = (contratos_tipos + ['Definido'] * max_len)[:max_len]
        contratos_duraciones = (contratos_duraciones + [''] * max_len)[:max_len]
        contratos_fines = (contratos_fines + [''] * max_len)[:max_len]
        
        for ct, cd, ci, cf in zip(contratos_tipos, contratos_duraciones, contratos_inicios, contratos_fines):
            if ci.strip():
                # If indefinido, ignore fin and duracion
                c_fin = cf.strip() if ct != 'Indefinido' else None
                if not c_fin: c_fin = None
                
                c_dur = int(cd.strip()) if cd.strip() and ct != 'Indefinido' else None
                
                conn.execute(
                    "INSERT INTO ths_contratos (identificacion, tipo_contrato, duracion_meses, fecha_inicio, fecha_fin) VALUES (?, ?, ?, ?, ?)",
                    (identificacion, ct, c_dur, ci.strip(), c_fin)
                )

        # Procesar Certificados Adicionales
        cert_adic_nombres = request.form.getlist("cert_adic_nombre[]")
        cert_adic_fechas = request.form.getlist("cert_adic_fecha[]")
        cert_adic_vigencias = request.form.getlist("cert_adic_vigencia[]")
        cert_adic_unidades = request.form.getlist("cert_adic_unidad[]")
        
        for cn, cf, cv, cu in zip(cert_adic_nombres, cert_adic_fechas, cert_adic_vigencias, cert_adic_unidades):
            if cn.strip() and cf.strip() and cv.strip() and cu.strip():
                conn.execute(
                    "INSERT INTO ths_certificados_adicionales (identificacion, nombre_certificado, fecha_realizacion, vigencia, unidad_vigencia) VALUES (?, ?, ?, ?, ?)",
                    (identificacion, cn.strip(), cf.strip(), cv.strip(), cu.strip())
                )
            
        conn.commit()
        conn.close()
        return redirect(url_for("admin_ths_trip"))

    @app.route("/admin/ths_trip/eliminar/<identificacion>", methods=["POST", "GET"])
    @login_required
    @ths_trip_required
    def admin_ths_trip_eliminar(identificacion):
        if identificacion:
            try:
                conn = get_db()
                conn.execute("DELETE FROM ths_trip_records WHERE identificacion = ?", (identificacion,))
                conn.execute("DELETE FROM ths_certificados_adicionales WHERE identificacion = ?", (identificacion,))
                conn.commit()
                conn.close()
                flash("Registro eliminado exitosamente.", "success")
            except Exception as e:
                flash(f"Error al eliminar: {e}", "error")
        
        return redirect(url_for("admin_ths_trip"))

    @app.route("/admin/ths_trip/toggle/<identificacion>", methods=["POST"])
    @login_required
    @ths_trip_required
    def admin_ths_trip_toggle(identificacion):
        conn = get_db()
        record = conn.execute("SELECT activo FROM ths_trip_records WHERE identificacion = ?", (identificacion,)).fetchone()
        if record:
            nuevo_estado = 0 if record["activo"] == 1 else 1
            conn.execute("UPDATE ths_trip_records SET activo = ? WHERE identificacion = ?", (nuevo_estado, identificacion))
            conn.commit()
            flash("Estado del registro actualizado.", "success")
        else:
            flash("Registro no encontrado.", "error")
        conn.close()
        return redirect(url_for("admin_ths_trip"))
