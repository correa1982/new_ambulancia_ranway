import json
import os
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db, get_pas_opciones
from utils import login_required, admin_required, calcular_edad, get_user_info, ahora, hoy
# _load_config imported lazily inside functions to avoid circular import
from itsdangerous import URLSafeSerializer, BadSignature
from constants import CHECKLIST_CONFIG, PASB_OPCIONES, PASM_OPCIONES

CHECKLIST_COLS = {
    "tam":  ["fecha", "hora", "placa", "turno", "observaciones",
             "registrado_por", "registrado_por_identificacion",
             "perfil_registrador", "firma_registrador", "fecha_registro",
             "datos_json", "finalizado"],
    "tab":  ["fecha", "hora", "placa", "turno", "observaciones",
             "registrado_por", "registrado_por_identificacion",
             "perfil_registrador", "firma_registrador", "fecha_registro",
             "datos_json", "finalizado"],
    "avanzada": ["fecha", "hora", "evento", "botiquin", "observaciones",
                 "registrado_por", "registrado_por_identificacion",
                 "perfil_registrador", "firma_registrador", "fecha_registro",
                 "datos_json", "finalizado"],
    "pasb": ["fecha", "hora", "ubicacion", "pasb_numero",
             "carpas", "camillas", "sillas", "iluminacion",
             "oxigeno", "material_curacion", "medicamentos_basicos", "glucometro", "oximetro",
             "comunicaciones", "agua_saneamiento", "senalizacion",
             "personal_aph", "estado_operativo", "observaciones",
             "registrado_por", "registrado_por_identificacion",
             "perfil_registrador", "firma_registrador", "fecha_registro",
             "datos_json", "finalizado"],
    "pasm": ["fecha", "hora", "ubicacion", "pasm_numero",
             "carpas", "camillas", "sillas", "iluminacion",
             "monitor_desfibrilador", "ventilador", "bomba_infusion",
             "oxigeno", "material_curacion", "medicamentos_ava", "glucometro", "oximetro",
             "comunicaciones", "agua_saneamiento", "senalizacion",
             "personal_medico", "personal_enfermeria", "personal_aph",
             "estado_operativo", "observaciones",
             "registrado_por", "registrado_por_identificacion",
             "perfil_registrador", "firma_registrador", "fecha_registro",
             "datos_json", "finalizado"],
    "equipos": ["fecha", "hora", "grupo_equipos", "observaciones",
                "registrado_por", "registrado_por_identificacion",
                "perfil_registrador", "firma_registrador", "fecha_registro",
                "datos_json", "finalizado"],
    "calif_atencion": ["fecha", "hora", "primer_nombre", "primer_apellido",
                       "tipo_documento", "identificacion", "datos_json",
                       "registrado_por", "registrado_por_identificacion",
                       "perfil_registrador", "firma_registrador", "firma_paciente",
                       "responsable_nombre", "responsable_apellido",
                       "responsable_tipo_doc", "responsable_identificacion",
                       "finalizado", "fecha_registro"],
    "segur_paciente": ["fecha", "hora", "primer_nombre", "primer_apellido",
                       "tipo_documento", "identificacion", "nombre_reporte", "descripcion",
                       "datos_json",
                       "registrado_por", "registrado_por_identificacion",
                       "perfil_registrador", "firma_registrador",
                       "finalizado", "fecha_registro"],
}

def register_routes(app):
    @app.route("/checklist/<tipo>", methods=["GET", "POST"])
    @login_required
    def form_checklist(tipo):
        cfg = CHECKLIST_CONFIG.get(tipo)
        if not cfg:
            flash("Tipo de checklist no válido.", "error")
            return redirect(url_for("dashboard"))

        if request.method == "POST":
            data = request.form
            conn = get_db()
            firma, perfil, rm = get_user_info(conn, session["usuario"]["identificacion"])
            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")

            accion = data.get("accion", "finalizar")
            finalizado = 0 if accion == "borrador" else 1

            # Validar variables obligatorias al finalizar
            if finalizado == 1:
                faltantes = []
                fecha_val = data.get("fecha", "").strip()
                hora_val = data.get("hora", "").strip()
                if not fecha_val:
                    faltantes.append("Fecha")
                if not hora_val:
                    faltantes.append("Hora")

                if tipo in ("pasb", "pasm"):
                    ubicacion_val = data.get("ubicacion", "").strip()
                    pas_val = data.get("pasb_numero" if tipo == "pasb" else "pasm_numero", "").strip()
                    estado_val = data.get("estado_operativo", "").strip()
                    if not ubicacion_val:
                        faltantes.append("Ubicación / Lugar")
                    if not pas_val:
                        faltantes.append("Número del PASB" if tipo == "pasb" else "Número del PASM")
                    if not estado_val:
                        faltantes.append("Estado del Puesto")
                elif tipo in ("tam", "tab"):
                    placa_val = data.get("placa", "").strip()
                    if not placa_val:
                        faltantes.append("Placa del Vehículo")
                elif tipo == "avanzada":
                    evento_val = data.get("evento", "").strip()
                    botiquin_val = data.get("botiquin", "").strip()
                    if not evento_val:
                        faltantes.append("Evento")
                    if not botiquin_val:
                        faltantes.append("Botiquín")

                if faltantes:
                    conn.close()
                    flash(f"Los siguientes campos son obligatorios para finalizar: {', '.join(faltantes)}.", "error")
                    return redirect(request.referrer or url_for("form_checklist", tipo=tipo))

            # Dynamic: collect all checklist_item responses into JSON
            pasb_numero = data.get("pasb_numero", "")
            pasm_numero = data.get("pasm_numero", "")
            items_db = conn.execute(
                "SELECT * FROM checklist_items WHERE tipo_checklist = ? AND activo = 1 ORDER BY categoria, id",
                (tipo,)
            ).fetchall()
            datos = {}
            if tipo == "pasb" and pasb_numero:
                datos["pasb_numero"] = {
                    "nombre": "Número del PASB",
                    "categoria": "identificacion",
                    "valor": pasb_numero,
                    "observacion": ""
                }
            if tipo == "pasm" and pasm_numero:
                datos["pasm_numero"] = {
                    "nombre": "Número del PASM",
                    "categoria": "identificacion",
                    "valor": pasm_numero,
                    "observacion": ""
                }
            for item in items_db:
                val = data.get(item["identificador"], "")
                obs = data.get("obs_" + item["identificador"], "")
                fecha_venc = data.get("vencimiento_" + item["identificador"], "")
                if fecha_venc:
                    try:
                        fecha_venc_parsed = json.loads(fecha_venc)
                        if isinstance(fecha_venc_parsed, (list, dict)):
                            fecha_venc = fecha_venc_parsed
                    except Exception:
                        pass
                cant_actual = data.get("cant_actual_" + item["identificador"], "")
                tipo_incumplimiento = data.get("tipo_incumplimiento_" + item["identificador"], "")
                datos[item["identificador"]] = {
                    "nombre": item["nombre"],
                    "categoria": item["categoria"],
                    "cantidad": item.get("cantidad"),
                    "aplica_vencimiento": item.get("aplica_vencimiento", 0),
                    "valor": val,
                    "observacion": obs,
                    "fecha_vencimiento": fecha_venc,
                    "cant_actual": cant_actual,
                    "tipo_incumplimiento": tipo_incumplimiento
                }
            if tipo in ("avanzada", "tam", "tab", "pasm", "pasb"):
                nombres = request.form.getlist("integrante_nombre[]")
                identificaciones = request.form.getlist("integrante_doc[]")
                perfiles = request.form.getlist("integrante_perfil[]")
                integrantes = []
                for nom, ident, perf in zip(nombres, identificaciones, perfiles):
                    if nom.strip():
                        integrantes.append({
                            "nombre": nom.strip(),
                            "identificacion": ident.strip(),
                            "perfil": perf.strip()
                        })
                datos["_integrantes"] = integrantes

            datos_json_str = json.dumps(datos, ensure_ascii=False)

            table = cfg["table"]
            record_id = data.get("id") or request.args.get("id")

            if record_id:
                try:
                    record_id = int(record_id)
                except (ValueError, Exception):
                    record_id = None

            special_values = {
                "registrado_por": session["usuario"]["nombre"],
                "registrado_por_identificacion": session["usuario"]["identificacion"],
                "perfil_registrador": perfil,
                "firma_registrador": firma,
                "fecha_registro": now_str,
                "datos_json": datos_json_str,
                "finalizado": finalizado,
            }
            cols = CHECKLIST_COLS[tipo]
            values = [special_values.get(c, data.get(c, "")) for c in cols]

            if record_id:
                values.append(record_id)
                set_clause = ", ".join(f"{c} = ?" for c in cols)
                conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", tuple(values))
            else:
                placeholders = ", ".join(["?"] * len(cols))
                cursor = conn.execute(
                    f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders})",
                    tuple(values)
                )
                record_id = cursor.lastrowid

            conn.commit()
            conn.close()

            if request.form.get("_offline_sync") == "1":
                return jsonify({"status": "success", "id": record_id})

            if finalizado == 1:
                flash(f"{cfg['titulo']} finalizado y guardado correctamente.", "success")
                return redirect(url_for("registros_checklist", tipo=tipo))
            else:
                flash(f"Borrador de {cfg['titulo']} guardado correctamente.", "success")
                return redirect(url_for("form_checklist", tipo=tipo, id=record_id))

        # GET: load dynamic items for all checklists
        checklist_items_by_cat = {}
        vehiculos = []
        medicos = []
        enfermeros = []
        aphs = []
        record = None
        datos = {}

        conn = get_db()
        items_db = conn.execute(
            "SELECT * FROM checklist_items WHERE tipo_checklist = ? AND activo = 1 ORDER BY categoria, id",
            (tipo,)
        ).fetchall()
        vehiculos = []
        if tipo == "tam":
            try:
                veh_rows = conn.execute(
                    "SELECT placa, tipo FROM vehiculos WHERE (tipo = 'TAM' OR tipo LIKE '%TAM%') AND activo = 1 ORDER BY placa"
                ).fetchall()
                veh_placas = {r["placa"] for r in veh_rows}
                vehiculos = [dict(r) for r in veh_rows]
                tam_db = conn.execute(
                    "SELECT DISTINCT placa FROM checklist_tam WHERE placa IS NOT NULL AND placa != '' ORDER BY placa"
                ).fetchall()
                for r in tam_db:
                    if r["placa"] not in veh_placas:
                        vehiculos.append({"placa": r["placa"], "tipo": "TAM"})
                        veh_placas.add(r["placa"])
            except Exception:
                pass
            if not vehiculos:
                vehiculos = conn.execute("SELECT placa, tipo FROM vehiculos WHERE activo = 1 ORDER BY placa").fetchall()
        elif tipo == "tab":
            try:
                veh_rows = conn.execute(
                    "SELECT placa, tipo FROM vehiculos WHERE (tipo = 'TAB' OR tipo LIKE '%TAB%') AND activo = 1 ORDER BY placa"
                ).fetchall()
                veh_placas = {r["placa"] for r in veh_rows}
                vehiculos = [dict(r) for r in veh_rows]
                tab_db = conn.execute(
                    "SELECT DISTINCT placa FROM checklist_tab WHERE placa IS NOT NULL AND placa != '' ORDER BY placa"
                ).fetchall()
                for r in tab_db:
                    if r["placa"] not in veh_placas:
                        vehiculos.append({"placa": r["placa"], "tipo": "TAB"})
                        veh_placas.add(r["placa"])
            except Exception:
                pass
            if not vehiculos:
                vehiculos = conn.execute("SELECT placa, tipo FROM vehiculos WHERE activo = 1 ORDER BY placa").fetchall()
        else:
            vehiculos = conn.execute(
                "SELECT placa, tipo FROM vehiculos WHERE activo = 1 ORDER BY tipo, placa"
            ).fetchall()

        if tipo == "pasm":
            medicos = conn.execute(
                "SELECT nombre FROM usuarios WHERE activo = 1 AND (fecha_validez IS NULL OR fecha_validez >= CURDATE()) AND perfil LIKE '%Médico%' ORDER BY nombre"
            ).fetchall()
            enfermeros = conn.execute(
                "SELECT nombre FROM usuarios WHERE activo = 1 AND (fecha_validez IS NULL OR fecha_validez >= CURDATE()) AND perfil LIKE '%Enfermer%' ORDER BY nombre"
            ).fetchall()

        if tipo in ("pasm", "pasb"):
            aphs = conn.execute(
                "SELECT nombre FROM usuarios WHERE activo = 1 AND (fecha_validez IS NULL OR fecha_validez >= CURDATE()) AND perfil LIKE '%APH%' ORDER BY nombre"
            ).fetchall()

        todos_usuarios = []
        if tipo == "avanzada":
            try:
                usuarios_db = conn.execute(
                    "SELECT nombre, identificacion, perfil FROM usuarios WHERE activo = 1 AND (fecha_validez IS NULL OR fecha_validez >= CURDATE()) ORDER BY nombre"
                ).fetchall()
                todos_usuarios = [dict(u) for u in usuarios_db]
            except Exception:
                try:
                    usuarios_db = conn.execute(
                        "SELECT nombre, identificacion, perfil FROM usuarios WHERE activo = 1 ORDER BY nombre"
                    ).fetchall()
                    todos_usuarios = [dict(u) for u in usuarios_db]
                except Exception:
                    todos_usuarios = []

        # Load draft if ?id= provided
        record_id = request.args.get("id")
        if record_id:
            try:
                record_id = int(record_id)
                row = conn.execute(f"SELECT * FROM {cfg['table']} WHERE id = ?", (record_id,)).fetchone()
                if row:
                    r = dict(row)
                    is_owner = (session["usuario"]["rol"] == "admin" or
                                r.get("registrado_por_identificacion") == session["usuario"]["identificacion"])
                    if is_owner and r.get("finalizado") == 0:
                        record = r
                        if r.get("datos_json"):
                            try:
                                datos = json.loads(r["datos_json"])
                            except Exception:
                                pass
                    elif not is_owner:
                        flash("No puede editar registros de otros usuarios.", "error")
                    else:
                        flash("Este checklist ya fue finalizado y no se puede editar.", "error")
            except (ValueError, Exception):
                pass
        else:
            # Nuevo checklist: cargar las fechas de vencimiento del último checklist realizado
            precargado_ultimo = False
            try:
                if tipo in ("pasb", "pasm"):
                    col_pas = "pasb_numero" if tipo == "pasb" else "pasm_numero"
                    pas_num_param = request.args.get(col_pas)
                    if pas_num_param:
                        last_row = conn.execute(
                            f"SELECT datos_json FROM {cfg['table']} WHERE {col_pas} = ? AND finalizado = 1 AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                            (pas_num_param,)
                        ).fetchone()
                        if not last_row:
                            last_row = conn.execute(
                                f"SELECT datos_json FROM {cfg['table']} WHERE {col_pas} = ? AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                                (pas_num_param,)
                            ).fetchone()
                        if last_row and last_row["datos_json"]:
                            ultimo_datos = json.loads(last_row["datos_json"])
                            for field, info in ultimo_datos.items():
                                if field.startswith("_") or not isinstance(info, dict):
                                    continue
                                datos[field] = {
                                    "valor": info.get("valor", ""),
                                    "fecha_vencimiento": info.get("fecha_vencimiento", ""),
                                    "observacion": info.get("observacion", ""),
                                    "cant_actual": info.get("cant_actual", ""),
                                    "tipo_incumplimiento": info.get("tipo_incumplimiento", "")
                                }
                            precargado_ultimo = True
                    else:
                        precargado_ultimo = False
                        datos = {}
                elif tipo in ("tam", "tab"):
                    placa_param = request.args.get("placa")
                    if placa_param:
                        placa_clean = placa_param.strip()
                        last_row = conn.execute(
                            f"""SELECT datos_json FROM {cfg['table']} 
                                WHERE (UPPER(TRIM(placa)) = UPPER(TRIM(?)) 
                                       OR UPPER(REPLACE(REPLACE(TRIM(placa), '-', ''), ' ', '')) = UPPER(REPLACE(REPLACE(TRIM(?), '-', ''), ' ', '')))
                                  AND finalizado = 1 
                                  AND datos_json IS NOT NULL 
                                  AND datos_json != '' 
                                ORDER BY id DESC LIMIT 1""",
                            (placa_clean, placa_clean)
                        ).fetchone()
                        if last_row and last_row["datos_json"]:
                            ultimo_datos = json.loads(last_row["datos_json"])
                            for field, info in ultimo_datos.items():
                                if field.startswith("_") or not isinstance(info, dict):
                                    continue
                                datos[field] = {
                                    "valor": info.get("valor", ""),
                                    "fecha_vencimiento": info.get("fecha_vencimiento", ""),
                                    "observacion": info.get("observacion", ""),
                                    "cant_actual": info.get("cant_actual", ""),
                                    "tipo_incumplimiento": info.get("tipo_incumplimiento", "")
                                }
                            precargado_ultimo = True
                    else:
                        precargado_ultimo = False
                        datos = {}
                elif tipo == "avanzada":
                    botiquin_param = request.args.get("botiquin")
                    if botiquin_param:
                        last_row = conn.execute(
                            f"SELECT datos_json FROM checklist_avanzada WHERE botiquin = ? AND finalizado = 1 AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                            (botiquin_param,)
                        ).fetchone()
                        if not last_row:
                            last_row = conn.execute(
                                f"SELECT datos_json FROM checklist_avanzada WHERE botiquin = ? AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                                (botiquin_param,)
                            ).fetchone()
                        if last_row and last_row["datos_json"]:
                            ultimo_datos = json.loads(last_row["datos_json"])
                            for field, info in ultimo_datos.items():
                                if field.startswith("_") or not isinstance(info, dict):
                                    continue
                                datos[field] = {
                                    "valor": info.get("valor", ""),
                                    "fecha_vencimiento": info.get("fecha_vencimiento", ""),
                                    "observacion": info.get("observacion", ""),
                                    "cant_actual": info.get("cant_actual", ""),
                                    "tipo_incumplimiento": info.get("tipo_incumplimiento", "")
                                }
                            precargado_ultimo = True
                    else:
                        precargado_ultimo = False
                        datos = {}
                else:
                    last_row = conn.execute(
                        f"SELECT datos_json FROM {cfg['table']} WHERE datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    if last_row and last_row["datos_json"]:
                        ultimo_datos = json.loads(last_row["datos_json"])
                        for field, info in ultimo_datos.items():
                            if field.startswith("_") or not isinstance(info, dict):
                                continue
                            datos[field] = {
                                "valor": info.get("valor", ""),
                                "fecha_vencimiento": info.get("fecha_vencimiento", ""),
                                "observacion": info.get("observacion", ""),
                                "cant_actual": info.get("cant_actual", ""),
                                "tipo_incumplimiento": info.get("tipo_incumplimiento", "")
                            }
                        precargado_ultimo = True
            except Exception:
                pass

        # Cargar entregas/traslados pendientes desde inventario
        traslados_pendientes = []
        if tipo in ("pasb", "pasm", "tam", "tab", "avanzada"):
            try:
                rows_traslados = conn.execute(
                    "SELECT * FROM checklist_pasb_traslados WHERE estado = 'pendiente' ORDER BY fecha_salida DESC"
                ).fetchall()
                for tr in rows_traslados:
                    d_tr = dict(tr)
                    if d_tr.get("fecha_vencimiento") and hasattr(d_tr["fecha_vencimiento"], "strftime"):
                        d_tr["fecha_vencimiento"] = d_tr["fecha_vencimiento"].strftime("%Y-%m-%d")
                    traslados_pendientes.append(d_tr)
            except Exception:
                traslados_pendientes = []

        pasb_opciones = get_pas_opciones(conn, "pasb")
        pasm_opciones = get_pas_opciones(conn, "pasm")
        botiquines_opciones = get_pas_opciones(conn, "avanzada")

        conn.close()
        for item in items_db:
            cat = item["categoria"]
            if cat not in checklist_items_by_cat:
                checklist_items_by_cat[cat] = []
            checklist_items_by_cat[cat].append(dict(item))

        return render_template(
            cfg["template"],
            usuario=session["usuario"],
            tipo=tipo,
            titulo=cfg["titulo"],
            subtitulo=cfg["subtitulo"],
            hoy=hoy().isoformat(),
            hora_actual=ahora().strftime("%H:%M"),
            checklist_items=checklist_items_by_cat,
            vehiculos=vehiculos,
            pasb_opciones=pasb_opciones,
            pasm_opciones=pasm_opciones,
            botiquines_opciones=botiquines_opciones,
            medicos=medicos,
            enfermeros=enfermeros,
            aphs=aphs,
            todos_usuarios=todos_usuarios,
            traslados_pendientes=traslados_pendientes,
            precargado_ultimo=locals().get("precargado_ultimo", False),
            record=record,
            datos=datos,
            placa_param=request.args.get("placa", "").strip()
        )


    @app.route("/checklist/<tipo>/aceptar_traslado/<int:traslado_id>", methods=["POST"])
    @app.route("/checklist/pasb/aceptar_traslado/<int:traslado_id>", methods=["POST"])
    @app.route("/checklist/pasm/aceptar_traslado/<int:traslado_id>", methods=["POST"])
    @login_required
    def aceptar_traslado_tipo(traslado_id, tipo="pasb"):
        conn = get_db()
        traslado = conn.execute("SELECT * FROM checklist_pasb_traslados WHERE id = ?", (traslado_id,)).fetchone()
        if not traslado:
            conn.close()
            return jsonify({"status": "error", "message": "Traslado no encontrado."}), 404
            
        now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
        user_name = session["usuario"]["nombre"]
        conn.execute(
            "UPDATE checklist_pasb_traslados SET estado = 'aceptado', aceptado_por = ?, fecha_aceptado = ? WHERE id = ?",
            (user_name, now_str, traslado_id)
        )
        conn.commit()
        
        tr_dict = dict(traslado)
        if tr_dict.get("fecha_vencimiento") and hasattr(tr_dict["fecha_vencimiento"], "strftime"):
            tr_dict["fecha_vencimiento"] = tr_dict["fecha_vencimiento"].strftime("%Y-%m-%d")
        elif tr_dict.get("fecha_vencimiento"):
            tr_dict["fecha_vencimiento"] = str(tr_dict["fecha_vencimiento"])
            
        conn.close()
        return jsonify({"status": "success", "message": f"Artículo '{traslado['nombre']}' aceptado correctamente.", "traslado": tr_dict})


    @app.route("/api/checklist/ultimo_datos")
    @login_required
    def api_checklist_ultimo_datos():
        tipo = request.args.get("tipo", "pasb")
        cfg = CHECKLIST_CONFIG.get(tipo)
        if not cfg:
            return jsonify({"status": "error", "message": "Tipo no válido"}), 400
            
        pasb_numero = request.args.get("pasb_numero")
        pasm_numero = request.args.get("pasm_numero")
        placa = request.args.get("placa")
        botiquin = request.args.get("botiquin")

        conn = get_db()
        try:
            row = None
            if tipo == "pasb":
                if pasb_numero:
                    row = conn.execute(
                        f"SELECT datos_json FROM {cfg['table']} WHERE pasb_numero = ? AND finalizado = 1 AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                        (pasb_numero,)
                    ).fetchone()
                    if not row:
                        row = conn.execute(
                            f"SELECT datos_json FROM {cfg['table']} WHERE pasb_numero = ? AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                            (pasb_numero,)
                        ).fetchone()
                else:
                    conn.close()
                    return jsonify({"status": "not_found", "datos": {}})
            elif tipo == "pasm":
                if pasm_numero:
                    row = conn.execute(
                        f"SELECT datos_json FROM {cfg['table']} WHERE pasm_numero = ? AND finalizado = 1 AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                        (pasm_numero,)
                    ).fetchone()
                    if not row:
                        row = conn.execute(
                            f"SELECT datos_json FROM {cfg['table']} WHERE pasm_numero = ? AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                            (pasm_numero,)
                        ).fetchone()
                else:
                    conn.close()
                    return jsonify({"status": "not_found", "datos": {}})
            elif tipo in ("tam", "tab"):
                if placa:
                    placa_clean = placa.strip()
                    row = conn.execute(
                        f"""SELECT datos_json FROM {cfg['table']} 
                            WHERE (UPPER(TRIM(placa)) = UPPER(TRIM(?)) 
                                   OR UPPER(REPLACE(REPLACE(TRIM(placa), '-', ''), ' ', '')) = UPPER(REPLACE(REPLACE(TRIM(?), '-', ''), ' ', '')))
                              AND finalizado = 1 
                              AND datos_json IS NOT NULL 
                              AND datos_json != '' 
                            ORDER BY id DESC LIMIT 1""",
                        (placa_clean, placa_clean)
                    ).fetchone()
                else:
                    conn.close()
                    return jsonify({"status": "not_found", "datos": {}})
            elif tipo == "avanzada":
                if botiquin:
                    row = conn.execute(
                        f"SELECT datos_json FROM checklist_avanzada WHERE botiquin = ? AND finalizado = 1 AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                        (botiquin,)
                    ).fetchone()
                    if not row:
                        row = conn.execute(
                            f"SELECT datos_json FROM checklist_avanzada WHERE botiquin = ? AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1",
                            (botiquin,)
                        ).fetchone()
                else:
                    conn.close()
                    return jsonify({"status": "not_found", "datos": {}})
            else:
                row = conn.execute(
                    f"SELECT datos_json FROM {cfg['table']} WHERE finalizado = 1 AND datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if not row:
                    row = conn.execute(
                        f"SELECT datos_json FROM {cfg['table']} WHERE datos_json IS NOT NULL AND datos_json != '' ORDER BY id DESC LIMIT 1"
                    ).fetchone()
            
            if row and row.get("datos_json"):
                datos_obj = json.loads(row["datos_json"])
                conn.close()
                return jsonify({"status": "success", "datos": datos_obj})
            conn.close()
            return jsonify({"status": "not_found", "datos": {}})
        except Exception as e:
            conn.close()
            return jsonify({"status": "error", "message": str(e)}), 500


    @app.route("/formularios/checklist/<tipo>/registros")
    @login_required
    def registros_checklist(tipo):
        cfg = CHECKLIST_CONFIG.get(tipo)
        if not cfg:
            return redirect(url_for("formulario"))
        conn = get_db()
        from datetime import date
        fecha_hoy = hoy().strftime('%Y-%m-%d')
        fecha_filtro = request.args.get("fecha", fecha_hoy)
        fecha_like = f"{fecha_filtro}%"
        
        is_admin = session.get("usuario", {}).get("rol") == "admin"
        user_ident = session.get("usuario", {}).get("identificacion")

        if tipo in ("pasb", "pasm", "tam", "tab", "avanzada"):
            # Para PASB, PASM, TAM, TAB y Avanzada cada usuario solo visualiza los que él mismo almacenó
            items = conn.execute(
                f"SELECT * FROM {cfg['table']} WHERE fecha_registro LIKE ? AND registrado_por_identificacion = ? ORDER BY id DESC",
                (fecha_like, user_ident)
            ).fetchall()
        elif not is_admin:
            items = conn.execute(
                f"SELECT * FROM {cfg['table']} WHERE fecha_registro LIKE ? AND registrado_por_identificacion = ? ORDER BY id DESC",
                (fecha_like, user_ident)
            ).fetchall()
        else:
            items = conn.execute(
                f"SELECT * FROM {cfg['table']} WHERE fecha_registro LIKE ? ORDER BY id DESC",
                (fecha_like,)
            ).fetchall()
        conn.close()
        return render_template("registros_formulario.html", items=items,
                               tipo=tipo, titulo=cfg["titulo"],
                               usuario=session["usuario"], fecha_filtro=fecha_filtro)


    @app.route("/formularios/checklist/<tipo>/<int:record_id>")
    @login_required
    def ver_checklist(tipo, record_id):
        cfg = CHECKLIST_CONFIG.get(tipo)
        if not cfg or tipo not in ("tam", "tab", "pasb", "pasm", "equipos", "calif_atencion", "segur_paciente", "avanzada"):
            flash("Tipo de checklist no válido.", "error")
            return redirect(url_for("dashboard"))
        conn = get_db()
        record = conn.execute(f"SELECT * FROM {cfg['table']} WHERE id = ?", (record_id,)).fetchone()
        if not record:
            conn.close()
            flash("Registro no encontrado.", "error")
            return redirect(url_for("registros_checklist", tipo=tipo))
        record_dict = dict(record)
        # Parse JSON data
        datos = {}
        if record_dict.get("datos_json"):
            try:
                datos = json.loads(record_dict["datos_json"])
            except Exception:
                pass

        for field, info in datos.items():
            if isinstance(info, dict):
                fv = info.get("fecha_vencimiento")
                if isinstance(fv, str) and fv.strip().startswith("["):
                    try:
                        fv = json.loads(fv)
                    except Exception:
                        pass
                if isinstance(fv, list):
                    info["vencimiento_entries"] = fv
                elif fv:
                    info["vencimiento_entries"] = [{"cant": info.get("cantidad") or 1, "fecha": str(fv)}]
                else:
                    info["vencimiento_entries"] = []

        # Validar permisos para no administradores
        is_admin = session.get("usuario", {}).get("rol") == "admin"
        user_ident = str(session.get("usuario", {}).get("identificacion") or "")
        if not is_admin:
            is_creator = str(record_dict.get("registrado_por_identificacion") or "") == user_ident
            is_integrante = False
            for integ in (datos.get("_integrantes") or []):
                if str(integ.get("identificacion") or "").strip() == user_ident:
                    is_integrante = True
                    break
            if not is_creator and not is_integrante:
                conn.close()
                flash("No tienes permiso para visualizar este registro.", "error")
                return redirect(url_for("registros_checklist", tipo=tipo))
                
        # Load checklist_items to preserve exact order
        items_db = conn.execute(
            "SELECT * FROM checklist_items WHERE tipo_checklist = ? ORDER BY categoria, id",
            (tipo,)
        ).fetchall()
        checklist_items_by_cat = {}
        for item in items_db:
            cat = item["categoria"]
            if cat not in checklist_items_by_cat:
                checklist_items_by_cat[cat] = []
            checklist_items_by_cat[cat].append(dict(item))
                
        # Get institution config
        from app import _load_config
        cfg_inst = _load_config()

        conn.close()
        return render_template("ver_checklist.html",
                               record=record_dict, datos=datos, tipo=tipo,
                               checklist_items=checklist_items_by_cat,
                               titulo=cfg["titulo"], subtitulo=cfg["subtitulo"],
                               cfg=cfg_inst,
                               usuario=session["usuario"])

