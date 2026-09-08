import os
from flask import render_template, request, redirect, url_for, session, flash
from db import get_db
from utils import login_required, ahora, hoy, get_user_info

def register_routes(app):
    @app.route("/formularios/voluntariado/nuevo", methods=["GET", "POST"])
    @login_required
    def form_voluntariado():
        if request.method == "POST":
            data = request.form
            
            fecha = data.get("fecha")
            hora_inicio = data.get("hora_inicio")
            hora_fin = data.get("hora_fin")
            disponibilidad = data.get("disponibilidad")
            disponibilidad_otro = data.get("disponibilidad_otro", "") if disponibilidad == "OTRO" else ""
            total_horas = data.get("total_horas", "0")
            actividad_realizada = data.get("actividad_realizada")
            observaciones = data.get("observaciones")
            
            conn = get_db()
            firma, perfil, _ = get_user_info(conn, session["usuario"]["identificacion"])
            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
            
            registrado_por = session["usuario"]["nombre"]
            registrado_por_identificacion = session["usuario"]["identificacion"]
            
            conn.execute("""
                INSERT INTO registro_voluntariado (
                    fecha, hora_inicio, hora_fin, disponibilidad, disponibilidad_otro, 
                    total_horas, actividad_realizada, observaciones, registrado_por, 
                    registrado_por_identificacion, perfil_registrador, firma_registrador, fecha_registro
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fecha, hora_inicio, hora_fin, disponibilidad, disponibilidad_otro,
                total_horas, actividad_realizada, observaciones,
                registrado_por, registrado_por_identificacion, perfil, firma, now_str
            ))
            
            conn.commit()
            conn.close()
            
            flash("Registro de voluntariado guardado exitosamente.", "success")
            return redirect(url_for("registros_voluntariado"))
            
        return render_template("form_voluntariado.html", usuario=session["usuario"], hoy=hoy().isoformat())

    @app.route("/formularios/voluntariado/registros")
    @login_required
    def registros_voluntariado():
        conn = get_db()
        identificacion = session["usuario"]["identificacion"]
        formularios_acceso = session["usuario"].get("formularios_acceso", {})
        
        # Check permissions: if admin or has 'voluntariado_admin'
        es_admin_vol = session["usuario"].get("rol") == "admin"
        if not es_admin_vol:
            # Check all profiles of the user for 'voluntariado_admin'
            if isinstance(formularios_acceso, dict):
                for perfiles_acc in formularios_acceso.values():
                    if 'voluntariado_admin' in perfiles_acc:
                        es_admin_vol = True
                        break
            elif isinstance(formularios_acceso, list):
                if 'voluntariado_admin' in formularios_acceso:
                        es_admin_vol = True

        if es_admin_vol:
            registros = conn.execute("SELECT * FROM registro_voluntariado ORDER BY id DESC").fetchall()
        else:
            registros = conn.execute("SELECT * FROM registro_voluntariado WHERE registrado_por_identificacion = ? ORDER BY id DESC", (identificacion,)).fetchall()
            
        conn.close()
        return render_template("registros_voluntariado.html", registros=registros, es_admin_vol=es_admin_vol)

    @app.route("/formularios/voluntariado/avalar/<int:record_id>", methods=["POST"])
    @login_required
    def avalar_voluntariado(record_id):
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
            flash("No tienes permiso para avalar registros.", "error")
            return redirect(url_for("registros_voluntariado"))

        conn = get_db()
        firma, perfil, _ = get_user_info(conn, session["usuario"]["identificacion"])
        now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
        
        avalado_por = session["usuario"]["nombre"]
        avalado_por_identificacion = session["usuario"]["identificacion"]
        
        conn.execute("""
            UPDATE registro_voluntariado 
            SET estado = 'Avalado', avalado_por = ?, avalado_por_identificacion = ?, firma_avalador = ?, fecha_aval = ?
            WHERE id = ?
        """, (avalado_por, avalado_por_identificacion, firma, now_str, record_id))
        
        conn.commit()
        conn.close()
        
        flash("Registro avalado exitosamente.", "success")
        return redirect(url_for("registros_voluntariado"))

    @app.route("/formularios/voluntariado/imprimir/<int:record_id>")
    @login_required
    def imprimir_voluntariado(record_id):
        conn = get_db()
        registro = conn.execute("SELECT * FROM registro_voluntariado WHERE id = ?", (record_id,)).fetchone()
        
        if not registro:
            conn.close()
            flash("Registro no encontrado", "error")
            return redirect(url_for("registros_voluntariado"))
            
        identificacion = session["usuario"]["identificacion"]
        es_admin_vol = session["usuario"].get("rol") == "admin"
        
        if not es_admin_vol:
            formularios_acceso = session["usuario"].get("formularios_acceso", {})
            if isinstance(formularios_acceso, dict):
                for perfiles_acc in formularios_acceso.values():
                    if 'voluntariado_admin' in perfiles_acc:
                        es_admin_vol = True
                        break
            elif isinstance(formularios_acceso, list):
                if 'voluntariado_admin' in formularios_acceso:
                    es_admin_vol = True

        if not es_admin_vol and registro["registrado_por_identificacion"] != identificacion:
            conn.close()
            flash("No tienes permiso para ver este registro", "error")
            return redirect(url_for("registros_voluntariado"))
            
        from app import _load_config
        cfg_inst = _load_config()
        conn.close()
        
        return render_template("imprimir_voluntariado.html", registro=registro, cfg=cfg_inst)

    @app.route("/formularios/voluntariado/estadisticas")
    @login_required
    def estadisticas_voluntariado():
        conn = get_db()
        es_admin_vol = session["usuario"].get("rol") == "admin"
        if not es_admin_vol:
            formularios_acceso = session["usuario"].get("formularios_acceso", {})
            if isinstance(formularios_acceso, dict):
                for perfiles_acc in formularios_acceso.values():
                    if 'voluntariado_admin' in perfiles_acc:
                        es_admin_vol = True
                        break
            elif isinstance(formularios_acceso, list):
                if 'voluntariado_admin' in formularios_acceso:
                    es_admin_vol = True

        if not es_admin_vol:
            conn.close()
            flash("No tienes permisos de administrador de voluntariado.", "error")
            return redirect(url_for("dashboard"))
            
        registros = conn.execute("SELECT fecha, total_horas, registrado_por FROM registro_voluntariado WHERE estado = 'Avalado'").fetchall()
        conn.close()
        
        return render_template("estadisticas_voluntariado.html", registros=registros)
