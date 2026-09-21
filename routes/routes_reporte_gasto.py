import json
from datetime import datetime
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db, get_pas_opciones
from utils import login_required, ahora, hoy, get_user_info

def tiene_permiso_reporte_gasto(usuario):
    if not usuario:
        return False
    if usuario.get("rol") == "admin":
        return True
    accesos = usuario.get("formularios_acceso", [])
    if isinstance(accesos, str):
        try:
            accesos = json.loads(accesos)
        except Exception:
            accesos = []
    if isinstance(accesos, dict):
        # En caso de que esté estructurado por perfiles
        flat_accesos = []
        for v in accesos.values():
            if isinstance(v, list):
                flat_accesos.extend(v)
            elif isinstance(v, str):
                flat_accesos.append(v)
        accesos = flat_accesos

    permisos_validos = {"avanzada", "pasm", "pasb", "tab", "tam", "reporte_gasto"}
    return any(p in permisos_validos for p in accesos)


def register_routes(app):

    @app.route("/reporte_gasto/nuevo", methods=["GET", "POST"])
    @login_required
    def form_reporte_gasto():
        if not tiene_permiso_reporte_gasto(session.get("usuario")):
            flash("No tienes permiso para acceder al Reporte de Gasto.", "error")
            return redirect(url_for("dashboard"))

        conn = get_db()
        user_ident = session["usuario"]["identificacion"]
        user_nom = session["usuario"]["nombre"]

        if request.method == "POST":
            data = request.form
            accion = data.get("accion", "finalizar").strip().lower()
            finalizado = 0 if accion == "borrador" else 1

            fecha = data.get("fecha", "").strip()
            nombre_evento = data.get("nombre_evento", "").strip()
            tipo_origen = data.get("tipo_origen", "").strip().upper()
            identificador_origen = data.get("identificador_origen", "").strip()
            observaciones = data.get("observaciones", "").strip()

            # Procesar artículos utilizados
            item_nombres = data.getlist("item_nombre[]")
            item_idents = data.getlist("item_identificador[]")
            item_cats = data.getlist("item_categoria[]")
            item_cants = data.getlist("item_cantidad[]")
            item_obs = data.getlist("item_observacion[]")

            articulos = []
            for i in range(len(item_nombres)):
                nom = item_nombres[i].strip() if i < len(item_nombres) else ""
                ident = item_idents[i].strip() if i < len(item_idents) else ""
                cat = item_cats[i].strip() if i < len(item_cats) else "General"
                cant_str = item_cants[i].strip() if i < len(item_cants) else "0"
                obs = item_obs[i].strip() if i < len(item_obs) else ""

                if not nom:
                    continue

                try:
                    cant = int(cant_str)
                except ValueError:
                    cant = 0

                if finalizado == 1 and cant <= 0:
                    conn.close()
                    flash(f"La cantidad utilizada para '{nom}' debe ser mayor a 0.", "error")
                    return redirect(url_for("form_reporte_gasto"))

                articulos.append({
                    "identificador": ident,
                    "nombre": nom,
                    "categoria": cat,
                    "cantidad": cant,
                    "observacion": obs
                })

            if finalizado == 1:
                faltantes = []
                if not fecha:
                    faltantes.append("Fecha")
                if not nombre_evento:
                    faltantes.append("Nombre del Evento")
                if not tipo_origen:
                    faltantes.append("Tipo de Origen")
                if not identificador_origen:
                    faltantes.append("Unidad / Origen")

                if faltantes:
                    conn.close()
                    flash(f"Los siguientes campos son obligatorios para finalizar: {', '.join(faltantes)}.", "error")
                    return redirect(url_for("form_reporte_gasto"))

                if not articulos:
                    conn.close()
                    flash("Debe registrar al menos un artículo utilizado con cantidad mayor a 0.", "error")
                    return redirect(url_for("form_reporte_gasto"))
            else:
                # Si es borrador y falta fecha o nombre, usar defaults seguros
                if not fecha:
                    fecha = hoy().strftime("%Y-%m-%d")
                if not nombre_evento:
                    nombre_evento = "Borrador de Gasto"

            firma, perfil, rm = get_user_info(conn, user_ident)
            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
            datos_json_str = json.dumps(articulos, ensure_ascii=False)

            # Buscar si el usuario actual ya tiene un borrador guardado en la base de datos
            borrador_previo = conn.execute(
                "SELECT id FROM reporte_gasto WHERE registrado_por_identificacion = ? AND finalizado = 0 ORDER BY id DESC LIMIT 1",
                (user_ident,)
            ).fetchone()

            if finalizado == 1:
                if borrador_previo:
                    conn.execute("""
                        UPDATE reporte_gasto
                        SET fecha = ?, nombre_evento = ?, tipo_origen = ?, identificador_origen = ?,
                            observaciones = ?, datos_json = ?, registrado_por = ?, perfil_registrador = ?,
                            firma_registrador = ?, fecha_registro = ?, finalizado = 1
                        WHERE id = ?
                    """, (
                        fecha, nombre_evento, tipo_origen, identificador_origen,
                        observaciones, datos_json_str, user_nom, perfil,
                        firma, now_str, borrador_previo["id"]
                    ))
                    reporte_id = borrador_previo["id"]
                else:
                    cursor = conn.execute("""
                        INSERT INTO reporte_gasto (
                            fecha, nombre_evento, tipo_origen, identificador_origen,
                            observaciones, datos_json,
                            registrado_por, registrado_por_identificacion, perfil_registrador,
                            firma_registrador, fecha_registro, finalizado
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """, (
                        fecha, nombre_evento, tipo_origen, identificador_origen,
                        observaciones, datos_json_str,
                        user_nom, user_ident, perfil,
                        firma, now_str
                    ))
                    reporte_id = cursor.lastrowid

                conn.commit()
                conn.close()
                flash(f"Reporte de Gasto #{reporte_id} finalizado y guardado exitosamente.", "success")
                return redirect(url_for("ver_reporte_gasto", reporte_id=reporte_id))

            else:
                # Guardar como borrador (finalizado = 0)
                if borrador_previo:
                    conn.execute("""
                        UPDATE reporte_gasto
                        SET fecha = ?, nombre_evento = ?, tipo_origen = ?, identificador_origen = ?,
                            observaciones = ?, datos_json = ?, registrado_por = ?, perfil_registrador = ?,
                            firma_registrador = ?, fecha_registro = ?, finalizado = 0
                        WHERE id = ?
                    """, (
                        fecha, nombre_evento, tipo_origen, identificador_origen,
                        observaciones, datos_json_str, user_nom, perfil,
                        firma, now_str, borrador_previo["id"]
                    ))
                else:
                    conn.execute("""
                        INSERT INTO reporte_gasto (
                            fecha, nombre_evento, tipo_origen, identificador_origen,
                            observaciones, datos_json,
                            registrado_por, registrado_por_identificacion, perfil_registrador,
                            firma_registrador, fecha_registro, finalizado
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        fecha, nombre_evento, tipo_origen, identificador_origen,
                        observaciones, datos_json_str,
                        user_nom, user_ident, perfil,
                        firma, now_str
                    ))

                conn.commit()
                conn.close()
                flash("💾 Borrador de Reporte de Gasto guardado correctamente.", "success")
                return redirect(url_for("form_reporte_gasto"))

        # GET: opciones iniciales de unidades para cada tipo
        pasb_ops = get_pas_opciones(conn, "pasb")
        pasm_ops = get_pas_opciones(conn, "pasm")

        # Vehículos TAM y TAB
        tam_rows = conn.execute("SELECT placa FROM vehiculos WHERE (tipo = 'TAM' OR tipo_ambulancia = 'TAM' OR tipo LIKE '%TAM%' OR tipo_ambulancia LIKE '%TAM%') AND activo = 1 ORDER BY placa").fetchall()
        tam_ops = [r["placa"] for r in tam_rows]
        try:
            tam_db = conn.execute("SELECT DISTINCT placa FROM checklist_tam WHERE placa IS NOT NULL AND placa != '' ORDER BY placa").fetchall()
            for r in tam_db:
                if r["placa"] not in tam_ops:
                    tam_ops.append(r["placa"])
        except Exception:
            pass

        tab_rows = conn.execute("SELECT placa FROM vehiculos WHERE (tipo = 'TAB' OR tipo_ambulancia = 'TAB' OR tipo LIKE '%TAB%' OR tipo_ambulancia LIKE '%TAB%') AND activo = 1 ORDER BY placa").fetchall()
        tab_ops = [r["placa"] for r in tab_rows]
        try:
            tab_db = conn.execute("SELECT DISTINCT placa FROM checklist_tab WHERE placa IS NOT NULL AND placa != '' ORDER BY placa").fetchall()
            for r in tab_db:
                if r["placa"] not in tab_ops:
                    tab_ops.append(r["placa"])
        except Exception:
            pass

        # Buscar si el usuario actual tiene un borrador guardado en BD
        borrador_row = conn.execute(
            "SELECT * FROM reporte_gasto WHERE registrado_por_identificacion = ? AND finalizado = 0 ORDER BY id DESC LIMIT 1",
            (user_ident,)
        ).fetchone()

        borrador = None
        if borrador_row:
            borrador = dict(borrador_row)
            if borrador.get("fecha"):
                try:
                    borrador["fecha"] = borrador["fecha"].strftime("%Y-%m-%d")
                except Exception:
                    borrador["fecha"] = str(borrador["fecha"])[:10]
            try:
                borrador["articulos"] = json.loads(borrador.get("datos_json") or "[]")
            except Exception:
                borrador["articulos"] = []

        hoy_str = hoy().strftime("%Y-%m-%d")
        conn.close()

        return render_template(
            "reporte_gasto.html",
            hoy=hoy_str,
            pasb_ops=pasb_ops,
            pasm_ops=pasm_ops,
            tam_ops=tam_ops,
            tab_ops=tab_ops,
            borrador=borrador,
            usuario=session["usuario"]
        )


    @app.route("/reporte_gasto/borrador/descartar", methods=["GET", "POST"])
    @login_required
    def descartar_borrador_gasto():
        if not tiene_permiso_reporte_gasto(session.get("usuario")):
            flash("No tienes permiso para realizar esta acción.", "error")
            return redirect(url_for("dashboard"))

        user_ident = session["usuario"]["identificacion"]
        conn = get_db()
        conn.execute(
            "DELETE FROM reporte_gasto WHERE registrado_por_identificacion = ? AND finalizado = 0",
            (user_ident,)
        )
        conn.commit()
        conn.close()
        flash("Borrador descartado correctamente. Puedes iniciar un nuevo reporte.", "info")
        return redirect(url_for("form_reporte_gasto"))


    @app.route("/api/reporte_gasto/autosave", methods=["POST"])
    @login_required
    def api_reporte_gasto_autosave():
        if not tiene_permiso_reporte_gasto(session.get("usuario")):
            return jsonify({"status": "forbidden"}), 403

        try:
            req_data = request.get_json(force=True) or {}
            fecha = (req_data.get("fecha") or hoy().strftime("%Y-%m-%d")).strip()
            nombre_evento = (req_data.get("nombre_evento") or "Borrador de Gasto").strip()
            tipo_origen = (req_data.get("tipo_origen") or "").strip().upper()
            identificador_origen = (req_data.get("identificador_origen") or "").strip()
            observaciones = (req_data.get("observaciones") or "").strip()
            articulos = req_data.get("articulos") or []

            user_ident = session["usuario"]["identificacion"]
            user_nom = session["usuario"]["nombre"]

            conn = get_db()
            firma, perfil, rm = get_user_info(conn, user_ident)
            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
            datos_json_str = json.dumps(articulos, ensure_ascii=False)

            borrador_previo = conn.execute(
                "SELECT id FROM reporte_gasto WHERE registrado_por_identificacion = ? AND finalizado = 0 ORDER BY id DESC LIMIT 1",
                (user_ident,)
            ).fetchone()

            if borrador_previo:
                conn.execute("""
                    UPDATE reporte_gasto
                    SET fecha = ?, nombre_evento = ?, tipo_origen = ?, identificador_origen = ?,
                        observaciones = ?, datos_json = ?, registrado_por = ?, perfil_registrador = ?,
                        firma_registrador = ?, fecha_registro = ?, finalizado = 0
                    WHERE id = ?
                """, (
                    fecha, nombre_evento, tipo_origen, identificador_origen,
                    observaciones, datos_json_str, user_nom, perfil,
                    firma, now_str, borrador_previo["id"]
                ))
                borrador_id = borrador_previo["id"]
            else:
                cur = conn.execute("""
                    INSERT INTO reporte_gasto (
                        fecha, nombre_evento, tipo_origen, identificador_origen,
                        observaciones, datos_json,
                        registrado_por, registrado_por_identificacion, perfil_registrador,
                        firma_registrador, fecha_registro, finalizado
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """, (
                    fecha, nombre_evento, tipo_origen, identificador_origen,
                    observaciones, datos_json_str,
                    user_nom, user_ident, perfil,
                    firma, now_str
                ))
                borrador_id = cur.lastrowid

            conn.commit()
            conn.close()
            return jsonify({"status": "success", "borrador_id": borrador_id, "updated_at": now_str})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500


    @app.route("/api/reporte_gasto/articulos_disponibles")
    @login_required
    def api_articulos_disponibles():
        tipo = request.args.get("tipo", "").strip().lower()
        ident = request.args.get("identificador", "").strip()

        if not tipo or not ident:
            return jsonify({"status": "error", "message": "Parámetros tipo e identificador requeridos.", "articulos": []}), 400

        tablas_map = {
            "pasb": ("checklist_pasb", "pasb_numero"),
            "pasm": ("checklist_pasm", "pasm_numero"),
            "tam":  ("checklist_tam",  "placa"),
            "tab":  ("checklist_tab",  "placa")
        }

        if tipo not in tablas_map:
            return jsonify({"status": "error", "message": "Tipo de origen no válido.", "articulos": []}), 400

        tabla, col_id = tablas_map[tipo]
        conn = get_db()
        try:
            # Buscar el checklist más reciente finalizado (o más reciente almacenado)
            row = conn.execute(
                f"SELECT datos_json FROM {tabla} WHERE {col_id} = ? AND finalizado = 1 AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                (ident,)
            ).fetchone()
            if not row:
                row = conn.execute(
                    f"SELECT datos_json FROM {tabla} WHERE {col_id} = ? AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                    (ident,)
                ).fetchone()

            conn.close()

            if not row or not row["datos_json"]:
                return jsonify({
                    "status": "not_found",
                    "message": f"No se encontraron checklists registrados para {tipo.upper()} '{ident}'.",
                    "articulos": []
                })

            datos = json.loads(row["datos_json"])
            articulos = []

            for field, info in datos.items():
                if field.startswith("_") or not isinstance(info, dict):
                    continue

                valor = str(info.get("valor", "")).strip().upper()
                if valor == "NA":
                    continue

                nombre = info.get("nombre") or field
                categoria = info.get("categoria") or "Insumos"
                cant_disp = 0

                # Obtener cantidad actual si está especificada
                if info.get("cant_actual") is not None and str(info.get("cant_actual")).strip() != "":
                    try:
                        cant_disp = int(info["cant_actual"])
                    except Exception:
                        cant_disp = 0
                elif valor == "SI":
                    # Si cumplió y no tiene cant_actual explícita, usar cantidad estándar o suma de vencimientos
                    fv = info.get("fecha_vencimiento")
                    if isinstance(fv, str) and fv.strip().startswith("["):
                        try:
                            fv = json.loads(fv)
                        except Exception:
                            pass
                    if isinstance(fv, list) and fv:
                        cant_disp = sum(int(e.get("cant") or 0) for e in fv if isinstance(e, dict))
                    else:
                        try:
                            cant_disp = int(info.get("cantidad") or 1)
                        except Exception:
                            cant_disp = 1

                if cant_disp > 0:
                    articulos.append({
                        "identificador": field,
                        "nombre": nombre,
                        "categoria": categoria,
                        "stock_disponible": cant_disp
                    })

            # Ordenar por nombre alfabéticamente
            articulos.sort(key=lambda x: x["nombre"].lower())

            return jsonify({
                "status": "success",
                "total": len(articulos),
                "articulos": articulos
            })

        except Exception as e:
            if conn:
                conn.close()
            return jsonify({"status": "error", "message": str(e), "articulos": []}), 500


    @app.route("/reporte_gasto/registros")
    @login_required
    def registros_reporte_gasto():
        if not tiene_permiso_reporte_gasto(session.get("usuario")):
            flash("No tienes permiso para consultar los reportes de gasto.", "error")
            return redirect(url_for("dashboard"))

        conn = get_db()
        fecha_filtro = request.args.get("fecha", hoy().strftime("%Y-%m-%d"))
        fecha_like = f"{fecha_filtro}%"

        is_admin = session.get("usuario", {}).get("rol") == "admin"
        user_ident = session.get("usuario", {}).get("identificacion")

        if is_admin:
            if fecha_filtro:
                rows = conn.execute(
                    "SELECT * FROM reporte_gasto WHERE finalizado = 1 AND fecha_registro LIKE ? ORDER BY id DESC",
                    (fecha_like,)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM reporte_gasto WHERE finalizado = 1 ORDER BY id DESC").fetchall()
        else:
            if fecha_filtro:
                rows = conn.execute(
                    "SELECT * FROM reporte_gasto WHERE finalizado = 1 AND fecha_registro LIKE ? AND registrado_por_identificacion = ? ORDER BY id DESC",
                    (fecha_like, user_ident)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reporte_gasto WHERE finalizado = 1 AND registrado_por_identificacion = ? ORDER BY id DESC",
                    (user_ident,)
                ).fetchall()

        items = []
        for r in rows:
            rd = dict(r)
            try:
                arts = json.loads(rd.get("datos_json") or "[]")
                rd["total_articulos"] = len(arts)
                rd["total_unidades"] = sum(a.get("cantidad", 0) for a in arts)
            except Exception:
                rd["total_articulos"] = 0
                rd["total_unidades"] = 0
            items.append(rd)

        conn.close()

        return render_template(
            "registros_reporte_gasto.html",
            items=items,
            fecha_filtro=fecha_filtro,
            usuario=session["usuario"]
        )


    @app.route("/reporte_gasto/ver/<int:reporte_id>")
    @login_required
    def ver_reporte_gasto(reporte_id):
        if not tiene_permiso_reporte_gasto(session.get("usuario")):
            flash("No tienes permiso para visualizar este reporte de gasto.", "error")
            return redirect(url_for("dashboard"))

        conn = get_db()
        row = conn.execute("SELECT * FROM reporte_gasto WHERE id = ?", (reporte_id,)).fetchone()
        if not row:
            conn.close()
            flash("Reporte de gasto no encontrado.", "error")
            return redirect(url_for("registros_reporte_gasto"))

        record = dict(row)

        is_admin = session.get("usuario", {}).get("rol") == "admin"
        user_ident = session.get("usuario", {}).get("identificacion")
        if not is_admin and record.get("registrado_por_identificacion") != user_ident:
            conn.close()
            flash("Solo puedes visualizar reportes de gasto que tú mismo hayas registrado.", "error")
            return redirect(url_for("registros_reporte_gasto"))

        articulos = []
        try:
            articulos = json.loads(record.get("datos_json") or "[]")
        except Exception:
            articulos = []

        from app import _load_config
        cfg_inst = _load_config()

        conn.close()

        return render_template(
            "ver_reporte_gasto.html",
            record=record,
            articulos=articulos,
            cfg=cfg_inst,
            usuario=session["usuario"]
        )
