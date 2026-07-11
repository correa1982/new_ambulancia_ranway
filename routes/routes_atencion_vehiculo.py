import json
import os
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from utils import login_required, admin_required, get_user_info, ahora, hoy
# _load_config imported lazily inside functions to avoid circular import

def register_routes(app):
    # --- Formulario Atencion Vehiculo de Intervencion ---
    @app.route("/formularios/atencion_vehiculo", methods=["GET", "POST"])
    @login_required
    def form_atencion_vehiculo():
        if request.method == "POST":
            data = request.form
            accion = request.form.get("accion", "finalizar")
            finalizado = 0 if accion == "borrador" else 1
            conn = get_db()
            firma, perfil, rm = get_user_info(conn, session["usuario"]["identificacion"])
            comandantes_perfil = data.getlist("comandante_perfil[]")
            comandantes_nombre = data.getlist("comandante_nombre[]")
            comandantes_doc = data.getlist("comandante_doc[]")
            comandante_list = []
            for i in range(len(comandantes_perfil)):
                if comandantes_nombre[i].strip():
                    comandante_list.append({
                        "perfil": comandantes_perfil[i],
                        "nombre": comandantes_nombre[i],
                        "identificacion": comandantes_doc[i] if i < len(comandantes_doc) else ""
                    })
            comandante_json = json.dumps(comandante_list) if comandante_list else "[]"
            
            integrantes_perfil = data.getlist("integrante_perfil[]")
            integrantes_nombre = data.getlist("integrante_nombre[]")
            integrantes_doc = data.getlist("integrante_doc[]")
            integrantes_list = []
            for i in range(len(integrantes_perfil)):
                if integrantes_nombre[i].strip():
                    integrantes_list.append({
                        "perfil": integrantes_perfil[i],
                        "nombre": integrantes_nombre[i],
                        "identificacion": integrantes_doc[i] if i < len(integrantes_doc) else ""
                    })
            integrantes_json = json.dumps(integrantes_list) if integrantes_list else "[]"

            try:
                conn.execute("""
                    INSERT INTO atencion_vehiculo (
                        consecutivo, pais, departamento, municipio, barrio, direccion,
                        fecha_hora_despacho, fecha_hora_salida, fecha_hora_llegada,
                        comandante_incidente, integrantes_tripulacion, tipo, subtipo,
                        descripcion, equipos_json, finalizado, fecha_hora_finalizacion, registrado_por,
                        registrado_por_identificacion, perfil_registrador,
                        registro_medico_registrador, firma_registrador, fecha_registro
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("consecutivo"),
                    data.get("pais"),
                    data.get("departamento"),
                    data.get("municipio"),
                    data.get("barrio"),
                    data.get("direccion"),
                    data.get("fecha_hora_despacho"),
                    data.get("fecha_hora_salida"),
                    data.get("fecha_hora_llegada"),
                    comandante_json,
                    integrantes_json,
                    data.get("tipo"),
                    data.get("subtipo"),
                    data.get("descripcion"),
                    data.get("equipos_json") or "[]",
                    finalizado,
                    data.get("fecha_hora_finalizacion"),
                    session["usuario"]["nombre"],
                    session["usuario"]["identificacion"],
                    perfil,
                    rm,
                    firma,
                    ahora().strftime("%Y-%m-%d %H:%M:%S")
                ))
                conn.commit()
                if finalizado == 1:
                    flash("Formulario Atención Vehículo de Intervención finalizado y guardado con éxito.", "success")
                else:
                    flash("Borrador de Atención Vehículo de Intervención guardado con éxito.", "success")
            except Exception as e:
                flash(f"Error al guardar el formulario: {e}", "error")
            finally:
                conn.close()
            return redirect(url_for("registros_atencion_vehiculo"))

        # GET: Render form
        conn = get_db()
        firma, _, _ = get_user_info(conn, session["usuario"]["identificacion"])
        grupos_equipos_db = conn.execute(
            "SELECT nombre FROM checklist_categorias WHERE tipo_checklist = 'equipos' AND activo = 1 ORDER BY nombre"
        ).fetchall()
        grupos_equipos = [row["nombre"] for row in grupos_equipos_db]
        
        # Cargar todos los usuarios para el datalist
        usuarios = conn.execute("SELECT nombre, identificacion, perfil FROM usuarios ORDER BY nombre ASC").fetchall()
        todos_usuarios = [dict(u) for u in usuarios]
        
        conn.close()
        return render_template("atencion_vehiculo.html", usuario=session["usuario"], firma_usuario=firma, item=None, grupos_equipos=grupos_equipos, todos_usuarios=todos_usuarios)

    @app.route("/formularios/atencion_vehiculo/registros")
    @login_required
    def registros_atencion_vehiculo():
        conn = get_db()
        fecha_hoy = hoy().strftime('%Y-%m-%d')
        fecha_filtro = request.args.get("fecha", fecha_hoy)
        
        # Filtro por fecha en fecha_registro
        if fecha_filtro:
            fecha_like = f"{fecha_filtro}%"
            items = conn.execute(
                "SELECT * FROM atencion_vehiculo WHERE fecha_registro LIKE ? ORDER BY id DESC", 
                (fecha_like,)
            ).fetchall()
        else:
            items = conn.execute("SELECT * FROM atencion_vehiculo ORDER BY id DESC").fetchall()
            
        conn.close()
        return render_template(
            "registros_formulario.html", 
            items=items,
            tipo="atencion_vehiculo", 
            titulo="Atención Vehículo de Intervención",
            usuario=session["usuario"], 
            fecha_filtro=fecha_filtro
        )

    @app.route("/formularios/atencion_vehiculo/ver/<int:id>")
    @login_required
    def ver_atencion_vehiculo(id):
        conn = get_db()
        item = conn.execute("SELECT * FROM atencion_vehiculo WHERE id = ?", (id,)).fetchone()
        
        conn.close()
        from app import _load_config
        cfg = _load_config()
        
        if not item:
            flash("Registro no encontrado.", "error")
            return redirect(url_for("registros_atencion_vehiculo"))
            
        try:
            comandante_list = json.loads(item["comandante_incidente"]) if item["comandante_incidente"] else []
        except:
            comandante_list = []
            
        try:
            integrantes_list = json.loads(item["integrantes_tripulacion"]) if item["integrantes_tripulacion"] else []
        except:
            integrantes_list = []
            
        return render_template("ver_atencion_vehiculo.html", item=item, cfg=cfg, comandante_list=comandante_list, integrantes_list=integrantes_list)

    @app.route("/formularios/atencion_vehiculo/editar/<int:id>", methods=["GET", "POST"])
    @login_required
    def editar_atencion_vehiculo(id):
        conn = get_db()
        item = conn.execute("SELECT * FROM atencion_vehiculo WHERE id = ?", (id,)).fetchone()
        if not item:
            conn.close()
            flash("Registro no encontrado.", "error")
            return redirect(url_for("registros_atencion_vehiculo"))
            
        if item["finalizado"] == 1:
            conn.close()
            flash("Este registro ya ha sido finalizado y no puede ser editado.", "error")
            return redirect(url_for("registros_atencion_vehiculo"))
            
        if request.method == "POST":
            data = request.form
            accion = request.form.get("accion", "finalizar")
            finalizado = 0 if accion == "borrador" else 1
            comandantes_perfil = data.getlist("comandante_perfil[]")
            comandantes_nombre = data.getlist("comandante_nombre[]")
            comandantes_doc = data.getlist("comandante_doc[]")
            comandante_list = []
            for i in range(len(comandantes_perfil)):
                if comandantes_nombre[i].strip():
                    comandante_list.append({
                        "perfil": comandantes_perfil[i],
                        "nombre": comandantes_nombre[i],
                        "identificacion": comandantes_doc[i] if i < len(comandantes_doc) else ""
                    })
            comandante_json = json.dumps(comandante_list) if comandante_list else "[]"
            
            integrantes_perfil = data.getlist("integrante_perfil[]")
            integrantes_nombre = data.getlist("integrante_nombre[]")
            integrantes_doc = data.getlist("integrante_doc[]")
            integrantes_list = []
            for i in range(len(integrantes_perfil)):
                if integrantes_nombre[i].strip():
                    integrantes_list.append({
                        "perfil": integrantes_perfil[i],
                        "nombre": integrantes_nombre[i],
                        "identificacion": integrantes_doc[i] if i < len(integrantes_doc) else ""
                    })
            integrantes_json = json.dumps(integrantes_list) if integrantes_list else "[]"

            try:
                conn.execute("""
                    UPDATE atencion_vehiculo SET
                        consecutivo = ?, pais = ?, departamento = ?, municipio = ?, barrio = ?, direccion = ?,
                        fecha_hora_despacho = ?, fecha_hora_salida = ?, fecha_hora_llegada = ?,
                        comandante_incidente = ?, integrantes_tripulacion = ?, tipo = ?, subtipo = ?,
                        descripcion = ?, equipos_json = ?, finalizado = ?, fecha_hora_finalizacion = ?
                    WHERE id = ?
                """, (
                    data.get("consecutivo"),
                    data.get("pais"),
                    data.get("departamento"),
                    data.get("municipio"),
                    data.get("barrio"),
                    data.get("direccion"),
                    data.get("fecha_hora_despacho"),
                    data.get("fecha_hora_salida"),
                    data.get("fecha_hora_llegada"),
                    comandante_json,
                    integrantes_json,
                    data.get("tipo"),
                    data.get("subtipo"),
                    data.get("descripcion"),
                    data.get("equipos_json") or "[]",
                    finalizado,
                    data.get("fecha_hora_finalizacion"),
                    id
                ))
                conn.commit()
                if finalizado == 1:
                    flash("Formulario Atención Vehículo de Intervención finalizado y guardado con éxito.", "success")
                else:
                    flash("Borrador actualizado con éxito.", "success")
            except Exception as e:
                flash(f"Error al actualizar: {e}", "error")
            finally:
                conn.close()
            return redirect(url_for("registros_atencion_vehiculo"))
            
        grupos_equipos_db = conn.execute(
            "SELECT nombre FROM checklist_categorias WHERE tipo_checklist = 'equipos' AND activo = 1 ORDER BY nombre"
        ).fetchall()
        grupos_equipos = [row["nombre"] for row in grupos_equipos_db]
        
        # Cargar todos los usuarios para el datalist
        usuarios = conn.execute("SELECT nombre, identificacion, perfil FROM usuarios ORDER BY nombre ASC").fetchall()
        todos_usuarios = [dict(u) for u in usuarios]
        
        conn.close()
        
        try:
            comandante_list = json.loads(item["comandante_incidente"]) if item["comandante_incidente"] else []
        except:
            comandante_list = []
            
        try:
            integrantes_list = json.loads(item["integrantes_tripulacion"]) if item["integrantes_tripulacion"] else []
        except:
            integrantes_list = []
            
        return render_template("atencion_vehiculo.html", usuario=session["usuario"], item=item, grupos_equipos=grupos_equipos, comandante_list=comandante_list, integrantes_list=integrantes_list, todos_usuarios=todos_usuarios)

    @app.route("/formularios/atencion_vehiculo/eliminar/<int:id>")
    @login_required
    def eliminar_atencion_vehiculo(id):
        conn = get_db()
        item = conn.execute("SELECT * FROM atencion_vehiculo WHERE id = ?", (id,)).fetchone()
        if item and item["finalizado"] == 1:
            conn.close()
            flash("Este registro ya ha sido finalizado y no puede ser eliminado.", "error")
            return redirect(url_for("registros_atencion_vehiculo"))
            
        try:
            conn.execute("DELETE FROM atencion_vehiculo WHERE id = ?", (id,))
            conn.commit()
            flash("Registro eliminado permanentemente.", "success")
        except Exception as e:
            flash(f"Error al eliminar el registro: {e}", "error")
        finally:
            conn.close()
        return redirect(url_for("registros_atencion_vehiculo"))
