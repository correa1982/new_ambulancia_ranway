import json
import os
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from utils import login_required, admin_required, calcular_edad, get_user_info, ahora, hoy
from itsdangerous import URLSafeSerializer, BadSignature
from constants import REQUIRED_PATIENT_FIELDS, PATIENT_FULL_FIELDS, PATIENT_MCI_FIELDS, EXAMEN_FISICO_KEYS

def _build_patient_sql(fields, for_insert=False):
    cols = ", ".join(fields)
    placeholders = ", ".join(["?"] * len(fields))
    if for_insert:
        return f"INSERT INTO pacientes ({cols}) VALUES ({placeholders})"
    cols_set = ", ".join(f"{f} = ?" for f in fields)
    return f"UPDATE pacientes SET {cols_set}"

def _patient_values(field_list, data, **overrides):
    special = {
        "identificacion_paciente": lambda d: d.get("identificacion_paciente", "").strip(),
        "tipo_documento": lambda d: d.get("tipo_documento", "").strip() or "CC",
        "primer_apellido": lambda d: d.get("primer_apellido", "").strip(),
        "primer_nombre": lambda d: d.get("primer_nombre", "").strip() or overrides.get("pnombre_default", ""),
        "segundo_apellido": lambda d: d.get("segundo_apellido", "").strip() or overrides.get("sapellido_default") or None,
        "segundo_nombre": lambda d: d.get("segundo_nombre", "").strip() or overrides.get("snombre_default") or None,
        "fecha_nacimiento": lambda d: d.get("fecha_nacimiento", "").strip(),
        "edad": lambda d: overrides.get("edad"),
        "registrado_por": lambda d: overrides["usuario_nombre"],
        "registrado_por_identificacion": lambda d: overrides["usuario_identificacion"],
        "registro_medico_registrador": lambda d: overrides.get("registro_medico", ""),
        "perfil_registrador": lambda d: overrides.get("perfil", ""),
        "firma_registrador": lambda d: overrides.get("firma", ""),
        "fecha_inicio_atencion": lambda d: overrides.get("fecha_inicio"),
        "fecha_finalizacion_registro": lambda d: overrides["now_str"] if overrides.get("finalizado") else None,
        "finalizado": lambda d: overrides.get("finalizado", 0),
        "atencion_colectiva_id": lambda d: overrides.get("atencion_colectiva_id"),
        "fecha_registro": lambda d: overrides["now_str"],
        "examen_fisico": lambda d: overrides.get("examen_fisico", ""),
        "datos_complementarios": lambda d: overrides.get("datos_complementarios", ""),
        "inmovilizacion": lambda d: ", ".join(d.getlist("inmovilizacion")) or None,
        "otros_procedimientos": lambda d: ", ".join(d.getlist("otros_procedimientos")) or None,
        "x_items": lambda d: ", ".join(d.getlist("x_items[]")) or None,
        "a_items": lambda d: ", ".join(d.getlist("a_items[]")) or None,
        "b_items": lambda d: ", ".join(d.getlist("b_items[]")) or None,
        "c_items": lambda d: ", ".join(d.getlist("c_items[]")) or None,
        "d_items": lambda d: ", ".join(d.getlist("d_items[]")) or None,
        "e_items": lambda d: ", ".join(d.getlist("e_items[]")) or None,
    }
    return [special.get(f, lambda d: d.get(f, "").strip() or None)(data) for f in field_list]


def register_routes(app, serializer, TIPOS_DOCUMENTO, TIPOS_AFILIACION, ASEGURADORAS):
    @app.route("/formulario", methods=["GET", "POST"])
    @login_required
    def formulario():
        if request.method == "POST":
            data = request.form
            fecha_nacimiento = data.get("fecha_nacimiento")
            edad = calcular_edad(fecha_nacimiento) if fecha_nacimiento else None
            fecha_inicio_atencion = data.get("fecha_inicio_atencion")
            atencion_colectiva_id = data.get("atencion_colectiva_id")
            if atencion_colectiva_id == "":
                atencion_colectiva_id = None

            accion = data.get("accion", "borrador")
            finalizado = 1 if accion == "finalizar" else 0
            guardar_y_continuar = (accion == "guardar_continuar")
            
            paciente_id_raw = request.args.get("id") or data.get("id")
            paciente_id = None
            if paciente_id_raw:
                try:
                    paciente_id = int(serializer.loads(paciente_id_raw))
                except (BadSignature, ValueError, TypeError):
                    flash("Enlace de borrador inválido.", "error")
                    return redirect(url_for("registros"))

            conn = get_db()
            is_offline_sync = (data.get("_offline_sync") == "1")

            # Perform server-side validation only when finalizing
            errors = []
            if finalizado == 1:
                for field, label in REQUIRED_PATIENT_FIELDS:
                    if not data.get(field) or not data.get(field).strip():
                        errors.append(f"El campo '{label}' es obligatorio al finalizar.")

            if errors:
                if is_offline_sync:
                    conn.close()
                    from flask import jsonify
                    return jsonify({"status": "error", "errors": errors}), 400
                    
                for err in errors:
                    flash(err, "error")

                # Pre-fill patient structure for rendering inputs back
                paciente = {
                    "id": paciente_id,
                    "identificacion_paciente": data.get("identificacion_paciente"),
                    "tipo_documento": data.get("tipo_documento"),
                    "primer_apellido": data.get("primer_apellido"),
                    "segundo_apellido": data.get("segundo_apellido"),
                    "primer_nombre": data.get("primer_nombre"),
                    "segundo_nombre": data.get("segundo_nombre"),
                    "fecha_nacimiento": data.get("fecha_nacimiento"),
                    "edad": edad,
                    "telefono": data.get("telefono"),
                    "direccion": data.get("direccion"),
                    "tipo_afiliacion": data.get("tipo_afiliacion"),
                    "aseguradora": data.get("aseguradora"),
                    "motivo_consulta": data.get("motivo_consulta"),
                    "enfermedad_actual": data.get("enfermedad_actual"),
                    "analisis": data.get("analisis"),
                    "plan": data.get("plan"),
                    "sexo_biologico": data.get("sexo_biologico"),
                    "identidad_genero": data.get("identidad_genero"),
                    "estado_civil": data.get("estado_civil"),
                    "ocupacion": data.get("ocupacion"),
                    "nacionalidad": data.get("nacionalidad"),
                    "correo_electronico": data.get("correo_electronico"),
                    "departamento_residencia": data.get("departamento_residencia"),
                    "municipio_residencia": data.get("municipio_residencia"),
                    "barrio_residencia": data.get("barrio_residencia"),
                    "pertenencia_etnica": data.get("pertenencia_etnica"),
                    "discapacidad": data.get("discapacidad"),
                    "habitante_calle": data.get("habitante_calle"),
                    "aplica_acompanante": data.get("aplica_acompanante"),
                    "acompanante_nombre": data.get("acompanante_nombre"),
                    "acompanante_tipo_doc": data.get("acompanante_tipo_doc"),
                    "acompanante_doc": data.get("acompanante_doc"),
                    "acompanante_telefono": data.get("acompanante_telefono"),
                    "acompanante_parentesco": data.get("acompanante_parentesco"),
                    "aplica_responsable": data.get("aplica_responsable"),
                    "responsable_nombre": data.get("responsable_nombre"),
                    "responsable_tipo_doc": data.get("responsable_tipo_doc"),
                    "responsable_doc": data.get("responsable_doc"),
                    "responsable_telefono": data.get("responsable_telefono"),
                    "responsable_parentesco": data.get("responsable_parentesco"),
                    "antecedentes_personales": data.get("antecedentes_personales"),
                    "antecedentes_quirurgicos": data.get("antecedentes_quirurgicos"),
                    "antecedentes_toxicologicos": data.get("antecedentes_toxicologicos"),
                    "antecedentes_alergicos": data.get("antecedentes_alergicos"),
                    "antecedentes_ginecobstetricos": data.get("antecedentes_ginecobstetricos"),
                    "medicamentos_actuales": data.get("medicamentos_actuales"),
                    "otros_antecedentes": data.get("otros_antecedentes"),
                    "antecedentes_familiares": data.get("antecedentes_familiares"),
                    "presion_arterial": data.get("presion_arterial"),
                    "saturacion_oxigeno": data.get("saturacion_oxigeno"),
                    "frecuencia_cardiaca": data.get("frecuencia_cardiaca"),
                    "frecuencia_respiratoria": data.get("frecuencia_respiratoria"),
                    "glicemia": data.get("glicemia"),
                    "diagnostico_cie10": data.get("diagnostico_cie10"),
                    "atencion_colectiva_id": atencion_colectiva_id,
                    "finalizado": 0,
                    "primer_respondiente": data.get("primer_respondiente"),
                    "es_emergencia_medica": data.get("es_emergencia_medica"),
                    "detalle_emergencia_medica": data.get("detalle_emergencia_medica"),
                    "es_emergencia_traumatica": data.get("es_emergencia_traumatica"),
                    "detalle_emergencia_traumatica": data.get("detalle_emergencia_traumatica"),
                    "triage_fecha_hora": data.get("triage_fecha_hora"),
                    "triage_clasificacion": data.get("triage_clasificacion"),
                    "glasgow_ocular": data.get("glasgow_ocular"),
                    "glasgow_verbal": data.get("glasgow_verbal"),
                    "glasgow_motora": data.get("glasgow_motora"),
                    "glasgow_total": data.get("glasgow_total"),
                    "estado_consciencia": data.get("estado_consciencia"),
                    "cincinnati_facial": data.get("cincinnati_facial"),
                    "cincinnati_brazo": data.get("cincinnati_brazo"),
                    "cincinnati_habla": data.get("cincinnati_habla"),
                    "cincinnati_total": data.get("cincinnati_total"),
                    "rts_total": data.get("rts_total"),
                    "evaluacion_inicial": data.get("evaluacion_inicial"),
                    "examen_fisico": data.get("examen_fisico"),
                    "soat_aseguradora": data.get("soat_aseguradora"),
                    "soat_vigencia": data.get("soat_vigencia"),
                    "hora_despacho": data.get("hora_despacho"),
                    "hora_arribo": data.get("hora_arribo"),
                    "nombre_evento": data.get("nombre_evento"),
                    "tipo_servicio": data.get("tipo_servicio"),
                    "departamento": data.get("departamento"),
                    "municipio": data.get("municipio"),
                    "barrio": data.get("barrio"),
                    "direccion_atencion": data.get("direccion_atencion"),
                    "ambito_territorial": data.get("ambito_territorial"),
                    "entorno_atencion": data.get("entorno_atencion"),
                    "clasificacion": data.get("clasificacion"),
                    "causa_motiva_atencion": data.get("causa_motiva_atencion"),
                    "tipo_traslado": data.get("tipo_traslado"),
                    "entorno_otro": data.get("entorno_otro"),
                    "inmovilizacion": ", ".join(data.getlist("inmovilizacion")),
                    "otros_procedimientos": ", ".join(data.getlist("otros_procedimientos")),
                    "ventilacion_mecanica": data.get("ventilacion_mecanica"),
                    "torniquete": data.get("torniquete"),
                    "x_items": ", ".join(data.getlist("x_items[]")),
                    "a_items": ", ".join(data.getlist("a_items[]")),
                    "b_items": ", ".join(data.getlist("b_items[]")),
                    "c_items": ", ".join(data.getlist("c_items[]")),
                    "d_items": ", ".join(data.getlist("d_items[]")),
                    "e_items": ", ".join(data.getlist("e_items[]")),
                    "examen_fisico_obj": {k: {"estado": data.get(f"ef_{k}", ""), "obs": data.get(f"ef_{k}_obs", "")} for k in ["cabeza", "ojos", "nariz", "oidos", "boca", "cuello", "torax", "cardio", "pulmonar", "abdomen", "pelvis", "piel", "genito_urinario", "extremidades", "osteomuscular", "vascular_periferico", "neurologico", "estado_mental"]},
                }

                atencion_colectiva = None
                evento_pacientes = []
                if atencion_colectiva_id:
                    atencion_colectiva = conn.execute(
                        "SELECT * FROM atencion_colectiva WHERE id = ?", (atencion_colectiva_id,)
                    ).fetchone()
                    evento_pacientes = conn.execute(
                        "SELECT * FROM pacientes WHERE atencion_colectiva_id = ? ORDER BY id DESC",
                        (atencion_colectiva_id,)
                    ).fetchall()
                    
                cursor = conn.execute("SELECT nombre FROM aseguradoras WHERE activo = 1 ORDER BY nombre")
                aseguradoras_list = [row["nombre"] for row in cursor.fetchall()]
                p_aseg = data.get("aseguradora")
                if p_aseg and p_aseg not in aseguradoras_list:
                    aseguradoras_list.append(p_aseg)

                soat_cursor = conn.execute("SELECT nombre FROM aseguradoras_soat WHERE activo = 1 ORDER BY nombre")
                aseguradoras_soat_list = [row["nombre"] for row in soat_cursor.fetchall()]
                    
                conn.close()

                return render_template(
                    "formulario.html",
                    usuario=session["usuario"],
                    tipos_documento=TIPOS_DOCUMENTO,
                    tipos_afiliacion=TIPOS_AFILIACION,
                    aseguradoras=aseguradoras_list,
                    aseguradoras_soat=aseguradoras_soat_list,
                    hoy=hoy().isoformat(),
                    fecha_inicio_atencion=fecha_inicio_atencion,
                    atencion_colectiva=atencion_colectiva,
                    atencion_colectiva_id=atencion_colectiva_id,
                    paciente=paciente,
                    evento_pacientes=evento_pacientes
                )

            user_info = conn.execute(
                "SELECT * FROM usuarios WHERE identificacion = ?",
                (session["usuario"]["identificacion"],)
            ).fetchone()
            
            firma_registrador = user_info["firma"] if user_info else ""
            perfil_registrador = session["usuario"].get("perfil", "") if "usuario" in session else ""
            registro_medico_registrador = user_info["registro_medico"] if user_info else ""

            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")

            examen_fisico_dict = {k: {"estado": data.get(f"ef_{k}", ""), "obs": data.get(f"ef_{k}_obs", "")} for k in EXAMEN_FISICO_KEYS}
            db_examen_fisico = json.dumps(examen_fisico_dict, ensure_ascii=False)

            standard_keys = {
                "identificacion_paciente", "tipo_documento", "primer_apellido", "segundo_apellido",
                "primer_nombre", "segundo_nombre", "fecha_nacimiento", "edad", "telefono", "direccion",
                "tipo_afiliacion", "aseguradora", "motivo_consulta", "enfermedad_actual", "analisis", "plan",
                "sexo_biologico", "identidad_genero", "estado_civil", "ocupacion", "nacionalidad", "correo_electronico", "departamento_residencia", "municipio_residencia", "barrio_residencia", "antecedentes_personales", "antecedentes_quirurgicos", "antecedentes_toxicologicos", "antecedentes_alergicos", "antecedentes_ginecobstetricos", "medicamentos_actuales", "otros_antecedentes", "antecedentes_familiares",
                "presion_arterial", "saturacion_oxigeno", "frecuencia_cardiaca", "frecuencia_respiratoria", "glicemia", "dolor",
                "diagnostico_cie10", "pertenencia_etnica", "discapacidad", "habitante_calle",
                "aplica_acompanante", "acompanante_nombre", "acompanante_tipo_doc", "acompanante_doc", "acompanante_telefono", "acompanante_parentesco",
                "aplica_responsable", "responsable_nombre", "responsable_tipo_doc", "responsable_doc", "responsable_telefono", "responsable_parentesco",
                "primer_respondiente", "es_emergencia_medica", "detalle_emergencia_medica", "es_emergencia_traumatica", "detalle_emergencia_traumatica",
                "triage_fecha_hora", "triage_clasificacion",
                "glasgow_ocular", "glasgow_verbal", "glasgow_motora", "glasgow_total",
                "estado_consciencia", "cincinnati_facial", "cincinnati_brazo", "cincinnati_habla", "cincinnati_total", "rts_total",
                "accion", "id", "atencion_colectiva_id", "_offline_sync", "fecha_inicio_atencion",
                "soat_aseguradora", "soat_vigencia"
            }
            
            complementarios = {}
            for k in data.keys():
                if k not in standard_keys and not k.startswith("ef_"):
                    # Check if it has multiple values (e.g. array checkboxes)
                    val_list = data.getlist(k)
                    clean_k = k[:-2] if k.endswith("[]") else k
                    if len(val_list) > 1 or k.endswith("[]"):
                        complementarios[clean_k] = val_list
                    else:
                        complementarios[clean_k] = val_list[0]
            db_datos_complementarios = json.dumps(complementarios, ensure_ascii=False)

            full_update_fields = [f for f in PATIENT_FULL_FIELDS if f != "atencion_colectiva_id"]

            if paciente_id:
                conn.execute(
                    _build_patient_sql(full_update_fields) + " WHERE id = ?",
                    _patient_values(full_update_fields, data,
                        usuario_nombre=session["usuario"]["nombre"],
                        usuario_identificacion=session["usuario"]["identificacion"],
                        registro_medico=registro_medico_registrador,
                        perfil=perfil_registrador, firma=firma_registrador,
                        fecha_inicio=fecha_inicio_atencion,
                        now_str=now_str, finalizado=finalizado, edad=edad,
                        examen_fisico=db_examen_fisico,
                        datos_complementarios=db_datos_complementarios,
                    ) + [paciente_id]
                )
            else:
                full_insert_fields = PATIENT_FULL_FIELDS[:]
                reg_idx = full_insert_fields.index("registrado_por") + 1
                full_insert_fields.insert(reg_idx, "fecha_registro")
                cursor = conn.execute(
                    _build_patient_sql(full_insert_fields, for_insert=True),
                    _patient_values(full_insert_fields, data,
                        usuario_nombre=session["usuario"]["nombre"],
                        usuario_identificacion=session["usuario"]["identificacion"],
                        registro_medico=registro_medico_registrador,
                        perfil=perfil_registrador, firma=firma_registrador,
                        fecha_inicio=fecha_inicio_atencion,
                        now_str=now_str, finalizado=finalizado, edad=edad,
                        atencion_colectiva_id=atencion_colectiva_id,
                        examen_fisico=db_examen_fisico,
                        datos_complementarios=db_datos_complementarios,
                    )
                )
                paciente_id = cursor.lastrowid
            conn.commit()
            conn.close()

            if is_offline_sync:
                from flask import jsonify
                return jsonify({"status": "success"}), 200

            if finalizado == 1:
                flash("Historia Clínica finalizada y guardada correctamente.", "success")
                if atencion_colectiva_id:
                    # After finalizing a colectiva patient, go back to the colectiva panel (new patient form)
                    return redirect(url_for("formulario_mci", atencion_colectiva_id=atencion_colectiva_id))
                return redirect(url_for("registros"))
            elif guardar_y_continuar and atencion_colectiva_id:
                flash("Registro guardado. Complete la información cuando pueda. Registre el siguiente paciente.", "success")
                # Redirect to blank new form for next patient in this same colectiva event
                return redirect(url_for("formulario_mci", atencion_colectiva_id=atencion_colectiva_id))
            else:
                flash("Borrador guardado. Puede continuar editando este registro o ir al dashboard.", "success")
                if atencion_colectiva_id:
                    return redirect(url_for("formulario_mci", atencion_colectiva_id=atencion_colectiva_id, id=serializer.dumps(paciente_id)))
                return redirect(url_for("formulario", id=serializer.dumps(paciente_id)))

        # Capture start time of the attention session
        fecha_inicio_atencion = ahora().strftime("%Y-%m-%d %H:%M:%S")

        atencion_colectiva_id = request.args.get("atencion_colectiva_id")
        paciente_id_raw = request.args.get("id")
        
        # If atencion_colectiva_id is passed directly in the query parameters, redirect to formulario_mci
        if atencion_colectiva_id:
            return redirect(url_for("formulario_mci", atencion_colectiva_id=atencion_colectiva_id, id=paciente_id_raw))
            
        paciente_id = None
        if paciente_id_raw:
            try:
                paciente_id = int(serializer.loads(paciente_id_raw))
            except (BadSignature, ValueError, TypeError):
                flash("Enlace de borrador inválido.", "error")
                return redirect(url_for("registros"))
                
        paciente = None
        
        conn = get_db()
        if paciente_id:
            paciente = conn.execute("SELECT * FROM pacientes WHERE id = ?", (paciente_id,)).fetchone()
            if paciente:

                if paciente.get("examen_fisico"):
                    try:
                        paciente["examen_fisico_obj"] = json.loads(paciente["examen_fisico"])
                    except:
                        paciente["examen_fisico_obj"] = {}
                else:
                    paciente["examen_fisico_obj"] = {}
                    
                if paciente.get("datos_complementarios"):
                    try:
                        complementarios = json.loads(paciente["datos_complementarios"])
                        paciente.update(complementarios)
                    except:
                        pass
            if paciente:
                if session["usuario"]["rol"] != "admin" and str(paciente.get("registrado_por_identificacion")) != str(session["usuario"]["identificacion"]):
                    conn.close()
                    flash("Acceso denegado. No puede editar registros de otros usuarios.", "error")
                    return redirect(url_for("registros"))
                if paciente.get("finalizado") == 1:
                    conn.close()
                    flash("Esta historia clínica ya ha sido finalizada y no puede ser modificada.", "error")
                    return redirect(url_for("ver_hc", token=serializer.dumps(paciente.get("id"))))
                atencion_colectiva_id = paciente.get("atencion_colectiva_id")
                fecha_inicio_atencion = paciente.get("fecha_inicio_atencion")
                # If loaded patient has atencion_colectiva_id, redirect to formulario_mci
                if atencion_colectiva_id:
                    conn.close()
                    return redirect(url_for("formulario_mci", atencion_colectiva_id=atencion_colectiva_id, id=paciente_id_raw))

        atencion_colectiva = None
        evento_pacientes = []
        if atencion_colectiva_id:
            atencion_colectiva = conn.execute(
                "SELECT * FROM atencion_colectiva WHERE id = ?", (atencion_colectiva_id,)
            ).fetchone()
            # Block access if the collective event is already finalized
            if atencion_colectiva and atencion_colectiva["finalizado"] == 1:
                conn.close()
                flash("Este evento de Atención Colectiva ya fue finalizado. Las historias clínicas no pueden ser modificadas.", "error")
                return redirect(url_for("registros", atencion_colectiva_id=atencion_colectiva_id))
            evento_pacientes = conn.execute(
                "SELECT * FROM pacientes WHERE atencion_colectiva_id = ? ORDER BY id DESC",
                (atencion_colectiva_id,)
            ).fetchall()

        cursor = conn.execute("SELECT nombre FROM aseguradoras WHERE activo = 1 ORDER BY nombre")
        aseguradoras_list = [row["nombre"] for row in cursor.fetchall()]
        if paciente and paciente.get("aseguradora") and paciente.get("aseguradora") not in aseguradoras_list:
            aseguradoras_list.append(paciente.get("aseguradora"))

        soat_cursor = conn.execute("SELECT nombre FROM aseguradoras_soat WHERE activo = 1 ORDER BY nombre")
        aseguradoras_soat_list = [row["nombre"] for row in soat_cursor.fetchall()]
        p_soat = paciente.get("soat_aseguradora") if paciente else None
        if p_soat and p_soat not in aseguradoras_soat_list:
            aseguradoras_soat_list.append(p_soat)

        conn.close()

        return render_template(
            "formulario.html",
            usuario=session["usuario"],
            tipos_documento=TIPOS_DOCUMENTO,
            tipos_afiliacion=TIPOS_AFILIACION,
            aseguradoras=aseguradoras_list,
            aseguradoras_soat=aseguradoras_soat_list,
            hoy=hoy().isoformat(),
            fecha_inicio_atencion=fecha_inicio_atencion,
            atencion_colectiva=atencion_colectiva,
            atencion_colectiva_id=atencion_colectiva_id,
            paciente=paciente,
            evento_pacientes=evento_pacientes
        )


    @app.route("/formulario_mci", methods=["GET", "POST"])
    @login_required
    def formulario_mci():
        if request.method == "POST":
            data = request.form
            is_offline_sync = (data.get("_offline_sync") == "1")
            fecha_nacimiento = data.get("fecha_nacimiento")
            edad = data.get("edad")
            # If fecha_nacimiento is provided, calculate age from it
            if fecha_nacimiento:
                edad = calcular_edad(fecha_nacimiento)
            fecha_inicio_atencion = data.get("fecha_inicio_atencion")
            atencion_colectiva_id = data.get("atencion_colectiva_id")
            if atencion_colectiva_id == "":
                atencion_colectiva_id = None

            accion = data.get("accion", "guardar_continuar")
            finalizado = 1 if accion == "finalizar" else 0
            
            paciente_id_raw = request.args.get("id") or data.get("id")
            paciente_id = None
            if paciente_id_raw:
                try:
                    paciente_id = int(serializer.loads(paciente_id_raw))
                except (BadSignature, ValueError, TypeError):
                    flash("Enlace de paciente inválido.", "error")
                    return redirect(url_for("registros"))

            conn = get_db()
            
            user_info = conn.execute(
                "SELECT * FROM usuarios WHERE identificacion = ?",
                (session["usuario"]["identificacion"],)
            ).fetchone()
            
            firma_registrador = user_info["firma"] if user_info else ""
            perfil_registrador = session["usuario"].get("perfil", "") if "usuario" in session else ""
            registro_medico_registrador = user_info["registro_medico"] if user_info else ""

            now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")

            mci_update_fields = [f for f in PATIENT_MCI_FIELDS if f != "atencion_colectiva_id"]

            if paciente_id:
                conn.execute(
                    _build_patient_sql(mci_update_fields) + " WHERE id = ?",
                    _patient_values(mci_update_fields, data,
                        pnombre_default="NN",
                        usuario_nombre=session["usuario"]["nombre"],
                        usuario_identificacion=session["usuario"]["identificacion"],
                        registro_medico=registro_medico_registrador,
                        perfil=perfil_registrador, firma=firma_registrador,
                        fecha_inicio=fecha_inicio_atencion,
                        now_str=now_str, finalizado=finalizado, edad=edad,
                    ) + [paciente_id]
                )
            else:
                mci_insert_fields = PATIENT_MCI_FIELDS[:]
                reg_idx = mci_insert_fields.index("registrado_por") + 1
                mci_insert_fields.insert(reg_idx, "fecha_registro")
                conn.execute(
                    _build_patient_sql(mci_insert_fields, for_insert=True),
                    _patient_values(mci_insert_fields, data,
                        pnombre_default="NN",
                        usuario_nombre=session["usuario"]["nombre"],
                        usuario_identificacion=session["usuario"]["identificacion"],
                        registro_medico=registro_medico_registrador,
                        perfil=perfil_registrador, firma=firma_registrador,
                        fecha_inicio=fecha_inicio_atencion,
                        now_str=now_str, finalizado=finalizado, edad=edad,
                        atencion_colectiva_id=atencion_colectiva_id,
                    )
                )
            conn.commit()
            conn.close()

            if is_offline_sync:
                return jsonify({"status": "success", "message": "Sincronizado correctamente"})

            if finalizado == 1:
                flash("Paciente de Atención Colectiva finalizado.", "success")
                if atencion_colectiva_id:
                    return redirect(url_for("formulario_mci", atencion_colectiva_id=atencion_colectiva_id))
                return redirect(url_for("registros"))
            else:
                flash("Registro guardado. Puede registrar el siguiente paciente.", "success")
                if atencion_colectiva_id:
                    return redirect(url_for("formulario_mci", atencion_colectiva_id=atencion_colectiva_id))
                return redirect(url_for("registros"))

        fecha_inicio_atencion = ahora().strftime("%Y-%m-%d %H:%M:%S")

        atencion_colectiva_id = request.args.get("atencion_colectiva_id")
        paciente_id_raw = request.args.get("id")
        paciente_id = None
        if paciente_id_raw:
            try:
                paciente_id = int(serializer.loads(paciente_id_raw))
            except (BadSignature, ValueError, TypeError):
                flash("Enlace de paciente inválido.", "error")
                return redirect(url_for("registros"))
                
        paciente = None
        
        conn = get_db()
        if paciente_id:
            paciente = conn.execute("SELECT * FROM pacientes WHERE id = ?", (paciente_id,)).fetchone()
            if paciente:

                if paciente.get("examen_fisico"):
                    try:
                        paciente["examen_fisico_obj"] = json.loads(paciente["examen_fisico"])
                    except:
                        paciente["examen_fisico_obj"] = {}
                else:
                    paciente["examen_fisico_obj"] = {}
            if paciente:
                if session["usuario"]["rol"] != "admin" and str(paciente["registrado_por_identificacion"]) != str(session["usuario"]["identificacion"]):
                    conn.close()
                    flash("Acceso denegado. No puede editar registros de otros usuarios.", "error")
                    return redirect(url_for("registros"))
                if paciente["finalizado"] == 1:
                    conn.close()
                    flash("Esta historia clínica ya ha sido finalizada y no puede ser modificada.", "error")
                    return redirect(url_for("ver_hc", token=serializer.dumps(paciente["id"])))
                atencion_colectiva_id = paciente["atencion_colectiva_id"]
                fecha_inicio_atencion = paciente["fecha_inicio_atencion"]

        atencion_colectiva = None
        evento_pacientes = []
        counts = {"finalizados": 0, "borradores": 0, "total": 0}
        if atencion_colectiva_id:
            atencion_colectiva = conn.execute(
                "SELECT * FROM atencion_colectiva WHERE id = ?", (atencion_colectiva_id,)
            ).fetchone()
            if atencion_colectiva and atencion_colectiva["finalizado"] == 1:
                conn.close()
                flash("Este evento de Atención Colectiva ya fue finalizado. Las historias clínicas no pueden ser modificadas.", "error")
                return redirect(url_for("registros", atencion_colectiva_id=atencion_colectiva_id))
            evento_pacientes = conn.execute(
                "SELECT * FROM pacientes WHERE atencion_colectiva_id = ? ORDER BY id DESC",
                (atencion_colectiva_id,)
            ).fetchall()
            counts["total"] = len(evento_pacientes)
            counts["finalizados"] = sum(1 for p in evento_pacientes if p["finalizado"] == 1)
            counts["borradores"] = counts["total"] - counts["finalizados"]

        cursor = conn.execute("SELECT nombre FROM aseguradoras WHERE activo = 1 ORDER BY nombre")
        aseguradoras_list = [row["nombre"] for row in cursor.fetchall()]
        if paciente and paciente.get("aseguradora") and paciente.get("aseguradora") not in aseguradoras_list:
            aseguradoras_list.append(paciente.get("aseguradora"))

        conn.close()

        return render_template(
            "formulario_mci.html",
            usuario=session["usuario"],
            tipos_documento=TIPOS_DOCUMENTO,
            tipos_afiliacion=TIPOS_AFILIACION,
            aseguradoras=aseguradoras_list,
            hoy=hoy().isoformat(),
            fecha_inicio_atencion=fecha_inicio_atencion,
            atencion_colectiva=atencion_colectiva,
            atencion_colectiva_id=atencion_colectiva_id,
            paciente=paciente,
            evento_pacientes=evento_pacientes,
            counts=counts
        )

    @app.route("/formulario_mci/finalizar_todas", methods=["POST"])
    @login_required
    def finalizar_todas_mci():
        ac_id = request.form.get("atencion_colectiva_id")
        if not ac_id:
            flash("ID de atención colectiva inválido.", "error")
            return redirect(url_for("registros"))
            
        conn = get_db()
        now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
        
        # Finalizar todos los pacientes de esta atención colectiva
        conn.execute(
            "UPDATE pacientes SET finalizado = 1, fecha_finalizacion_registro = ? WHERE atencion_colectiva_id = ?",
            (now_str, ac_id)
        )
        
        # También podemos finalizar el evento en sí
        conn.execute(
            "UPDATE atencion_colectiva SET finalizado = 1 WHERE id = ?",
            (ac_id,)
        )
        conn.commit()
        conn.close()
        
        flash("Todas las historias clínicas de la Atención Colectiva han sido finalizadas exitosamente.", "success")
        return redirect(url_for("registros", atencion_colectiva_id=ac_id))

    @app.route("/calcular_edad")
    def calcular_edad_endpoint():
        fecha = request.args.get("fecha_nacimiento")
        try:
            edad = calcular_edad(fecha)
            return {"edad": edad}
        except Exception:
            return {"edad": ""}


    @app.route("/registros")
    @login_required
    def registros():
        conn = get_db()
        atencion_colectiva_id = request.args.get("atencion_colectiva_id")
        
        # Filtro de fecha (por defecto hoy)
        from datetime import date
        fecha_hoy = hoy().strftime('%Y-%m-%d')
        fecha_filtro = request.args.get("fecha", "")
        fecha_like = f"{fecha_filtro}%" if fecha_filtro else "%"
        
        search_query = request.args.get("search", "").strip()
        search_like = f"%{search_query}%" if search_query else None
        
        page = request.args.get("page", 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page

        atencion_colectiva = None
        is_admin = (session["usuario"]["rol"] == "admin")
        user_ident = session["usuario"]["identificacion"]
        
        user_perfil = session["usuario"].get("perfil", "")
        
        profesional_filtro = request.args.get("profesional", "")
        aseguradora_filtro = request.args.get("aseguradora", "")
        
        # Base query for patients
        base_sql = "FROM pacientes WHERE 1=1"
        params = []
        
        if atencion_colectiva_id:
            base_sql += " AND atencion_colectiva_id = ?"
            params.append(atencion_colectiva_id)
            
        if not is_admin:
            base_sql += " AND registrado_por_identificacion = ? AND perfil_registrador = ?"
            params.extend([user_ident, user_perfil])
        elif profesional_filtro:
            base_sql += " AND registrado_por_identificacion = ?"
            params.append(profesional_filtro)
            
        if aseguradora_filtro:
            base_sql += " AND aseguradora = ?"
            params.append(aseguradora_filtro)
            
        if fecha_filtro:
            base_sql += " AND fecha_registro LIKE ?"
            params.append(fecha_like)
            
        if search_like:
            base_sql += " AND (primer_nombre LIKE ? OR primer_apellido LIKE ? OR identificacion_paciente LIKE ?)"
            params.extend([search_like, search_like, search_like])
            
        # Count total records for pagination
        count_sql = f"SELECT COUNT(*) as total {base_sql}"
        total_records = conn.execute(count_sql, tuple(params)).fetchone()["total"]
        total_pages = (total_records + per_page - 1) // per_page
        
        # Fetch records
        fetch_sql = f"SELECT * {base_sql} ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([per_page, offset])
        pacientes = conn.execute(fetch_sql, tuple(params)).fetchall()

        if atencion_colectiva_id:
            atencion_colectiva = conn.execute(
                "SELECT * FROM atencion_colectiva WHERE id = ?", (atencion_colectiva_id,)
            ).fetchone()

        profesionales = []
        if is_admin:
            profesionales = conn.execute("SELECT identificacion, nombre FROM usuarios WHERE activo = 1 AND (fecha_validez IS NULL OR fecha_validez >= CURDATE()) ORDER BY nombre").fetchall()

        aseguradoras_db = conn.execute("SELECT nombre FROM aseguradoras WHERE activo = 1 ORDER BY nombre").fetchall()
        aseguradoras = [a["nombre"] for a in aseguradoras_db]

        conn.close()
        return render_template(
            "registros.html",
            pacientes=pacientes,
            usuario=session["usuario"],
            atencion_colectiva=atencion_colectiva,
            atencion_colectiva_id=atencion_colectiva_id,
            fecha_filtro=fecha_filtro,
            search_query=search_query,
            profesional_filtro=profesional_filtro,
            aseguradora_filtro=aseguradora_filtro,
            profesionales=profesionales,
            aseguradoras=aseguradoras,
            page=page,
            total_pages=total_pages
        )


    @app.route("/registros/ver/<token>")
    @login_required
    def ver_hc(token):
        try:
            paciente_id = int(serializer.loads(token))
        except (BadSignature, ValueError, TypeError):
            flash("Enlace de historia clínica inválido.", "error")
            return redirect(url_for("registros"))
            
        conn = get_db()
        paciente = conn.execute("SELECT * FROM pacientes WHERE id = ?", (paciente_id,)).fetchone()
        if not paciente:
            conn.close()
            flash("Registro de paciente no encontrado.", "error")
            return redirect(url_for("registros"))
        
        if session["usuario"]["rol"] != "admin" and paciente["registrado_por_identificacion"] != session["usuario"]["identificacion"]:
            conn.close()
            flash("Acceso denegado. Solo puede ver sus propios registros.", "error")
            return redirect(url_for("registros"))
            
        atencion_colectiva = None
        if paciente["atencion_colectiva_id"]:
            atencion_colectiva = conn.execute(
                "SELECT * FROM atencion_colectiva WHERE id = ?", (paciente["atencion_colectiva_id"],)
            ).fetchone()
        conn.close()
        return render_template("ver_hc.html", p=paciente, atencion_colectiva=atencion_colectiva, usuario=session["usuario"])


    # --- Admin Routes for User Management ---

