from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from db import get_db
from utils import login_required, get_user_info, get_configuracion, ahora
import json

def register_routes(app):
    @app.route("/formularios/reporte_actividades/nuevo", methods=["GET", "POST"])
    @login_required
    def form_reporte_actividades():
        formularios_acceso = session["usuario"].get("formularios_acceso", {})
        tiene_permiso = session["usuario"].get("rol") == "admin"
        es_admin_vol = session["usuario"].get("rol") == "admin"
        
        if not tiene_permiso:
            if isinstance(formularios_acceso, dict):
                for perfiles_acc in formularios_acceso.values():
                    if 'reporte_actividades' in perfiles_acc:
                        tiene_permiso = True
                    if 'voluntariado_admin' in perfiles_acc:
                        es_admin_vol = True
            elif isinstance(formularios_acceso, list):
                if 'reporte_actividades' in formularios_acceso:
                    tiene_permiso = True
                if 'voluntariado_admin' in formularios_acceso:
                    es_admin_vol = True
                    
        if not tiene_permiso and not es_admin_vol:
            flash("No tienes acceso al formulario de Reporte de Actividades.", "error")
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            nombre_evento = request.form.get("nombre_evento")
            fecha_evento = request.form.get("fecha_evento")
            lugar_evento = request.form.get("lugar_evento")
            hora_inicio = request.form.get("hora_inicio")
            hora_fin = request.form.get("hora_fin")
            tipo_servicio = request.form.get("tipo_servicio")
            
            ambulancia_tab = request.form.get("ambulancia_tab") or "0"
            ambulancia_tam = request.form.get("ambulancia_tam") or "0"
            pasm = request.form.get("pasm") or "0"
            pasb = request.form.get("pasb") or "0"
            equipos_intervencion = request.form.get("equipos_intervencion") or "0"
            moto_aph = request.form.get("moto_aph") or "0"
            unidad_rescate = request.form.get("unidad_rescate") or "0"
            unidad_logistica = request.form.get("unidad_logistica") or "0"
            
            total_personal = request.form.get("total_personal")
            pacientes_atendidos = request.form.get("pacientes_atendidos")
            pacientes_trasladados = request.form.get("pacientes_trasladados")
            observaciones = request.form.get("observaciones")
            
            conn = get_db()
            identificacion = session["usuario"]["identificacion"]
            firma, perfil, _ = get_user_info(conn, identificacion)
            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
            registrado_por = session["usuario"]["nombre"]
            
            conn.execute("""
                INSERT INTO reporte_actividades (
                    nombre_evento, fecha_evento, lugar_evento, hora_inicio, hora_fin, tipo_servicio,
                    ambulancia_tab, ambulancia_tam, pasm, pasb, equipos_intervencion, moto_aph, unidad_rescate, unidad_logistica,
                    total_personal, pacientes_atendidos, pacientes_trasladados, observaciones,
                    registrado_por, registrado_por_identificacion, perfil_registrador, firma_registrador, fecha_registro
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                nombre_evento, fecha_evento, lugar_evento, hora_inicio, hora_fin, tipo_servicio,
                ambulancia_tab, ambulancia_tam, pasm, pasb, equipos_intervencion, moto_aph, unidad_rescate, unidad_logistica,
                total_personal, pacientes_atendidos, pacientes_trasladados, observaciones,
                registrado_por, identificacion, perfil, firma, now_str
            ))
            
            conn.commit()
            conn.close()
            
            flash("Reporte de actividades registrado exitosamente.", "success")
            return redirect(url_for("dashboard"))
            
        return render_template("form_reporte_actividades.html", es_admin_vol=es_admin_vol)

    @app.route("/formularios/reporte_actividades/registros")
    @login_required
    def registros_reporte_actividades():
        formularios_acceso = session["usuario"].get("formularios_acceso", {})
        es_admin_vol = session["usuario"].get("rol") == "admin"
        
        if not es_admin_vol:
            if isinstance(formularios_acceso, dict):
                for perfiles_acc in formularios_acceso.values():
                    if 'voluntariado_admin' in perfiles_acc:
                        es_admin_vol = True
                        break
            elif isinstance(formularios_acceso, list):
                if 'voluntariado_admin' in formularios_acceso:
                    es_admin_vol = True

        if not es_admin_vol:
            flash("Acceso denegado. Solo el Admin Voluntariado puede ver estos registros.", "error")
            return redirect(url_for("dashboard"))

        conn = get_db()
        registros = conn.execute("SELECT * FROM reporte_actividades WHERE estado IN ('Pendiente', 'Avalado') ORDER BY id DESC").fetchall()
        conn.close()
        
        return render_template("registros_reporte_actividades.html", registros=registros)
        
    @app.route("/formularios/reporte_actividades/inactivos")
    @login_required
    def inactivos_reporte_actividades():
        formularios_acceso = session["usuario"].get("formularios_acceso", {})
        es_admin_vol = session["usuario"].get("rol") == "admin"
        
        if not es_admin_vol:
            if isinstance(formularios_acceso, dict):
                for perfiles_acc in formularios_acceso.values():
                    if 'voluntariado_admin' in perfiles_acc:
                        es_admin_vol = True
                        break
            elif isinstance(formularios_acceso, list):
                if 'voluntariado_admin' in formularios_acceso:
                    es_admin_vol = True

        if not es_admin_vol:
            flash("Acceso denegado.", "error")
            return redirect(url_for("dashboard"))

        conn = get_db()
        registros = conn.execute("SELECT * FROM reporte_actividades WHERE estado = 'Inactivo' ORDER BY id DESC").fetchall()
        conn.close()
        
        return render_template("inactivos_reporte_actividades.html", registros=registros)

    @app.route("/formularios/reporte_actividades/avalar/<int:record_id>", methods=["POST"])
    @login_required
    def avalar_reporte(record_id):
        es_admin_vol = session["usuario"].get("rol") == "admin"
        formularios_acceso = session["usuario"].get("formularios_acceso", {})
        if not es_admin_vol:
            if isinstance(formularios_acceso, dict):
                for perfiles_acc in formularios_acceso.values():
                    if 'voluntariado_admin' in perfiles_acc:
                        es_admin_vol = True
                        break
            elif isinstance(formularios_acceso, list):
                if 'voluntariado_admin' in formularios_acceso:
                    es_admin_vol = True

        if not es_admin_vol:
            flash("No tienes permiso.", "error")
            return redirect(url_for("dashboard"))

        conn = get_db()
        firma, _, _ = get_user_info(conn, session["usuario"]["identificacion"])
        now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
        
        avalado_por = session["usuario"]["nombre"]
        avalado_por_identificacion = session["usuario"]["identificacion"]
        
        conn.execute("""
            UPDATE reporte_actividades 
            SET estado = 'Avalado', avalado_por = ?, avalado_por_identificacion = ?, firma_avalador = ?, fecha_aval = ?
            WHERE id = ?
        """, (avalado_por, avalado_por_identificacion, firma, now_str, record_id))
        
        conn.commit()
        conn.close()
        
        flash("Reporte avalado exitosamente.", "success")
        return redirect(url_for("registros_reporte_actividades"))
        
    @app.route("/formularios/reporte_actividades/inactivar/<int:record_id>", methods=["POST"])
    @login_required
    def inactivar_reporte(record_id):
        es_admin_vol = session["usuario"].get("rol") == "admin"
        formularios_acceso = session["usuario"].get("formularios_acceso", {})
        if not es_admin_vol:
            if isinstance(formularios_acceso, dict):
                for perfiles_acc in formularios_acceso.values():
                    if 'voluntariado_admin' in perfiles_acc:
                        es_admin_vol = True
                        break
            elif isinstance(formularios_acceso, list):
                if 'voluntariado_admin' in formularios_acceso:
                    es_admin_vol = True

        if not es_admin_vol:
            flash("No tienes permiso.", "error")
            return redirect(url_for("dashboard"))

        conn = get_db()
        conn.execute("UPDATE reporte_actividades SET estado = 'Inactivo' WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        
        flash("Reporte inactivado.", "info")
        return redirect(url_for("registros_reporte_actividades"))

    @app.route("/formularios/reporte_actividades/imprimir/<int:record_id>")
    @login_required
    def imprimir_reporte(record_id):
        conn = get_db()
        registro = conn.execute("SELECT * FROM reporte_actividades WHERE id = ?", (record_id,)).fetchone()
        
        if not registro:
            conn.close()
            flash("Registro no encontrado.", "error")
            return redirect(url_for("dashboard"))
            
        cfg = get_configuracion(conn)
        conn.close()
        
        return render_template("imprimir_reporte_actividades.html", registro=registro, cfg=cfg)

    @app.route("/formularios/reporte_actividades/estadisticas")
    @login_required
    def estadisticas_reporte():
        es_admin_vol = session["usuario"].get("rol") == "admin"
        formularios_acceso = session["usuario"].get("formularios_acceso", {})
        
        if not es_admin_vol:
            if isinstance(formularios_acceso, dict):
                for perfiles_acc in formularios_acceso.values():
                    if 'voluntariado_admin' in perfiles_acc:
                        es_admin_vol = True
                        break
            elif isinstance(formularios_acceso, list):
                if 'voluntariado_admin' in formularios_acceso:
                    es_admin_vol = True

        if not es_admin_vol:
            flash("No tienes permisos.", "error")
            return redirect(url_for("dashboard"))

        conn = get_db()
        # Solo contabilizar Avalados
        registros = conn.execute("SELECT * FROM reporte_actividades WHERE estado = 'Avalado'").fetchall()
        conn.close()
        
        # Calcular estadísticas por tipo de servicio
        stats_servicios = {}
        for r in registros:
            tipo = r.get("tipo_servicio")
            if not tipo:
                continue
            if tipo not in stats_servicios:
                stats_servicios[tipo] = {"cantidad": 0, "horas": 0.0}
            stats_servicios[tipo]["cantidad"] += 1
            
            # Calcular horas
            try:
                if r.get("hora_inicio") and r.get("hora_fin"):
                    from datetime import datetime
                    h_in = datetime.strptime(r["hora_inicio"], "%H:%M")
                    h_fin = datetime.strptime(r["hora_fin"], "%H:%M")
                    if h_fin < h_in:
                        # Cruza la medianoche
                        diff = (h_fin.hour + 24 - h_in.hour) + (h_fin.minute - h_in.minute)/60.0
                    else:
                        diff = (h_fin - h_in).total_seconds() / 3600.0
                    stats_servicios[tipo]["horas"] += diff
            except Exception:
                pass
        
        for k in stats_servicios:
            stats_servicios[k]["horas"] = round(stats_servicios[k]["horas"], 2)
        
        return render_template("estadisticas_reporte_actividades.html", registros=registros, stats_servicios=stats_servicios)
