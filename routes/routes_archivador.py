import os
import uuid
from flask import render_template, request, redirect, url_for, session, flash, current_app, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from db import get_db
from utils import login_required, ahora, get_user_info

def get_categorias(conn):
    rows = conn.execute("SELECT * FROM archivador_categorias ORDER BY activo DESC, nombre ASC").fetchall()
    return rows

def get_categoria_nombres(conn):
    rows = conn.execute("SELECT nombre FROM archivador_categorias WHERE activo = 1 ORDER BY nombre ASC").fetchall()
    return [r["nombre"] for r in rows]

def get_nombres_formulario(conn):
    rows = conn.execute("SELECT nombre FROM archivador_formularios WHERE activo = 1 ORDER BY nombre ASC").fetchall()
    return [r["nombre"] for r in rows]

def get_formularios_con_categoria(conn):
    rows = conn.execute("""
        SELECT af.nombre, af.categoria_id, ac.nombre as categoria_nombre
        FROM archivador_formularios af
        LEFT JOIN archivador_categorias ac ON af.categoria_id = ac.id
        WHERE af.activo = 1
        ORDER BY af.nombre ASC
    """).fetchall()
    return rows

def get_formularios(conn):
    rows = conn.execute("""
        SELECT af.*, ac.nombre as categoria_nombre
        FROM archivador_formularios af
        LEFT JOIN archivador_categorias ac ON af.categoria_id = ac.id
        ORDER BY af.activo DESC, af.nombre ASC
    """).fetchall()
    return rows

def get_formularios_por_categoria(conn):
    """Return dict mapping categoria_nombre -> list of formularios, plus uncategorized."""
    formularios = get_formularios(conn)
    result = {}
    for f in formularios:
        cat = f["categoria_nombre"] or "Sin categoría"
        if cat not in result:
            result[cat] = []
        result[cat].append(f)
    return result

def register_routes(app):
    @app.route("/archivador")
    @login_required
    def archivador_list():
        conn = get_db()
        search_query = request.args.get("search", "").strip()
        categoria_filter = request.args.get("categoria", "").strip()
        fecha_desde = request.args.get("fecha_desde", "").strip()
        fecha_hasta = request.args.get("fecha_hasta", "").strip()

        where = "1=1"
        params = []

        if search_query:
            where += " AND (nombre_formulario LIKE ? OR archivo_nombre LIKE ? OR descripcion LIKE ?)"
            params.extend([f"%{search_query}%", f"%{search_query}%", f"%{search_query}%"])

        if categoria_filter:
            where += " AND categoria = ?"
            params.append(categoria_filter)

        if fecha_desde:
            where += " AND fecha_documento >= ?"
            params.append(fecha_desde)

        if fecha_hasta:
            where += " AND fecha_documento <= ?"
            params.append(fecha_hasta)

        archivos = conn.execute(f"SELECT * FROM archivador WHERE {where} ORDER BY id DESC", params).fetchall()
        categorias = get_categoria_nombres(conn)
        conn.close()

        return render_template(
            "archivador.html",
            archivos=archivos,
            search_query=search_query,
            categoria_filter=categoria_filter,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            categorias=categorias
        )

    @app.route("/archivador/nuevo", methods=["GET", "POST"])
    @login_required
    def archivador_nuevo():
        conn = get_db()
        if request.method == "POST":
            nombre_formulario_select = request.form.get("nombre_formulario_select", "").strip()
            if nombre_formulario_select == "Otro":
                nombre_formulario = request.form.get("nombre_formulario_otro", "").strip()
            else:
                nombre_formulario = nombre_formulario_select

            categoria = request.form.get("categoria", "").strip()
            descripcion = request.form.get("descripcion", "").strip()
            fecha_documento = request.form.get("fecha_documento", "").strip()
            files = request.files.getlist("archivo")

            files = [f for f in files if f and f.filename]

            if not nombre_formulario or not files:
                msg = "Debes ingresar un nombre de formulario y seleccionar al menos un archivo."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": False, "message": msg, "redirect": url_for("archivador_nuevo")}), 400
                flash(msg, "error")
                return redirect(url_for("archivador_nuevo"))

            try:
                max_consecutivo_row = conn.execute(
                    "SELECT MAX(consecutivo) as max_c FROM archivador"
                ).fetchone()
                current_consecutivo = (max_consecutivo_row["max_c"] or 0) + 1
            except Exception:
                current_consecutivo = 1

            existing_frm = conn.execute("SELECT id FROM archivador_formularios WHERE nombre = ?", (nombre_formulario,)).fetchone()
            if not existing_frm:
                try:
                    conn.execute("INSERT INTO archivador_formularios (nombre, activo) VALUES (?, 1)", (nombre_formulario,))
                except Exception:
                    pass

            upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'archivador')
            os.makedirs(upload_folder, exist_ok=True)
            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
            firma, perfil, rm = get_user_info(conn, session["usuario"]["identificacion"])
            count = 0

            for file in files:
                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                file_path = os.path.join(upload_folder, unique_filename)
                file.save(file_path)

                archivo_url = f"/static/uploads/archivador/{unique_filename}"

                conn.execute("""
                    INSERT INTO archivador (
                        nombre_formulario, consecutivo, archivo_url, archivo_nombre,
                        fecha_registro, registrado_por, registrado_por_identificacion, perfil_registrador,
                        categoria, descripcion, fecha_documento
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    nombre_formulario,
                    current_consecutivo + count,
                    archivo_url,
                    filename,
                    now_str,
                    session["usuario"]["nombre"],
                    session["usuario"]["identificacion"],
                    perfil,
                    categoria or None,
                    descripcion or None,
                    fecha_documento or None
                ))
                count += 1

            conn.commit()
            conn.close()

            if count == 1:
                msg = f"Archivo subido correctamente. Consecutivo: #{current_consecutivo}"
            else:
                msg = f"{count} archivos subidos correctamente. Consecutivos: #{current_consecutivo} - #{current_consecutivo + count - 1}"

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"success": True, "message": msg, "redirect": url_for("archivador_list")})

            flash(msg, "success")
            return redirect(url_for("archivador_list"))

        nombres_formulario = get_nombres_formulario(conn)
        formularios_con_categoria = get_formularios_con_categoria(conn)
        categorias = get_categoria_nombres(conn)
        conn.close()

        return render_template(
            "archivador_nuevo.html",
            nombres_formulario=nombres_formulario,
            formularios_con_categoria=formularios_con_categoria,
            categorias=categorias,
            archivo=None
        )

    @app.route("/archivador/editar/<int:id>", methods=["GET", "POST"])
    @login_required
    def archivador_editar(id):
        conn = get_db()
        archivo = conn.execute("SELECT * FROM archivador WHERE id = ?", (id,)).fetchone()

        if not archivo:
            flash("Archivo no encontrado.", "error")
            conn.close()
            return redirect(url_for("archivador_list"))

        if request.method == "POST":
            nombre_formulario_select = request.form.get("nombre_formulario_select")
            nombre_formulario_otro = request.form.get("nombre_formulario_otro")
            nombre_formulario = nombre_formulario_otro if nombre_formulario_select == "Otro" else nombre_formulario_select
            nombre_formulario = nombre_formulario.strip() if nombre_formulario else ""
            
            categoria = request.form.get("categoria", "").strip()
            descripcion = request.form.get("descripcion", "").strip()
            fecha_documento = request.form.get("fecha_documento", "").strip()
            file = request.files.get("archivo")

            if not nombre_formulario:
                msg = "El nombre del formulario es obligatorio."
                if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                    return jsonify({"success": False, "message": msg, "redirect": url_for("archivador_editar", id=id)}), 400
                flash(msg, "error")
                return redirect(url_for("archivador_editar", id=id))

            archivo_url = archivo["archivo_url"]
            archivo_nombre = archivo["archivo_nombre"]

            if file and file.filename:
                old_path = os.path.join(current_app.root_path, archivo["archivo_url"].lstrip('/'))
                if os.path.exists(old_path):
                    os.remove(old_path)

                filename = secure_filename(file.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'archivador')
                os.makedirs(upload_folder, exist_ok=True)
                file_path = os.path.join(upload_folder, unique_filename)
                file.save(file_path)
                archivo_url = f"/static/uploads/archivador/{unique_filename}"
                archivo_nombre = filename

            conn.execute("""
                UPDATE archivador SET
                    nombre_formulario = ?, categoria = ?, descripcion = ?,
                    fecha_documento = ?, archivo_url = ?, archivo_nombre = ?
                WHERE id = ?
            """, (
                nombre_formulario,
                categoria or None,
                descripcion or None,
                fecha_documento or None,
                archivo_url,
                archivo_nombre,
                id
            ))

            existing_frm = conn.execute("SELECT id FROM archivador_formularios WHERE nombre = ?", (nombre_formulario,)).fetchone()
            if not existing_frm:
                try:
                    conn.execute("INSERT INTO archivador_formularios (nombre, activo) VALUES (?, 1)", (nombre_formulario,))
                except Exception:
                    pass

            conn.commit()
            conn.close()

            flash("Documento actualizado correctamente.", "success")
            return redirect(url_for("archivador_list"))

        nombres_formulario = get_nombres_formulario(conn)
        formularios_con_categoria = get_formularios_con_categoria(conn)
        categorias = get_categoria_nombres(conn)
        conn.close()

        return render_template(
            "archivador_nuevo.html",
            nombres_formulario=nombres_formulario,
            formularios_con_categoria=formularios_con_categoria,
            categorias=categorias,
            archivo=archivo
        )

    @app.route("/archivador/eliminar/<int:id>", methods=["POST"])
    @login_required
    def archivador_eliminar(id):
        conn = get_db()
        archivo = conn.execute("SELECT * FROM archivador WHERE id = ?", (id,)).fetchone()
        if not archivo:
            flash("Archivo no encontrado.", "error")
            return redirect(url_for("archivador_list"))

        file_path = os.path.join(current_app.root_path, archivo["archivo_url"].lstrip('/'))
        if os.path.exists(file_path):
            os.remove(file_path)

        conn.execute("DELETE FROM archivador WHERE id = ?", (id,))
        conn.commit()
        conn.close()

        flash("Archivo eliminado correctamente.", "success")
        return redirect(url_for("archivador_list"))

    # ════════════════════════════════════════════
    #  GESTIÓN DE ÍTEMS DEL ARCHIVADOR
    # ════════════════════════════════════════════

    @app.route("/archivador/gestion")
    @login_required
    def archivador_gestion():
        conn = get_db()
        categorias = get_categorias(conn)
        formularios = get_nombres_formulario(conn)
        conn.close()
        return render_template(
            "archivador_gestion.html",
            categorias=categorias,
            formularios=formularios,
            usuario=session["usuario"]
        )

    @app.route("/archivador/gestion/categoria/agregar", methods=["POST"])
    @login_required
    def archivador_categoria_agregar():
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("El nombre de la categoría es obligatorio.", "error")
            return redirect(url_for("admin_checklists", tipo="archivador"))

        conn = get_db()
        try:
            conn.execute("INSERT INTO archivador_categorias (nombre, activo) VALUES (?, 1)", (nombre,))
            conn.commit()
            flash(f"Categoría '{nombre}' agregada con éxito.", "success")
        except Exception as e:
            if "Duplicate" in str(e) or "UNIQUE" in str(e):
                flash(f"La categoría '{nombre}' ya existe.", "error")
            else:
                flash(f"Error al agregar la categoría: {e}", "error")
        conn.close()
        return redirect(url_for("admin_checklists", tipo="archivador"))

    @app.route("/archivador/gestion/categoria/toggle/<int:id>", methods=["POST"])
    @login_required
    def archivador_categoria_toggle(id):
        conn = get_db()
        cat = conn.execute("SELECT * FROM archivador_categorias WHERE id = ?", (id,)).fetchone()
        if not cat:
            flash("Categoría no encontrada.", "error")
            conn.close()
            return redirect(url_for("admin_checklists", tipo="archivador"))

        new_status = 0 if cat["activo"] == 1 else 1
        conn.execute("UPDATE archivador_categorias SET activo = ? WHERE id = ?", (new_status, id))
        conn.commit()
        conn.close()

        status_label = "activada" if new_status == 1 else "desactivada"
        flash(f"Categoría '{cat['nombre']}' {status_label}.", "success")
        return redirect(url_for("admin_checklists", tipo="archivador"))

    @app.route("/archivador/gestion/categoria/eliminar/<int:id>", methods=["POST"])
    @login_required
    def archivador_categoria_eliminar(id):
        conn = get_db()
        cat = conn.execute("SELECT * FROM archivador_categorias WHERE id = ?", (id,)).fetchone()
        if not cat:
            flash("Categoría no encontrada.", "error")
            conn.close()
            return redirect(url_for("admin_checklists", tipo="archivador"))

        conn.execute("DELETE FROM archivador_categorias WHERE id = ?", (id,))
        conn.commit()
        conn.close()

        flash(f"Categoría '{cat['nombre']}' eliminada.", "success")
        return redirect(url_for("admin_checklists", tipo="archivador"))

    @app.route("/archivador/gestion/formulario/agregar", methods=["POST"])
    @login_required
    def archivador_formulario_agregar():
        nombre = request.form.get("nombre", "").strip()
        categoria_id = request.form.get("categoria_id", "").strip()
        if not nombre:
            flash("El nombre del formulario es obligatorio.", "error")
            return redirect(url_for("admin_checklists", tipo="archivador"))

        categoria_id = int(categoria_id) if categoria_id else None
        conn = get_db()
        try:
            conn.execute("INSERT INTO archivador_formularios (nombre, activo, categoria_id) VALUES (?, 1, ?)", (nombre, categoria_id))
            conn.commit()
            flash(f"Formulario '{nombre}' agregado con éxito.", "success")
        except Exception as e:
            if "Duplicate" in str(e) or "UNIQUE" in str(e):
                flash(f"El formulario '{nombre}' ya existe.", "error")
            else:
                flash(f"Error al agregar el formulario: {e}", "error")
        conn.close()
        return redirect(url_for("admin_checklists", tipo="archivador"))

    @app.route("/archivador/gestion/formulario/editar/<int:id>", methods=["POST"])
    @login_required
    def archivador_formulario_editar(id):
        nuevo_nombre = request.form.get("nombre", "").strip()
        categoria_id = request.form.get("categoria_id", "").strip()
        if not nuevo_nombre:
            flash("El nombre del formulario es obligatorio.", "error")
            return redirect(url_for("admin_checklists", tipo="archivador"))

        categoria_id = int(categoria_id) if categoria_id else None
        conn = get_db()
        frm = conn.execute("SELECT * FROM archivador_formularios WHERE id = ?", (id,)).fetchone()
        if not frm:
            flash("Formulario no encontrado.", "error")
            conn.close()
            return redirect(url_for("admin_checklists", tipo="archivador"))

        old_nombre = frm["nombre"]
        try:
            conn.execute("UPDATE archivador_formularios SET nombre = ?, categoria_id = ? WHERE id = ?", (nuevo_nombre, categoria_id, id))
            conn.commit()
            flash(f"Formulario '{old_nombre}' actualizado.", "success")
        except Exception as e:
            if "Duplicate" in str(e) or "UNIQUE" in str(e):
                flash(f"Ya existe un formulario con el nombre '{nuevo_nombre}'.", "error")
            else:
                flash(f"Error al editar: {e}", "error")
        conn.close()
        return redirect(url_for("admin_checklists", tipo="archivador"))

    @app.route("/archivador/gestion/formulario/toggle/<int:id>", methods=["POST"])
    @login_required
    def archivador_formulario_toggle(id):
        conn = get_db()
        frm = conn.execute("SELECT * FROM archivador_formularios WHERE id = ?", (id,)).fetchone()
        if not frm:
            flash("Formulario no encontrado.", "error")
            conn.close()
            return redirect(url_for("admin_checklists", tipo="archivador"))

        new_status = 0 if frm["activo"] == 1 else 1
        conn.execute("UPDATE archivador_formularios SET activo = ? WHERE id = ?", (new_status, id))
        conn.commit()
        conn.close()

        status_label = "activado" if new_status == 1 else "desactivado"
        flash(f"Formulario '{frm['nombre']}' {status_label}.", "success")
        return redirect(url_for("admin_checklists", tipo="archivador"))

    @app.route("/archivador/gestion/formulario/eliminar/<int:id>", methods=["POST"])
    @login_required
    def archivador_formulario_eliminar(id):
        conn = get_db()
        frm = conn.execute("SELECT * FROM archivador_formularios WHERE id = ?", (id,)).fetchone()
        if not frm:
            flash("Formulario no encontrado.", "error")
            conn.close()
            return redirect(url_for("admin_checklists", tipo="archivador"))

        conn.execute("DELETE FROM archivador_formularios WHERE id = ?", (id,))
        conn.commit()
        conn.close()

        flash(f"Formulario '{frm['nombre']}' eliminado.", "success")
        return redirect(url_for("admin_checklists", tipo="archivador"))

    @app.route("/static/uploads/archivador/<path:filename>")
    def uploaded_archivador_file(filename):
        return send_from_directory(
            os.path.join(current_app.root_path, 'static', 'uploads', 'archivador'),
            filename
        )
