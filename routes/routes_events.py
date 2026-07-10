import json
import os
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from utils import login_required, admin_required, calcular_edad, get_user_info, ahora, hoy
# _load_config imported lazily inside functions to avoid circular import
from itsdangerous import URLSafeSerializer, BadSignature
from constants import REQUIRED_PATIENT_FIELDS

def register_routes(app):
    @login_required
    @app.route("/atencion_colectiva/ver/<int:id>")
    def ver_atencion_colectiva(id):
        conn = get_db()
        evento = conn.execute("SELECT * FROM atencion_colectiva WHERE id = ?", (id,)).fetchone()
        
        if not evento:
            conn.close()
            flash("Registro de atención colectiva no encontrado.", "error")
            return redirect(url_for("registros_atencion_colectiva"))
            
        pacientes = conn.execute(
            "SELECT COUNT(*) as count FROM pacientes WHERE atencion_colectiva_id = ?", 
            (id,)
        ).fetchone()["count"]
        
        conn.close()
        from app import _load_config
        return render_template("ver_atencion_colectiva.html", evento=evento, cfg=_load_config(), num_pacientes=pacientes)


    # ── Vistas Generales de Registros (Formularios Adicionales) ────────────────────────────────────────────────




    # ── Formulario Eventos ──────────────────────────────────────────────────────────
    @app.route("/formularios/eventos", methods=["GET", "POST"])
    @login_required
    def form_eventos():
        if request.method == "POST":
            data = request.form
            conn = get_db()
            firma, perfil, rm = get_user_info(conn, session["usuario"]["identificacion"])
            conn.execute("""
                INSERT INTO eventos (
                    fecha_inicio, hora_inicio, fecha_finalizacion, hora_finalizacion,
                    tipo_evento, direccion, municipio, num_afectados,
                    recursos_activados, observaciones,
                    firma_coordinador_evento,
                    registrado_por, registrado_por_identificacion,
                    perfil_registrador, registro_medico_registrador, firma_registrador, fecha_registro
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("fecha_inicio"), data.get("hora_inicio"),
                data.get("fecha_finalizacion"), data.get("hora_finalizacion"),
                data.get("tipo_evento"), data.get("direccion"), data.get("municipio"),
                data.get("num_afectados"),
                data.get("recursos_activados"), data.get("observaciones"),
                data.get("firma_coordinador_evento"),
                session["usuario"]["nombre"], session["usuario"]["identificacion"],
                perfil, rm, firma, ahora().strftime("%Y-%m-%d %H:%M:%S")
            ))
            conn.commit()
            conn.close()
            flash("Formulario de Eventos guardado correctamente.", "success")
            return redirect(url_for("registros_eventos"))
        conn = get_db()
        firma, _, _ = get_user_info(conn, session["usuario"]["identificacion"])
        vehiculos = conn.execute("SELECT placa, tipo, tipo_ambulancia FROM vehiculos WHERE activo = 1 ORDER BY tipo, placa").fetchall()
        conn.close()
        return render_template("eventos.html", usuario=session["usuario"],
                               firma_usuario=firma,
                               vehiculos=vehiculos,
                               hoy=hoy().isoformat())


    @app.route("/formularios/eventos/registros")
    @login_required
    def registros_eventos():
        conn = get_db()
        from datetime import date
        fecha_hoy = hoy().strftime('%Y-%m-%d')
        fecha_filtro = request.args.get("fecha", fecha_hoy)
        fecha_like = f"{fecha_filtro}%"
        
        items = conn.execute("SELECT * FROM eventos WHERE fecha_registro LIKE ? ORDER BY id DESC", (fecha_like,)).fetchall()
        conn.close()
        return render_template("registros_formulario.html", items=items,
                               tipo="eventos", titulo="Formulario Eventos",
                               usuario=session["usuario"], fecha_filtro=fecha_filtro)


    @app.route("/formularios/eventos/ver/<int:evento_id>")
    @login_required
    def ver_evento(evento_id):
        conn = get_db()
        evento = conn.execute("SELECT * FROM eventos WHERE id = ?", (evento_id,)).fetchone()
        if not evento:
            flash("Evento no encontrado.", "error")
            conn.close()
            return redirect(url_for("registros_eventos"))
        conn.close()
        from app import _load_config
        return render_template("ver_evento.html", evento=evento, cfg=_load_config(),
                               usuario=session["usuario"])




    # ── Atención Colectiva ──────────────────────────────────────────────────────────
    @app.route("/formularios/atencion-colectiva", methods=["GET", "POST"])
    @login_required
    def form_atencion_colectiva():
        conn = get_db()
        if request.method == "POST":
            data = request.form
            firma, perfil, rm = get_user_info(conn, session["usuario"]["identificacion"])
            cursor = conn.execute("""
                INSERT INTO atencion_colectiva (
                    fecha_inicio, hora_inicio, fecha_finalizacion, hora_finalizacion,
                    lugar, tipo_incidente,
                    recursos_desplegados, coordinador, observaciones,
                    registrado_por, registrado_por_identificacion,
                    perfil_registrador, registro_medico_registrador, firma_registrador, fecha_registro
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("fecha_inicio"), data.get("hora_inicio"),
                data.get("fecha_finalizacion"), data.get("hora_finalizacion"),
                data.get("lugar"), data.get("tipo_incidente"),
                data.get("recursos_desplegados"),
                data.get("coordinador"), data.get("observaciones"),
                session["usuario"]["nombre"], session["usuario"]["identificacion"],
                perfil, rm, firma, ahora().strftime("%Y-%m-%d %H:%M:%S")
            ))
            saved_id = cursor.lastrowid
            conn.commit()
            conn.close()
            flash("Registro de Atención Colectiva guardado correctamente. Registre los pacientes a continuación.", "success")
            return redirect(url_for("formulario_mci", atencion_colectiva_id=saved_id))

        saved_id = request.args.get("saved_id")
        # Pass list of active users for coordinator dropdown
        usuarios_db = conn.execute(
            "SELECT nombre, identificacion, perfil FROM usuarios WHERE activo = 1 AND (fecha_validez IS NULL OR fecha_validez >= CURDATE()) ORDER BY nombre"
        ).fetchall()
        
        usuarios = []
        for u in usuarios_db:
            u_dict = dict(u)
            if u_dict.get("perfil"):
                try:
                    perfiles = json.loads(u_dict["perfil"])
                    if isinstance(perfiles, list):
                        u_dict["perfil"] = ", ".join(perfiles)
                except Exception:
                    pass
            usuarios.append(u_dict)
        vehiculos = conn.execute("SELECT placa, tipo, tipo_ambulancia FROM vehiculos WHERE activo = 1 ORDER BY tipo, placa").fetchall()
        conn.close()
        return render_template("atencion_colectiva.html", usuario=session["usuario"],
                                hoy=hoy().isoformat(), usuarios=usuarios, saved_id=saved_id,
                                vehiculos=vehiculos)


    @app.route("/formularios/atencion-colectiva/registros")
    @login_required
    def registros_atencion_colectiva():
        conn = get_db()
        from datetime import date
        fecha_hoy = hoy().strftime('%Y-%m-%d')
        fecha_filtro = request.args.get("fecha", fecha_hoy)
        fecha_like = f"{fecha_filtro}%"
        
        is_admin = (session["usuario"]["rol"] == "admin")
        user_ident = session["usuario"]["identificacion"]
        user_perfil = session["usuario"].get("perfil", "")
        
        base_where = "ac.fecha_registro LIKE ?"
        params = [fecha_like]
        
        if not is_admin:
            base_where += " AND ac.registrado_por_identificacion = ? AND ac.perfil_registrador = ?"
            params.extend([user_ident, user_perfil])
            
        items = conn.execute(f"""
            SELECT ac.*, COUNT(p.id) as num_pacientes
            FROM atencion_colectiva ac
            LEFT JOIN pacientes p ON p.atencion_colectiva_id = ac.id
            WHERE {base_where}
            GROUP BY ac.id
            ORDER BY ac.id DESC
        """, tuple(params)).fetchall()
        conn.close()
        return render_template("registros_formulario.html", items=items,
                               tipo="atencion_colectiva", titulo="Atención Colectiva",
                               usuario=session["usuario"], fecha_filtro=fecha_filtro)


    # ── API: Validar y Finalizar Evento Masivo ──────────────────────────────────────

    @app.route("/formularios/atencion-colectiva/<int:ac_id>/finalizar", methods=["POST"])
    @login_required
    def finalizar_atencion_colectiva(ac_id):
        """Validates all patients of a collective event and (optionally) finalizes it.

        When the request header 'X-Validate-Only' is present, only validates and
        returns errors or a success count without writing to the database.
        Without that header, it performs the actual finalization.
        """
        validate_only = request.headers.get("X-Validate-Only") == "1"
        conn = get_db()

        ac = conn.execute(
            "SELECT * FROM atencion_colectiva WHERE id = ?", (ac_id,)
        ).fetchone()
        if not ac:
            conn.close()
            return jsonify({"ok": False, "error": "Evento no encontrado."}), 404

        if ac["finalizado"] == 1:
            conn.close()
            return jsonify({"ok": False, "error": "Este evento ya fue finalizado anteriormente."}), 400

        pacientes = conn.execute(
            "SELECT * FROM pacientes WHERE atencion_colectiva_id = ? ORDER BY id ASC", (ac_id,)
        ).fetchall()

        if not pacientes:
            conn.close()
            return jsonify({"ok": False, "error": "No hay pacientes registrados en este evento."}), 400

        # Validate each patient's required fields
        errors_by_patient = []
        serializer = URLSafeSerializer(app.secret_key)
        for idx, p in enumerate(pacientes):
            nombre = (
                f"{p['primer_nombre'] or ''} {p['primer_apellido'] or ''}".strip()
                or f"Paciente #{idx + 1}"
            )
            missing = []
            for field, label in REQUIRED_PATIENT_FIELDS:
                val = p[field]
                if not val or (isinstance(val, str) and not val.strip()):
                    missing.append(label)
            if missing:
                errors_by_patient.append({
                    "paciente_id": p["id"],
                    "paciente_id_encoded": serializer.dumps(p["id"]),
                    "nombre": nombre,
                    "identificacion": p["identificacion_paciente"] or "—",
                    "campos_faltantes": missing
                })

        if errors_by_patient:
            conn.close()
            return jsonify({"ok": False, "errores": errors_by_patient}), 422

        # Validation passed
        if validate_only:
            # Just report back that everything is valid + patient count
            conn.close()
            return jsonify({"ok": True, "num_pacientes": len(pacientes)})

        # Actually finalize: mark all patients and the event as finished
        now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE pacientes SET finalizado = 1, fecha_finalizacion_registro = ? WHERE atencion_colectiva_id = ?",
            (now_str, ac_id)
        )
        conn.execute(
            "UPDATE atencion_colectiva SET finalizado = 1 WHERE id = ?",
            (ac_id,)
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "redirect": url_for("registros", atencion_colectiva_id=ac_id)})

