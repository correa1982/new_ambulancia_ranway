import json
import os
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from utils import login_required, admin_required, calcular_edad, get_user_info, ahora, hoy
from itsdangerous import URLSafeSerializer, BadSignature

def register_routes(app):
    @app.route("/admin/vehiculos")
    @admin_required
    def admin_vehiculos():
        conn = get_db()
        vehiculos = conn.execute("SELECT * FROM vehiculos ORDER BY tipo, placa").fetchall()
        conn.close()
        return render_template("admin_vehiculos.html", vehiculos=vehiculos, usuario=session["usuario"])

    @app.route("/admin/mapa")
    @login_required
    @admin_required
    def admin_mapa():
        return render_template("mapa.html", usuario=session.get("usuario"))

    @app.route("/admin/vehiculos/agregar", methods=["POST"])
    @login_required
    @admin_required
    def admin_vehiculo_agregar():
        tipo = request.form.get("tipo", "").strip()
        placa = request.form.get("placa", "").strip().upper()
        marca = request.form.get("marca", "").strip()
        serie = request.form.get("serie", "").strip()
        modelo = request.form.get("modelo", "").strip()
        tipo_ambulancia = request.form.get("tipo_ambulancia", "").strip() if tipo == "Ambulancia" else None
        movil = request.form.get("movil", "").strip() if tipo == "Ambulancia" else None
        soat_vigencia = request.form.get("soat_vigencia", "").strip() or None
        rtm_vigencia = request.form.get("rtm_vigencia", "").strip() or None
        
        if not tipo or not placa or not marca or not serie or not modelo:
            flash("El tipo, placa, marca, serie y modelo son obligatorios.", "error")
            return redirect(url_for("admin_checklists", tipo="vehiculos"))
            
        if tipo == "Ambulancia":
            if tipo_ambulancia not in ("TAB", "TAM"):
                flash("El tipo de ambulancia debe ser TAB o TAM.", "error")
                return redirect(url_for("admin_checklists", tipo="vehiculos"))
            if movil not in ("MOVIL 1", "MOVIL 2", "MOVIL 3", "MOVIL 4", "MOVIL 5", "MOVIL 6"):
                flash("El móvil seleccionado no es válido.", "error")
                return redirect(url_for("admin_checklists", tipo="vehiculos"))
            
        conn = get_db()
        existing = conn.execute("SELECT id FROM vehiculos WHERE placa = ?", (placa,)).fetchone()
        if existing:
            flash(f"El vehículo con placa {placa} ya existe.", "error")
        else:
            conn.execute(
                "INSERT INTO vehiculos (tipo, placa, marca, serie, modelo, tipo_ambulancia, movil, soat_vigencia, rtm_vigencia, activo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (tipo, placa, marca, serie, modelo, tipo_ambulancia, movil, soat_vigencia, rtm_vigencia)
            )
            conn.commit()
            flash(f"Vehículo {placa} ({tipo}) agregado con éxito.", "success")
        conn.close()
        return redirect(url_for("admin_checklists", tipo="vehiculos"))

    @app.route("/admin/vehiculos/toggle/<int:vehiculo_id>")
    @login_required
    @admin_required
    def admin_vehiculo_toggle(vehiculo_id):
        conn = get_db()
        vehiculo = conn.execute("SELECT * FROM vehiculos WHERE id = ?", (vehiculo_id,)).fetchone()
        if vehiculo:
            nuevo_estado = 0 if vehiculo["activo"] else 1
            conn.execute("UPDATE vehiculos SET activo = ? WHERE id = ?", (nuevo_estado, vehiculo_id))
            conn.commit()
            flash(f"Estado del vehículo {vehiculo['placa']} actualizado.", "success")
        else:
            flash("Vehículo no encontrado.", "error")
        conn.close()
        return redirect(url_for("admin_checklists", tipo="vehiculos"))

    @app.route("/admin/vehiculos/eliminar/<int:vehiculo_id>")
    @login_required
    @admin_required
    def admin_vehiculo_eliminar(vehiculo_id):
        conn = get_db()
        conn.execute("DELETE FROM vehiculos WHERE id = ?", (vehiculo_id,))
        conn.commit()
        conn.close()
        flash("Vehículo eliminado correctamente.", "success")
        return redirect(url_for("admin_checklists", tipo="vehiculos"))

    @app.route("/admin/vehiculos/editar/<int:vehiculo_id>", methods=["POST"])
    @login_required
    @admin_required
    def admin_vehiculo_editar(vehiculo_id):
        tipo = request.form.get("tipo", "").strip()
        placa = request.form.get("placa", "").strip().upper()
        marca = request.form.get("marca", "").strip()
        serie = request.form.get("serie", "").strip()
        modelo = request.form.get("modelo", "").strip()
        tipo_ambulancia = request.form.get("tipo_ambulancia", "").strip() if tipo == "Ambulancia" else None
        movil = request.form.get("movil", "").strip() if tipo == "Ambulancia" else None
        soat_vigencia = request.form.get("soat_vigencia", "").strip() or None
        rtm_vigencia = request.form.get("rtm_vigencia", "").strip() or None
        
        if not tipo or not placa or not marca or not serie or not modelo:
            flash("El tipo, placa, marca, serie y modelo son obligatorios.", "error")
            return redirect(url_for("admin_checklists", tipo="vehiculos"))
            
        if tipo == "Ambulancia":
            if tipo_ambulancia not in ("TAB", "TAM"):
                flash("El tipo de ambulancia debe ser TAB o TAM.", "error")
                return redirect(url_for("admin_checklists", tipo="vehiculos"))
            if movil not in ("MOVIL 1", "MOVIL 2", "MOVIL 3", "MOVIL 4", "MOVIL 5", "MOVIL 6"):
                flash("El móvil seleccionado no es válido.", "error")
                return redirect(url_for("admin_checklists", tipo="vehiculos"))
            
        conn = get_db()
        existing = conn.execute("SELECT id FROM vehiculos WHERE placa = ? AND id != ?", (placa, vehiculo_id)).fetchone()
        if existing:
            flash(f"El vehículo con placa {placa} ya existe.", "error")
        else:
            conn.execute(
                """UPDATE vehiculos 
                   SET tipo = ?, placa = ?, marca = ?, serie = ?, modelo = ?, tipo_ambulancia = ?, movil = ?, soat_vigencia = ?, rtm_vigencia = ? 
                   WHERE id = ?""",
                (tipo, placa, marca, serie, modelo, tipo_ambulancia, movil, soat_vigencia, rtm_vigencia, vehiculo_id)
            )
            conn.commit()
            flash(f"Vehículo con placa {placa} actualizado con éxito.", "success")
        conn.close()
        return redirect(url_for("admin_checklists", tipo="vehiculos"))

    # ── Admin: Gestión de Categorías ────────────────────────────────────────────────
    @app.route("/admin/categorias/agregar", methods=["POST"])
    @login_required
    @admin_required
    def admin_categoria_agregar():
        tipo = request.form.get("tipo_checklist", "tam")
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("El nombre de la categoría es obligatorio.", "error")
            return redirect(url_for("admin_checklists", tipo=tipo))
            
        conn = get_db()
        existing = conn.execute("SELECT id FROM checklist_categorias WHERE tipo_checklist = ? AND nombre = ?", (tipo, nombre)).fetchone()
        if existing:
            flash("Esta categoría ya existe.", "error")
        else:
            conn.execute("INSERT INTO checklist_categorias (tipo_checklist, nombre, activo) VALUES (?, ?, 1)", (tipo, nombre))
            conn.commit()
            flash(f"Categoría «{nombre}» agregada.", "success")
        conn.close()
        return redirect(url_for("admin_checklists", tipo=tipo))

    @app.route("/admin/categorias/editar/<int:cat_id>", methods=["POST"])
    @login_required
    @admin_required
    def admin_categoria_editar(cat_id):
        nuevo_nombre = request.form.get("nuevo_nombre", "").strip()
        if not nuevo_nombre:
            flash("El nombre no puede estar vacío.", "error")
            return redirect(request.referrer or url_for("dashboard"))
            
        conn = get_db()
        cat = conn.execute("SELECT * FROM checklist_categorias WHERE id = ?", (cat_id,)).fetchone()
        if cat:
            tipo = cat["tipo_checklist"]
            viejo_nombre = cat["nombre"]
            
            # Check if new name already exists
            existing = conn.execute("SELECT id FROM checklist_categorias WHERE tipo_checklist = ? AND nombre = ? AND id != ?", (tipo, nuevo_nombre, cat_id)).fetchone()
            if existing:
                flash("Ya existe otra categoría con ese nombre.", "error")
            else:
                # Update category
                conn.execute("UPDATE checklist_categorias SET nombre = ? WHERE id = ?", (nuevo_nombre, cat_id))
                # Cascade update to items
                conn.execute("UPDATE checklist_items SET categoria = ? WHERE tipo_checklist = ? AND categoria = ?", (nuevo_nombre, tipo, viejo_nombre))
                conn.commit()
                flash(f"Categoría renombrada a «{nuevo_nombre}».", "success")
            conn.close()
            return redirect(url_for("admin_checklists", tipo=tipo))
        
        conn.close()
        flash("Categoría no encontrada.", "error")
        return redirect(request.referrer or url_for("dashboard"))

    @app.route("/admin/categorias/toggle/<int:cat_id>")
    @login_required
    @admin_required
    def admin_categoria_toggle(cat_id):
        conn = get_db()
        cat = conn.execute("SELECT * FROM checklist_categorias WHERE id = ?", (cat_id,)).fetchone()
        if cat:
            nuevo = 0 if cat["activo"] else 1
            conn.execute("UPDATE checklist_categorias SET activo = ? WHERE id = ?", (nuevo, cat_id))
            conn.commit()
            flash(f"Categoría «{cat['nombre']}» {'activada' if nuevo else 'desactivada'}.", "success")
            conn.close()
            return redirect(url_for("admin_checklists", tipo=cat["tipo_checklist"]))
        conn.close()
        flash("Categoría no encontrada.", "error")
        return redirect(request.referrer or url_for("dashboard"))

    # ── Admin: Gestión de Ítems de Checklists ───────────────────────────────────────
    @app.route("/admin/checklists")
    @login_required
    @admin_required
    def admin_checklists():
        tipo = request.args.get("tipo", "vehiculos")
        if tipo not in ("tam", "tab", "pasb", "pasm", "preoperacional", "vehiculos", "aseguradoras", "aseguradoras_soat", "equipos", "calif_atencion", "segur_paciente", "avanzada", "archivador"):
            tipo = "tam"
        conn = get_db()
        
        # When showing vehiculos tab, load vehicle data instead of checklist items
        if tipo == "vehiculos":
            vehiculos_raw = conn.execute("SELECT * FROM vehiculos ORDER BY tipo, placa").fetchall()
            vehiculos = []
            fecha_hoy = hoy()
            for row in vehiculos_raw:
                v = dict(row)
                
                # Process SOAT
                soat = v["soat_vigencia"]
                v["soat_dias"] = None
                v["soat_alerta"] = False
                v["soat_texto"] = "—"
                if soat:
                    if isinstance(soat, str):
                        try:
                            d_val = datetime.strptime(soat.split()[0], "%Y-%m-%d").date()
                        except Exception:
                            d_val = None
                    else:
                        d_val = soat
                    if d_val:
                        v["soat_dias"] = (d_val - fecha_hoy).days
                        v["soat_texto"] = d_val.strftime("%d/%m/%Y")
                        if v["soat_dias"] in (1, 2, 3, 4, 5, 10, 15):
                            v["soat_alerta"] = True
                            
                # Process RTM
                rtm = v["rtm_vigencia"]
                v["rtm_dias"] = None
                v["rtm_alerta"] = False
                v["rtm_texto"] = "—"
                if rtm:
                    if isinstance(rtm, str):
                        try:
                            d_val = datetime.strptime(rtm.split()[0], "%Y-%m-%d").date()
                        except Exception:
                            d_val = None
                    else:
                        d_val = rtm
                    if d_val:
                        v["rtm_dias"] = (d_val - fecha_hoy).days
                        v["rtm_texto"] = d_val.strftime("%d/%m/%Y")
                        if v["rtm_dias"] in (1, 2, 3, 4, 5, 10, 15):
                            v["rtm_alerta"] = True
                            
                vehiculos.append(v)
            conn.close()
            return render_template("admin_checklists.html", items=[], categorias=[], tipo=tipo,
                                   vehiculos=vehiculos, usuario=session["usuario"])
                                   
        # When showing aseguradoras tab
        if tipo == "aseguradoras":
            aseguradoras_list = conn.execute("SELECT * FROM aseguradoras ORDER BY nombre").fetchall()
            conn.close()
            return render_template("admin_checklists.html", items=[], categorias=[], tipo=tipo,
                                   aseguradoras_todas=aseguradoras_list, usuario=session["usuario"])

        # When showing aseguradoras SOAT tab
        if tipo == "aseguradoras_soat":
            soat_list = conn.execute("SELECT * FROM aseguradoras_soat ORDER BY nombre").fetchall()
            conn.close()
            return render_template("admin_checklists.html", items=[], categorias=[], tipo=tipo,
                                   aseguradoras_soat_todas=soat_list, usuario=session["usuario"])

        # When showing archivador tab
        if tipo == "archivador":
            from routes.routes_archivador import get_categorias, get_formularios_por_categoria
            categorias_arch = get_categorias(conn)
            formularios_por_cat = get_formularios_por_categoria(conn)
            conn.close()
            return render_template("admin_checklists.html", items=[], categorias=[], tipo=tipo,
                                   archivador_categorias=categorias_arch,
                                   archivador_formularios_por_cat=formularios_por_cat,
                                   usuario=session["usuario"])

        items = conn.execute(
            "SELECT * FROM checklist_items WHERE tipo_checklist = ? ORDER BY categoria, id",
            (tipo,)
        ).fetchall()
        categorias = conn.execute(
            "SELECT * FROM checklist_categorias WHERE tipo_checklist = ? ORDER BY nombre",
            (tipo,)
        ).fetchall()
        conn.close()
        return render_template("admin_checklists.html", items=items, categorias=categorias, tipo=tipo,
                               vehiculos=[], usuario=session["usuario"])


    @app.route("/admin/checklists/agregar", methods=["POST"])
    @login_required
    @admin_required
    def admin_checklist_agregar():
        tipo = request.form.get("tipo_checklist", "tam")
        categoria = request.form.get("categoria", "").strip()
        nombre = request.form.get("nombre", "").strip()

        if not categoria or not nombre:
            flash("La categoría y el nombre son obligatorios.", "error")
            return redirect(url_for("admin_checklists", tipo=tipo))

        cantidad = None
        if tipo in ("tam", "tab", "pasb", "pasm", "avanzada"):
            cantidad_raw = request.form.get("cantidad", "").strip()
            try:
                cantidad = int(cantidad_raw)
            except (ValueError, TypeError):
                cantidad = 1

        # Generate a slug from category + name to allow same name in different categories
        import re
        cat_slug  = re.sub(r"[^a-z0-9]+", "_", categoria.lower().strip())[:30]
        nom_slug  = re.sub(r"[^a-z0-9]+", "_", nombre.lower().strip())[:30]
        identificador = f"{cat_slug}_{nom_slug}"

        conn = get_db()
        # Check if already exists (same name + category combination)
        existing = conn.execute(
            "SELECT id FROM checklist_items WHERE tipo_checklist = ? AND nombre = ? AND categoria = ?",
            (tipo, nombre, categoria)
        ).fetchone()
        if existing:
            flash("Ya existe un ítem con ese nombre en esta categoría del checklist.", "error")
        else:
            conn.execute(
                "INSERT INTO checklist_items (tipo_checklist, categoria, identificador, nombre, activo, cantidad) VALUES (?, ?, ?, ?, 1, ?)",
                (tipo, categoria, identificador, nombre, cantidad)
            )
            conn.commit()
            flash(f"Ítem «{nombre}» agregado al checklist {tipo.upper()}.", "success")
        conn.close()
        return redirect(url_for("admin_checklists", tipo=tipo))


    @app.route("/admin/checklists/toggle/<int:item_id>")
    @login_required
    @admin_required
    def admin_checklist_toggle(item_id):
        conn = get_db()
        item = conn.execute("SELECT * FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
        if item:
            nuevo = 0 if item["activo"] else 1
            conn.execute("UPDATE checklist_items SET activo = ? WHERE id = ?", (nuevo, item_id))
            conn.commit()
            flash(f"Ítem «{item['nombre']}» {'activado' if nuevo else 'desactivado'}.", "success")
            conn.close()
            return redirect(url_for("admin_checklists", tipo=item["tipo_checklist"]))
        conn.close()
        flash("Ítem no encontrado.", "error")
        return redirect(url_for("admin_checklists"))


    @app.route("/admin/checklists/eliminar/<int:item_id>")
    @login_required
    @admin_required
    def admin_checklist_eliminar(item_id):
        conn = get_db()
        item = conn.execute("SELECT * FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
        if item:
            tipo = item["tipo_checklist"]
            conn.execute("DELETE FROM checklist_items WHERE id = ?", (item_id,))
            conn.commit()
            flash(f"Ítem «{item['nombre']}» eliminado permanentemente.", "success")
            conn.close()
            return redirect(url_for("admin_checklists", tipo=tipo))
        conn.close()
        flash("Ítem no encontrado.", "error")
        return redirect(url_for("admin_checklists"))


    @app.route("/configurar_institucion", methods=["POST"])
    @login_required
    @admin_required
    def configurar_institucion():
        nombre = request.form.get("nombre_institucion", "").strip()
        subtitulo = request.form.get("subtitulo_institucion", "").strip()
        nit = request.form.get("nit", "").strip()
        nombre_sistema = request.form.get("nombre_sistema", "").strip()
        habilitacion_codigos = request.form.getlist("habilitacion_codigo[]")
        habilitacion_descripciones = request.form.getlist("habilitacion_descripcion[]")

        habilitaciones = []
        for codigo, descripcion in zip(habilitacion_codigos, habilitacion_descripciones):
            codigo = codigo.strip()
            descripcion = descripcion.strip()
            if codigo or descripcion:
                habilitaciones.append({"codigo": codigo, "descripcion": descripcion})

        if not habilitaciones:
            legacy_habilitacion = request.form.get("habilitacion", "").strip()
            if legacy_habilitacion:
                habilitaciones = [{"codigo": legacy_habilitacion, "descripcion": ""}]

        logo_file = request.files.get("logo_file")
        marca_agua_file = request.files.get("marca_agua_file")

        conn = get_db()
        try:
            if nombre:
                conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('nombre_institucion', ?)", (nombre,))
            if subtitulo:
                conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('subtitulo_institucion', ?)", (subtitulo,))
            if nit:
                conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('nit', ?)", (nit,))
            if nombre_sistema:
                conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('nombre_sistema', ?)", (nombre_sistema,))

            if habilitaciones:
                import json
                serialized_habilitaciones = json.dumps(habilitaciones)
                conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('habilitaciones', ?)", (serialized_habilitaciones,))
                conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('habilitacion', ?)", (str(json.dumps(habilitaciones)),))
            else:
                conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('habilitaciones', ?)", ("[]",))
                conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('habilitacion', ?)", ("",))
                
            if logo_file and logo_file.filename:
                import os
                from datetime import datetime
                # Create static/uploads directory if it doesn't exist
                upload_dir = os.path.join(app.root_path, 'static', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Get extension and save file
                ext = logo_file.filename.rsplit('.', 1)[1].lower() if '.' in logo_file.filename else 'png'
                filename = f"logo_institucion.{ext}"
                filepath = os.path.join(upload_dir, filename)
                
                logo_file.save(filepath)
                
                # Generate a URL with a timestamp to avoid browser caching issues when replacing the logo
                logo_url = f"/static/uploads/{filename}?v={int(ahora().timestamp())}"
                
                conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('logo', ?)", (logo_url,))
                
            if marca_agua_file and marca_agua_file.filename:
                import os
                # Create static/uploads directory if it doesn't exist
                upload_dir = os.path.join(app.root_path, 'static', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)
                
                # Get extension and save file
                ext = marca_agua_file.filename.rsplit('.', 1)[1].lower() if '.' in marca_agua_file.filename else 'png'
                filename = f"marca_agua_institucion.{ext}"
                filepath = os.path.join(upload_dir, filename)
                
                marca_agua_file.save(filepath)
                
                # Generate a URL with a timestamp to avoid browser caching issues when replacing the watermark
                marca_agua_url = f"/static/uploads/{filename}?v={int(ahora().timestamp())}"
                
                conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('marca_agua', ?)", (marca_agua_url,))
                
            conn.commit()
            app.clear_config_cache()
            flash("Configuración guardada exitosamente.", "success")
        except Exception as e:
            import traceback
            print("ERROR IN configurar_institucion:", e)
            print(traceback.format_exc())
            flash(f"Error al guardar: {e}", "error")
        finally:
            conn.close()
            return redirect(url_for("configuracion"))

    @app.route("/configuracion", methods=["GET"])
    @login_required
    @admin_required
    def configuracion():
        conn = get_db()
        aseguradoras_list = conn.execute("SELECT * FROM aseguradoras ORDER BY nombre").fetchall()
        conn.close()
        return render_template("configuracion.html", usuario=session["usuario"], aseguradoras_todas=aseguradoras_list)


    @app.route("/admin/aseguradoras/agregar", methods=["POST"])
    @login_required
    @admin_required
    def admin_aseguradora_agregar():
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("El nombre de la aseguradora es obligatorio.", "error")
            return redirect(url_for("admin_checklists", tipo="aseguradoras"))
        
        conn = get_db()
        try:
            conn.execute("INSERT INTO aseguradoras (nombre, activo) VALUES (?, 1)", (nombre,))
            conn.commit()
            flash(f"Aseguradora «{nombre}» agregada con éxito.", "success")
        except Exception as e:
            if "UNIQUE" in str(e):
                flash(f"La aseguradora «{nombre}» ya existe.", "error")
            else:
                flash(f"Error al agregar aseguradora: {e}", "error")
        finally:
            conn.close()
        return redirect(url_for("admin_checklists", tipo="aseguradoras"))


    @app.route("/admin/aseguradoras/toggle/<int:aseg_id>")
    @login_required
    @admin_required
    def admin_aseguradora_toggle(aseg_id):
        conn = get_db()
        aseg = conn.execute("SELECT * FROM aseguradoras WHERE id = ?", (aseg_id,)).fetchone()
        if aseg:
            nuevo_estado = 0 if aseg["activo"] else 1
            conn.execute("UPDATE aseguradoras SET activo = ? WHERE id = ?", (nuevo_estado, aseg_id))
            conn.commit()
            flash(f"Estado de la aseguradora «{aseg['nombre']}» actualizado correctamente.", "success")
        else:
            flash("Aseguradora no encontrada.", "error")
        conn.close()
        return redirect(url_for("admin_checklists", tipo="aseguradoras"))


    @app.route("/admin/aseguradoras/eliminar/<int:aseg_id>")
    @login_required
    @admin_required
    def admin_aseguradora_eliminar(aseg_id):
        conn = get_db()
        aseg = conn.execute("SELECT * FROM aseguradoras WHERE id = ?", (aseg_id,)).fetchone()
        if aseg:
            conn.execute("DELETE FROM aseguradoras WHERE id = ?", (aseg_id,))
            conn.commit()
            flash(f"Aseguradora «{aseg['nombre']}» eliminada permanentemente.", "success")
        else:
            flash("Aseguradora no encontrada.", "error")
        conn.close()
        return redirect(url_for("admin_checklists", tipo="aseguradoras"))


    # ── CRUD Aseguradoras SOAT ────────────────────────────────────────────────────
    @app.route("/admin/aseguradoras-soat/agregar", methods=["POST"])
    @login_required
    @admin_required
    def admin_aseguradora_soat_agregar():
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("El nombre de la aseguradora SOAT es obligatorio.", "error")
            return redirect(url_for("admin_checklists", tipo="aseguradoras_soat"))
        conn = get_db()
        try:
            conn.execute("INSERT INTO aseguradoras_soat (nombre, activo) VALUES (?, 1)", (nombre,))
            conn.commit()
            flash(f"Aseguradora SOAT «{nombre}» agregada con éxito.", "success")
        except Exception as e:
            if "UNIQUE" in str(e) or "Duplicate" in str(e):
                flash(f"La aseguradora SOAT «{nombre}» ya existe.", "error")
            else:
                flash(f"Error al agregar aseguradora SOAT: {e}", "error")
        finally:
            conn.close()
        return redirect(url_for("admin_checklists", tipo="aseguradoras_soat"))


    @app.route("/admin/aseguradoras-soat/toggle/<int:aseg_id>")
    @login_required
    @admin_required
    def admin_aseguradora_soat_toggle(aseg_id):
        conn = get_db()
        aseg = conn.execute("SELECT * FROM aseguradoras_soat WHERE id = ?", (aseg_id,)).fetchone()
        if aseg:
            nuevo_estado = 0 if aseg["activo"] else 1
            conn.execute("UPDATE aseguradoras_soat SET activo = ? WHERE id = ?", (nuevo_estado, aseg_id))
            conn.commit()
            flash(f"Estado de aseguradora SOAT «{aseg['nombre']}» actualizado.", "success")
        else:
            flash("Aseguradora SOAT no encontrada.", "error")
        conn.close()
        return redirect(url_for("admin_checklists", tipo="aseguradoras_soat"))


    @app.route("/admin/aseguradoras-soat/eliminar/<int:aseg_id>")
    @login_required
    @admin_required
    def admin_aseguradora_soat_eliminar(aseg_id):
        conn = get_db()
        aseg = conn.execute("SELECT * FROM aseguradoras_soat WHERE id = ?", (aseg_id,)).fetchone()
        if aseg:
            conn.execute("DELETE FROM aseguradoras_soat WHERE id = ?", (aseg_id,))
            conn.commit()
            flash(f"Aseguradora SOAT «{aseg['nombre']}» eliminada permanentemente.", "success")
        else:
            flash("Aseguradora SOAT no encontrada.", "error")
        conn.close()
        return redirect(url_for("admin_checklists", tipo="aseguradoras_soat"))
    @app.route("/admin/exportar_rips")
    @login_required
    @admin_required
    def exportar_rips():
        return render_template("exportar_rips.html", usuario=session.get("usuario"), date_hoy=hoy())

    @app.route("/api/pacientes_por_fecha")
    @login_required
    @admin_required
    def api_pacientes_por_fecha():
        fecha_inicio = request.args.get("fecha_inicio")
        fecha_fin = request.args.get("fecha_fin")
        if not fecha_inicio or not fecha_fin:
            return jsonify({"error": "Fechas inválidas"}), 400
            
        conn = get_db()
        pacientes = conn.execute(
            "SELECT id, primer_nombre, segundo_nombre, primer_apellido, segundo_apellido, identificacion_paciente as documento, fecha_registro FROM pacientes WHERE DATE(fecha_registro) >= %s AND DATE(fecha_registro) <= %s ORDER BY fecha_registro DESC", 
            (fecha_inicio, fecha_fin)
        ).fetchall()
        conn.close()
        
        # Formatear la respuesta
        from flask import jsonify
        for p in pacientes:
            p['nombre_completo'] = f"{p.get('primer_nombre','')} {p.get('segundo_nombre','')} {p.get('primer_apellido','')} {p.get('segundo_apellido','')}".replace("  ", " ").strip()
            
        return jsonify({"pacientes": pacientes})

    @app.route("/api/generar_rips_excel", methods=["POST"])
    @login_required
    @admin_required
    def api_generar_rips_excel():
        pacientes_json = request.form.get("pacientes_datos")
        codigo_prestador = request.form.get("codigo_prestador", "")
        
        if not pacientes_json:
            flash("No se han enviado datos de pacientes.", "error")
            return redirect(url_for("exportar_rips"))
            
        import json
        try:
            pacientes_seleccionados = json.loads(pacientes_json)
        except Exception:
            flash("Error al leer los datos de pacientes seleccionados.", "error")
            return redirect(url_for("exportar_rips"))
            
        if not pacientes_seleccionados:
            flash("Debe seleccionar al menos un paciente.", "warning")
            return redirect(url_for("exportar_rips"))
            
        conn = get_db()
        ids = [str(p['id']) for p in pacientes_seleccionados]
        placeholders = ','.join(['%s']*len(ids))
        pacientes_db = conn.execute(f"SELECT * FROM pacientes WHERE id IN ({placeholders})", tuple(ids)).fetchall()
        conn.close()
        
        # Mapear facturas
        facturas_map = {str(p['id']): p.get('factura', '').strip() for p in pacientes_seleccionados}
        
        # Build Lists for DataFrames
        general_data = [
            ["NÚMERO DE IDENTIFICACIÓN DEL PRESTADOR", codigo_prestador],
            ["CODIGO DE HABILITACION DEL PRESTADOR", "50011187901"]
        ]
        
        facturas_data = []
        usuarios_data = []
        procedimientos_data = []
        consultas_data = []
        medicamentos_data = []
        otros_servicios_data = []
        
        facturas_vistas = set()
        
        cups_map = {
            "TAB": "890201",
            "TAM": "890202",
            "PAS-B": "890101",
            "PAS-M": "890102"
        }
        
        for p in pacientes_db:
            p_id = str(p['id'])
            factura = facturas_map.get(p_id, "")
            
            # Facturas
            if factura and factura not in facturas_vistas:
                facturas_vistas.add(factura)
                facturas_data.append({
                    "NÚMERO DE FACTURA": factura,
                    "TIPO NOTA": "",
                    "NÚMERO NOTA": "",
                    "VALOR TOTAL NETO FACTURA": 0
                })
                
            # Usuarios
            cod_divipola = str(p.get("municipio_residencia", "")).split(" - ")[0].strip() if p.get("municipio_residencia") else ""
            
            usuarios_data.append({
                "NÚMERO DE FACTURA": factura,
                "TIPO DE IDENTIFICACION": p.get("tipo_documento", "CC"),
                "NÚMERO DE IDENTIFICACIÓN": p.get("documento") or p.get("identificacion_paciente", ""),
                "TIPO DE USUARIO": "01",
                "FECHA NACIMIENTO (DD/MM/AAAA)": p.get("fecha_nacimiento", ""),
                "SEXO": "M" if str(p.get("sexo")).upper().startswith("M") else "F" if str(p.get("sexo")).upper().startswith("F") else "I",
                "CÓDIGO PAIS RECIDENCIA": "170",
                "CÓDIGO DEL MUNICIPIO DE RESIDENCIA HABITUAL": cod_divipola,
                "ZONA DE RESIDENCIA HABITUAL": "01",
                "INCAPACIDAD": "02",
                "CONSECUTIVO": len(usuarios_data) + 1,
                "CÓDIGO PAIS ORIGEN": "170"
            })
            
            # Procedimientos
            tipo_servicio = str(p.get("tipo_servicio", "")).upper()
            cod_cups = cups_map.get(tipo_servicio, "890201")
            diag_prin = str(p.get("diagnostico_cie10", "")).split(" - ")[0].strip() if p.get("diagnostico_cie10") else "R69X"
            
            procedimientos_data.append({
                "DOCUMENTO USUARIO": p.get("documento") or p.get("identificacion_paciente", ""),
                "FECHA Y HORA PROCEDIMIENTO": p.get("fecha_inicio_atencion") or p.get("fecha_registro", ""),
                "idMIPRES": "",
                "NÚMERO DE AUTORIZACIÓN": "",
                "CODIGO PROCEDIMIENTO": cod_cups,
                "VIA DE INGRESO": "02",
                "MODALIDAD ATENCIÓN": "01",
                "GRUPO SERVICIO": "01",
                "CODIGO SERVICIO": "314",
                "FINALIDAD PROCEDIMIENTO": "44",
                "TIPO DE IDENTIFICACION PROFESIONAL DE LA SALUD": p.get("tipo_documento", "CC"),
                "NÚMERO DE IDENTIFICACIÓN PROFESIONAL DE LA SALUD": p.get("documento") or p.get("identificacion_paciente", ""),
                "DIAGNOSTICO PRINCIPAL": diag_prin,
                "DIAGNOSTICO RELACIONADO": "",
                "COMPLICACIÓN": "",
                "VALOR PROCEDIMIENTO": 0,
                "TIPO PAGO MODERADOR": "05",
                "VALOR CUOTA MODERADORA": 0,
                "NÚMERO FEV": factura
            })
            
        import pandas as pd
        from io import BytesIO
        from flask import send_file
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_general = pd.DataFrame(general_data)
            df_general.to_excel(writer, sheet_name="General", index=False, header=False)
            
            df_facturas = pd.DataFrame(facturas_data, columns=["NÚMERO DE FACTURA", "TIPO NOTA", "NÚMERO NOTA", "VALOR TOTAL NETO FACTURA"])
            df_facturas.to_excel(writer, sheet_name="Facturas", index=False)
            
            df_usuarios = pd.DataFrame(usuarios_data, columns=["NÚMERO DE FACTURA", "TIPO DE IDENTIFICACION", "NÚMERO DE IDENTIFICACIÓN", "TIPO DE USUARIO", "FECHA NACIMIENTO (DD/MM/AAAA)", "SEXO", "CÓDIGO PAIS RECIDENCIA", "CÓDIGO DEL MUNICIPIO DE RESIDENCIA HABITUAL", "ZONA DE RESIDENCIA HABITUAL", "INCAPACIDAD", "CONSECUTIVO", "CÓDIGO PAIS ORIGEN"])
            df_usuarios.to_excel(writer, sheet_name="Usuarios", index=False)
            
            df_consultas = pd.DataFrame(consultas_data, columns=["DOCUMENTO USUARIO", "FECHA Y HORA CONSULTA", "NÚMERO DE AUTORIZACIÓN", "CODIGO CONSULTA", "MODALIDAD ATENCIÓN", "GRUPO SERVICIO", "CÓDIGO SERVICIO", "FINALIDAD CONSULTA", "CAUSA EXTERNA", "DIAGNOSTICO PRINCIPAL", "DIAGNOSTICO RELACIONADO 1", "DIAGNOSTICO RELACIONADO 2", "DIAGNOSTICO RELACIONADO 3", "TIPO DIAGNÓSTICO PRINCIPAL", "TIPO DE IDENTIFICACION PROFESIONAL DE LA SALUD", "NÚMERO DE IDENTIFICACIÓN PROFESIONAL DE LA SALUD", "VALOR CONSULTA", "TIPO PAGO MODERADOR", "VALOR CUOTA MODERADORA", "NÚMERO FEV"])
            df_consultas.to_excel(writer, sheet_name="Consultas", index=False)
            
            df_procedimientos = pd.DataFrame(procedimientos_data, columns=["DOCUMENTO USUARIO", "FECHA Y HORA PROCEDIMIENTO", "idMIPRES", "NÚMERO DE AUTORIZACIÓN", "CODIGO PROCEDIMIENTO", "VIA DE INGRESO", "MODALIDAD ATENCIÓN", "GRUPO SERVICIO", "CODIGO SERVICIO", "FINALIDAD PROCEDIMIENTO", "TIPO DE IDENTIFICACION PROFESIONAL DE LA SALUD", "NÚMERO DE IDENTIFICACIÓN PROFESIONAL DE LA SALUD", "DIAGNOSTICO PRINCIPAL", "DIAGNOSTICO RELACIONADO", "COMPLICACIÓN", "VALOR PROCEDIMIENTO", "TIPO PAGO MODERADOR", "VALOR CUOTA MODERADORA", "NÚMERO FEV"])
            df_procedimientos.to_excel(writer, sheet_name="Procedimientos", index=False)
            
            df_medicamentos = pd.DataFrame(medicamentos_data, columns=["DOCUMENTO USUARIO", "NÚMERO DE AUTORIZACIÓN", "idMIPRES", "FECHA Y HORA ADMINISTRACIÓN (AAAA-MM-DD hh:mm)", "DIAGNOSTICO PRINCIPAL", "DIAGNOSTICO RELACIONADO", "TIPO MEDICAMENTO", "CÓDIGO MEDICAMENTO", "DESCRIPCIÓN MEDICAMENTO", "CONCENTRACIÓN MEDICAMENTO", "UNIDAD MEDIDA", "FORMA FARMACÉUTICA", "UNIDAD MEDIDA DISPENSA", "CANTIDAD MEDICAMENTO", "DÍAS TRATAMIENTO", "TIPO DE IDENTIFICACION PROFESIONAL QUE PRESCRIBE EL MEDICAMENTO", "NÚMERO DE IDENTIFICACIÓN PROFESIONAL QUE PRESCRIBE EL MEDICAMENTO", "VALOR UNITARIO", "VALOR TOTAL", "TIPO PAGO MODERADOR", "VALOR PAGO MODERADORA", "NÚMERO FEV"])
            df_medicamentos.to_excel(writer, sheet_name="Medicamentos", index=False)
            
            df_otros = pd.DataFrame(otros_servicios_data, columns=["DOCUMENTO USUARIO", "NÚMERO DE AUTORIZACIÓN", "idMIPRES", "FECHA Y HORA SERVICIO (AAAA-MM-DD hh:mm)", "TIPO SERVICIO", "CÓDIGO DEL SERVICIO", "NOMBRE DEL SERVICIO", "CANTIDAD", "TIPO DE IDENTIFICACION PROFESIONAL QUE ORDENA O REALIZA EL SERVICIO", "NÚMERO DE IDENTIFICACIÓN PROFESIONAL QUE ORDENA O REALIZA EL SERVICIO", "VALOR UNITARIO", "VALOR TOTAL", "TIPO PAGO MODERADOR", "VALOR PAGO MODERADORA", "NÚMERO FEV"])
            df_otros.to_excel(writer, sheet_name="Otros servicios", index=False)
            
        output.seek(0)
        return send_file(output, download_name="RIPS_Generado.xlsx", as_attachment=True, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/api/generar_rips", methods=["POST"])
    @login_required
    @admin_required
    def api_generar_rips():
        pacientes_json = request.form.get("pacientes_datos")
        codigo_prestador = request.form.get("codigo_prestador", "")
        
        if not pacientes_json:
            flash("No se han enviado datos de pacientes.", "error")
            return redirect(url_for("exportar_rips"))
            
        import json
        try:
            pacientes_seleccionados = json.loads(pacientes_json)
        except Exception:
            flash("Error al leer los datos de pacientes seleccionados.", "error")
            return redirect(url_for("exportar_rips"))
            
        if not pacientes_seleccionados:
            flash("Debe seleccionar al menos un paciente.", "warning")
            return redirect(url_for("exportar_rips"))
            
        conn = get_db()
        ids = [str(p['id']) for p in pacientes_seleccionados]
        placeholders = ','.join(['%s']*len(ids))
        pacientes = conn.execute(f"SELECT * FROM pacientes WHERE id IN ({placeholders})", tuple(ids)).fetchall()
        conn.close()
        
        # Mapear facturas
        facturas_map = {str(p['id']): p.get('factura', '').strip() for p in pacientes_seleccionados}
        
        cups_map = {
            "TAB": "890201",
            "TAM": "890202",
            "PAS-B": "890101",
            "PAS-M": "890102"
        }
        
        usuarios = []
        procedimientos = []
        urgencias = []
        
        num_factura_general = "" # We'll use the first non-empty invoice for the transaccion block, or maybe blank
        
        for p in pacientes:
            p_id = str(p['id'])
            factura = facturas_map.get(p_id, "")
            
            if factura and not num_factura_general:
                num_factura_general = factura
                
            # Construir Nodo Usuario
            cod_divipola = str(p.get("municipio_residencia", "")).split(" - ")[0].strip() if p.get("municipio_residencia") else ""
            usuario = {
                "tipoDocumentoIdentificacion": p.get("tipo_documento", "CC"),
                "numDocumentoIdentificacion": p.get("documento") or p.get("identificacion_paciente", ""),
                "tipoUsuario": "01",
                "fechaNacimiento": p.get("fecha_nacimiento", ""),
                "sexo": "M" if str(p.get("sexo")).upper().startswith("M") else "F" if str(p.get("sexo")).upper().startswith("F") else "I",
                "codMunicipioResidencia": cod_divipola,
                "codZonaTerritorialResidencia": "01",
                "incapacidad": "02",
                "consecutivo": len(usuarios) + 1
            }
            usuarios.append(usuario)
            
            # Procedimiento (el traslado)
            tipo_servicio = str(p.get("tipo_servicio", "")).upper()
            cod_cups = cups_map.get(tipo_servicio, "890201")
            diag_prin = str(p.get("diagnostico_cie10", "")).split(" - ")[0].strip() if p.get("diagnostico_cie10") else ""
            if not diag_prin:
                diag_prin = "R69X" # Diagnostico por defecto (Causa desconocida)
                
            procedimiento = {
                "feInicioAtencion": p.get("fecha_inicio_atencion") or p.get("fecha_registro", ""),
                "numAutorizacion": "",
                "codProcedimiento": cod_cups,
                "viaIngresoServicioSalud": "02",
                "modalidadGrupoServicioTecSal": "01",
                "grupoServicios": "01",
                "codServicio": "314",
                "finalidadTecnologiaSalud": "44",
                "tipoDocumentoIdentificacion": p.get("tipo_documento", "CC"),
                "numDocumentoIdentificacion": p.get("documento") or p.get("identificacion_paciente", ""),
                "codDiagnosticoPrincipal": diag_prin,
                "codDiagnosticoRelacionado": "",
                "codComplicacion": "",
                "vrServicio": 0,
                "conceptoRecaudo": "05",
                "valorPagoModerador": 0,
                "numFEVPagoModerador": "",
                "consecutivo": len(procedimientos) + 1
            }
            procedimientos.append(procedimiento)
            
        
        # Ensamblar JSON Final Res 2275
        rips = {
            "numDocumentoIdObligado": codigo_prestador,
            "numFactura": num_factura_general,
            "tipoNota": "",
            "numNota": "",
            "usuarios": usuarios,
            "procedimientos": procedimientos,
            "urgencias": urgencias,
            "transaccion": {
                "numDocumentoIdObligado": codigo_prestador,
                "numFactura": num_factura_general,
                "tipoNota": "",
                "numNota": ""
            }
        }
        
        from flask import Response
        response = Response(
            json.dumps(rips, ensure_ascii=False, indent=2), 
            mimetype='application/json',
            headers={"Content-disposition": f"attachment; filename=RIPS_{num_factura_general or 'sin_factura'}.json"}
        )
        return response

