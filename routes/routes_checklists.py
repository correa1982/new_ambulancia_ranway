import json
import os
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
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
                datos[item["identificador"]] = {
                    "nombre": item["nombre"],
                    "categoria": item["categoria"],
                    "cantidad": item.get("cantidad"),
                    "valor": val,
                    "observacion": obs
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
            usuarios_db = conn.execute(
                "SELECT nombre, identificacion, perfil FROM usuarios WHERE activo = 1 AND (fecha_validez IS NULL OR fecha_validez >= CURDATE()) ORDER BY nombre"
            ).fetchall()
            todos_usuarios = [dict(u) for u in usuarios_db]

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
            pasb_opciones=PASB_OPCIONES,
            pasm_opciones=PASM_OPCIONES,
            medicos=medicos,
            enfermeros=enfermeros,
            aphs=aphs,
            todos_usuarios=todos_usuarios,
            record=record,
            datos=datos
        )


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
        
        items = conn.execute(f"SELECT * FROM {cfg['table']} WHERE fecha_registro LIKE ? ORDER BY id DESC", (fecha_like,)).fetchall()
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

