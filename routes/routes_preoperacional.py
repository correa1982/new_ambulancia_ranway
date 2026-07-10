import json
import os
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from utils import login_required, admin_required, calcular_edad, get_user_info, ahora, hoy
# _load_config imported lazily inside functions to avoid circular import
from itsdangerous import URLSafeSerializer, BadSignature
def register_routes(app):
    @app.route("/preoperacional", methods=["GET", "POST"])
    @login_required
    def form_preoperacional():
        if request.method == "POST":
            data = request.form
            conn = get_db()
            firma, perfil, rm = get_user_info(conn, session["usuario"]["identificacion"])
            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
            
            # Check if draft or final
            accion = data.get("accion", "finalizar")
            finalizado = 0 if accion == "borrador" else 1
            
            obs_general = data.get("observaciones", "").strip()
            
            # Dynamic: collect all checklist_item responses into JSON
            items_db = conn.execute(
                "SELECT * FROM checklist_items WHERE tipo_checklist = 'preoperacional' AND activo = 1 ORDER BY categoria, id"
            ).fetchall()
            
            datos = {}
            obs_list = []
            if obs_general:
                obs_list.append(obs_general)
                
            has_item_obs = False
            
            for item in items_db:
                ident = item["identificador"]
                val = data.get(ident, "")
                obs_val = data.get(f"obs_{ident}", "").strip()
                
                datos[ident] = {
                    "nombre": item["nombre"],
                    "categoria": item["categoria"],
                    "valor": val,
                    "observacion": obs_val
                }
                
                if val == "NO" and obs_val:
                    if not has_item_obs:
                        obs_list.append("\n--- NOVEDADES ESPECÍFICAS ---")
                        has_item_obs = True
                    obs_list.append(f"• {item['nombre']}: {obs_val}")
                    
            observaciones_final = "\n".join(obs_list).strip()
            datos_json_str = json.dumps(datos, ensure_ascii=False)

            import uuid
            from werkzeug.utils import secure_filename
            
            files = request.files.getlist("evidencia")
            evidencia_filenames = []
            upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'evidencias')
            os.makedirs(upload_folder, exist_ok=True)
            
            for file in files:
                if file and file.filename != '':
                    filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    file_path = os.path.join(upload_folder, unique_filename)
                    file.save(file_path)
                    evidencia_filenames.append(unique_filename)
            
            # Merge with existing evidence if editing draft
            existing_ev = request.form.get("existing_evidencia", "")
            if existing_ev:
                try:
                    parsed_existing = json.loads(existing_ev)
                    if isinstance(parsed_existing, list):
                        evidencia_filenames = parsed_existing + evidencia_filenames
                except Exception:
                    if existing_ev not in evidencia_filenames:
                        evidencia_filenames.insert(0, existing_ev)
                        
            evidencia_json = json.dumps(evidencia_filenames) if evidencia_filenames else ""

            # Query vehicle snapshot details
            placa = data.get("placa_vehiculo", "").strip()
            tipo_vehiculo = None
            tipo_ambulancia = None
            movil = None
            marca = None
            serie = None
            modelo = None
            soat_vigencia = None
            rtm_vigencia = None
            if placa:
                veh = conn.execute("SELECT * FROM vehiculos WHERE placa = ?", (placa,)).fetchone()
                if veh:
                    tipo_vehiculo = veh["tipo"]
                    tipo_ambulancia = veh["tipo_ambulancia"]
                    movil = veh["movil"]
                    marca = veh["marca"]
                    serie = veh["serie"]
                    modelo = veh["modelo"]
                    
                    # Format date values to string safely
                    def fmt_date(d):
                        if not d: return None
                        if isinstance(d, str): return d.split()[0]
                        return d.strftime("%Y-%m-%d")
                    soat_vigencia = fmt_date(veh["soat_vigencia"])
                    rtm_vigencia = fmt_date(veh["rtm_vigencia"])

            # Check if updating an existing record
            record_id = data.get("id") or request.args.get("id")
            if record_id:
                try:
                    record_id = int(record_id)
                    conn.execute("""
                        UPDATE preoperacional SET
                            fecha = ?, hora = ?, placa_vehiculo = ?,
                            tipo_vehiculo = ?, tipo_ambulancia = ?, movil = ?,
                            marca = ?, serie = ?, modelo = ?,
                            soat_vigencia = ?, rtm_vigencia = ?,
                            nombre_conductor = ?, kilometraje = ?, proximo_aceite = ?,
                            observaciones = ?, registrado_por = ?, registrado_por_identificacion = ?,
                            perfil_registrador = ?, firma_registrador = ?, fecha_registro = ?,
                            datos_json = ?, evidencia = ?, finalizado = ?
                        WHERE id = ?
                    """, (
                        data.get("fecha"), data.get("hora"), placa,
                        tipo_vehiculo, tipo_ambulancia, movil,
                        marca, serie, modelo,
                        soat_vigencia, rtm_vigencia,
                        data.get("nombre_conductor"), data.get("kilometraje"), data.get("proximo_aceite"),
                        observaciones_final,
                        session["usuario"]["nombre"], session["usuario"]["identificacion"],
                        perfil, firma, now_str,
                        datos_json_str, evidencia_json, finalizado,
                        record_id
                    ))
                except ValueError:
                    record_id = None
            if not record_id:
                cursor = conn.execute("""
                    INSERT INTO preoperacional (
                        fecha, hora, placa_vehiculo,
                        tipo_vehiculo, tipo_ambulancia, movil,
                        marca, serie, modelo,
                        soat_vigencia, rtm_vigencia,
                        nombre_conductor, kilometraje, proximo_aceite,
                        observaciones,
                        registrado_por, registrado_por_identificacion,
                        perfil_registrador, firma_registrador, fecha_registro,
                        datos_json, evidencia, finalizado
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data.get("fecha"), data.get("hora"), placa,
                    tipo_vehiculo, tipo_ambulancia, movil,
                    marca, serie, modelo,
                    soat_vigencia, rtm_vigencia,
                    data.get("nombre_conductor"), data.get("kilometraje"), data.get("proximo_aceite"),
                    observaciones_final,
                    session["usuario"]["nombre"], session["usuario"]["identificacion"],
                    perfil, firma, now_str,
                    datos_json_str, evidencia_json, finalizado
                ))
                record_id = cursor.lastrowid
                
            conn.commit()
            conn.close()
            
            if finalizado == 1:
                flash("Preoperacional de conductor finalizado y guardado correctamente.", "success")
                return redirect(url_for("registros_preoperacional"))
            else:
                flash("Borrador de preoperacional guardado correctamente.", "success")
                return redirect(url_for("form_preoperacional", id=record_id))
            
        conn = get_db()
        
        # Load draft preoperacional if id is passed in URL query parameter
        record_id = request.args.get("id")
        record = None
        datos = {}
        if record_id:
            try:
                record_id = int(record_id)
                record_row = conn.execute("SELECT * FROM preoperacional WHERE id = ?", (record_id,)).fetchone()
                if record_row:
                    record_dict = dict(record_row)
                    if session["usuario"]["rol"] == "admin" or record_dict["registrado_por_identificacion"] == session["usuario"]["identificacion"]:
                        if record_dict.get("finalizado") == 0:
                            record = record_dict
                            if record.get("datos_json"):
                                try:
                                    datos = json.loads(record["datos_json"])
                                except Exception:
                                    pass
                            
                            # Parse evidence list
                            ev_list = []
                            if record.get("evidencia"):
                                try:
                                    parsed_ev = json.loads(record["evidencia"])
                                    if isinstance(parsed_ev, list):
                                        ev_list = parsed_ev
                                    else:
                                        ev_list = [record["evidencia"]]
                                except Exception:
                                    ev_list = [record["evidencia"]]
                            record["evidencia_list"] = ev_list
                        else:
                            flash("Este preoperacional ya fue finalizado y no se puede editar.", "error")
                    else:
                        flash("Acceso denegado. No puede editar registros de otros usuarios.", "error")
            except ValueError:
                pass
                
        usuarios = conn.execute(
            "SELECT nombre FROM usuarios WHERE activo = 1 AND (fecha_validez IS NULL OR fecha_validez >= CURDATE()) AND perfil LIKE '%\"Conductor\"%' ORDER BY nombre"
        ).fetchall()
        
        # Fetch active items and group by category
        items_db = conn.execute(
            "SELECT * FROM checklist_items WHERE tipo_checklist = 'preoperacional' AND activo = 1 ORDER BY categoria, id"
        ).fetchall()
        items_por_cat = {}
        for item in items_db:
            cat = item["categoria"]
            if cat not in items_por_cat:
                items_por_cat[cat] = []
            items_por_cat[cat].append(item)
            
        vehiculos = conn.execute(
            "SELECT * FROM vehiculos WHERE activo = 1 ORDER BY tipo, placa"
        ).fetchall()
            
        conn.close()
        return render_template("preoperacional.html", usuario=session["usuario"],
                               hoy=hoy().isoformat(),
                               hora_actual=ahora().strftime("%H:%M"),
                               usuarios=usuarios,
                               items_por_cat=items_por_cat,
                               vehiculos=vehiculos,
                               record=record,
                               datos=datos)


    @app.route("/formularios/preoperacional/registros")
    @login_required
    def registros_preoperacional():
        conn = get_db()
        from datetime import date
        fecha_hoy = hoy().strftime('%Y-%m-%d')
        fecha_filtro = request.args.get("fecha", fecha_hoy)
        fecha_like = f"{fecha_filtro}%"
        
        items = conn.execute("SELECT * FROM preoperacional WHERE fecha_registro LIKE ? ORDER BY id DESC", (fecha_like,)).fetchall()
        conn.close()
        return render_template("registros_formulario.html", items=items,
                               tipo="preoperacional", titulo="Preoperacional Conductores",
                               usuario=session["usuario"], fecha_filtro=fecha_filtro)


    @app.route("/formularios/preoperacional/ver/<int:record_id>")
    @login_required
    def ver_preoperacional(record_id):
        conn = get_db()
        record = conn.execute("SELECT * FROM preoperacional WHERE id = ?", (record_id,)).fetchone()
        if not record:
            conn.close()
            flash("Registro preoperacional no encontrado.", "error")
            return redirect(url_for("registros_preoperacional"))
            
        record_dict = dict(record)
        
        evidencia_list = []
        if record_dict.get("evidencia"):
            try:
                parsed_ev = json.loads(record_dict["evidencia"])
                if isinstance(parsed_ev, list):
                    evidencia_list = parsed_ev
                else:
                    evidencia_list = [record_dict["evidencia"]]
            except Exception:
                evidencia_list = [record_dict["evidencia"]]
        record_dict["evidencia_list"] = evidencia_list

        datos = {}
        if record_dict.get("datos_json"):
            try:
                datos = json.loads(record_dict["datos_json"])
            except Exception:
                pass
                
        # Group data by category for rendering
        items_por_cat = {}
        for ident, info in datos.items():
            cat = info.get("categoria", "Otros")
            if cat not in items_por_cat:
                items_por_cat[cat] = []
            items_por_cat[cat].append({
                "identificador": ident,
                "nombre": info.get("nombre", ident),
                "valor": info.get("valor", ""),
                "observacion": info.get("observacion", "")
            })

        # Fallback for older records that don't have vehicle snapshots saved in the table
        if not record_dict.get("tipo_vehiculo") and record_dict.get("placa_vehiculo"):
            veh = conn.execute("SELECT * FROM vehiculos WHERE placa = ?", (record_dict["placa_vehiculo"],)).fetchone()
            if veh:
                record_dict["tipo_vehiculo"] = veh["tipo"]
                record_dict["tipo_ambulancia"] = veh["tipo_ambulancia"]
                record_dict["movil"] = veh["movil"]
                record_dict["marca"] = veh["marca"]
                record_dict["serie"] = veh["serie"]
                record_dict["modelo"] = veh["modelo"]
                
                # Format dates to string
                def fmt_date(d):
                    if not d: return "—"
                    if isinstance(d, str): return d.split()[0]
                    return d.strftime("%Y-%m-%d")
                record_dict["soat_vigencia"] = fmt_date(veh["soat_vigencia"])
                record_dict["rtm_vigencia"] = fmt_date(veh["rtm_vigencia"])

        from app import _load_config
        cfg = _load_config()

        conn.close()
        return render_template("ver_preoperacional.html", record=record_dict,
                               datos=datos, items_por_cat=items_por_cat,
                               cfg=cfg, usuario=session["usuario"])



