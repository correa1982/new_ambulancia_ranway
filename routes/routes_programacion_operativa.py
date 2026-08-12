from flask import render_template, request, session, redirect, url_for, flash
from utils import login_required
from db import get_db

def register_routes(app):
    @app.route("/programacion_operativa", methods=["GET", "POST"])
    @login_required
    def programacion_operativa():
        if not session.get("usuario") or (not session["usuario"].get("permiso_programacion_operativa") and str(session["usuario"].get("id")) != '1'):
            flash("No tienes permiso para acceder a Programación Operativa.", "error")
            return redirect(url_for("dashboard"))
            
        conn = get_db()
        if request.method == "POST":
            tipo_evento = request.form.get("tipo_evento")
            nombre_evento = request.form.get("nombre_evento", "").strip()
            fecha = request.form.get("fecha")
            hora_inicio = request.form.get("hora_inicio", "").strip()
            hora_finalizacion = request.form.get("hora_finalizacion", "").strip()
            lugar = request.form.get("lugar", "").strip()
            contacto = request.form.get("contacto", "").strip()
            coordina = request.form.get("coordina", "").strip()
            recursos_tecnicos = request.form.get("recursos_tecnicos", "").strip()
            registrado_por = session["usuario"]["id"]
            
            columnas_layout = request.form.get("columnas_layout", "3")
            try:
                columnas_layout = int(columnas_layout)
            except:
                columnas_layout = 3
            
            cursor = conn.execute("""
                INSERT INTO programacion_operativa 
                (tipo_evento, nombre_evento, fecha, hora_inicio, hora_finalizacion, lugar, contacto, coordina, recursos_tecnicos, registrado_por, columnas_layout)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tipo_evento, nombre_evento, fecha, hora_inicio, hora_finalizacion, lugar, contacto, coordina, recursos_tecnicos, registrado_por, columnas_layout))
            programacion_id = cursor.lastrowid
            
            if tipo_evento == "Tripulacion Basica":
                nombres = request.form.getlist("integrante_nombre[]")
                roles = request.form.getlist("integrante_rol[]")
                
                basica_tipo = request.form.get("basica_tipo_ambulancia", "").strip()
                basica_num = request.form.get("basica_numero_movil", "").strip()
                
                u_nombre = ""
                if basica_tipo or basica_num:
                    if basica_tipo:
                        u_nombre = f"AMB. {basica_tipo}"
                        if basica_num:
                            u_nombre += f" {basica_num}"
                    else:
                        u_nombre = basica_num
                
                for i, nombre in enumerate(nombres):
                    if nombre.strip():
                        rol = roles[i] if i < len(roles) else ""
                        conn.execute("""
                            INSERT INTO programacion_operativa_integrantes (programacion_id, nombre, rol_variable, orden, unidad_nombre)
                            VALUES (?, ?, ?, ?, ?)
                        """, (programacion_id, nombre.strip(), rol.strip(), i+1, u_nombre))
            elif tipo_evento == "Operativo Completo":
                unidad_nombres = request.form.getlist("unidad_nombre[]")
                unidad_tipos = request.form.getlist("unidad_tipo[]")
                unidad_counts = request.form.getlist("unidad_campos_count[]")
                u_roles = request.form.getlist("unidad_integrante_rol[]")
                u_nombres = request.form.getlist("unidad_integrante_nombre[]")
                
                offset = 0
                for u_idx, u_count_str in enumerate(unidad_counts):
                    try:
                        u_count = int(u_count_str)
                    except:
                        u_count = 0
                        
                    u_nombre = unidad_nombres[u_idx] if u_idx < len(unidad_nombres) else ""
                    u_tipo = unidad_tipos[u_idx] if u_idx < len(unidad_tipos) else ""
                    
                    for i in range(u_count):
                        idx = offset + i
                        if idx < len(u_nombres):
                            nombre = u_nombres[idx].strip()
                            rol = u_roles[idx].strip() if idx < len(u_roles) else ""
                            if nombre:
                                conn.execute("""
                                    INSERT INTO programacion_operativa_integrantes 
                                    (programacion_id, nombre, rol_variable, orden, unidad_nombre)
                                    VALUES (?, ?, ?, ?, ?)
                                """, (programacion_id, nombre, rol, i+1, u_nombre))
                    offset += u_count
            conn.commit()
            conn.close()
            flash("Programación operativa guardada correctamente.", "success")
            return redirect(url_for("programacion_operativa_explorador"))
            
        # Cargar personal de nómina
        # Obtener última nómina
        ultima_nomina = conn.execute("SELECT id FROM nomina ORDER BY id DESC LIMIT 1").fetchone()
        
        empleados = []
        if ultima_nomina:
            empleados_rows = conn.execute("SELECT DISTINCT nombres, apellidos FROM nomina_empleados WHERE nomina_id = ? ORDER BY nombres, apellidos", (ultima_nomina["id"],)).fetchall()
            for row in empleados_rows:
                empleados.append(f"{row['nombres']} {row['apellidos']}".strip())
                
        conn.close()
        return render_template("programacion_operativa.html", usuario=session["usuario"], empleados=empleados)

    @app.route("/programacion_operativa/explorador")
    @login_required
    def programacion_operativa_explorador():
        if not session.get("usuario") or (not session["usuario"].get("permiso_programacion_operativa") and str(session["usuario"].get("id")) != '1'):
            flash("No tienes permiso.", "error")
            return redirect(url_for("dashboard"))
            
        conn = get_db()
        fecha_desde = request.args.get('fecha_desde', '').strip()
        fecha_hasta = request.args.get('fecha_hasta', '').strip()
        
        if fecha_desde and fecha_hasta:
            eventos = conn.execute("SELECT * FROM programacion_operativa WHERE fecha >= ? AND fecha <= ? ORDER BY fecha DESC, id DESC", (fecha_desde, fecha_hasta)).fetchall()
        elif fecha_desde:
            eventos = conn.execute("SELECT * FROM programacion_operativa WHERE fecha >= ? ORDER BY fecha DESC, id DESC", (fecha_desde,)).fetchall()
        elif fecha_hasta:
            eventos = conn.execute("SELECT * FROM programacion_operativa WHERE fecha <= ? ORDER BY fecha DESC, id DESC", (fecha_hasta,)).fetchall()
        else:
            eventos = conn.execute("SELECT * FROM programacion_operativa ORDER BY id DESC").fetchall()
        
        for evento in eventos:
            evento["integrantes"] = conn.execute("SELECT * FROM programacion_operativa_integrantes WHERE programacion_id = ? ORDER BY orden", (evento["id"],)).fetchall()
            
        conn.close()
        return render_template("programacion_operativa_explorador.html", eventos=eventos, usuario=session["usuario"], fecha_desde=fecha_desde, fecha_hasta=fecha_hasta)

    @app.route("/programacion_operativa/imprimir/<int:evento_id>")
    @login_required
    def programacion_operativa_imprimir(evento_id):
        if not session.get("usuario") or (not session["usuario"].get("permiso_programacion_operativa") and str(session["usuario"].get("id")) != '1'):
            return "No tienes permiso.", 403
            
        conn = get_db()
        evento = conn.execute("SELECT * FROM programacion_operativa WHERE id = ?", (evento_id,)).fetchone()
        if not evento:
            conn.close()
            return "Evento no encontrado", 404
            
        integrantes = conn.execute("SELECT * FROM programacion_operativa_integrantes WHERE programacion_id = ? ORDER BY orden", (evento["id"],)).fetchall()
        conn.close()
        
        # Formatear la fecha
        import locale
        from datetime import datetime
        try:
            locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_TIME, 'es_CO.utf8')
            except:
                pass # Fallback to default if locales not found
                
        fecha_obj = evento['fecha']
        if isinstance(fecha_obj, str):
            try:
                fecha_obj = datetime.strptime(fecha_obj, '%Y-%m-%d')
            except:
                pass
                
        fecha_formateada = ""
        mes_ano = ""
        if isinstance(fecha_obj, datetime) or hasattr(fecha_obj, 'strftime'):
            # Convert to uppercase
            meses = ['ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO', 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
            dias = ['LUNES', 'MARTES', 'MIÉRCOLES', 'JUEVES', 'VIERNES', 'SÁBADO', 'DOMINGO']
            mes_str = meses[fecha_obj.month - 1]
            dia_semana_str = dias[fecha_obj.weekday()]
            
            fecha_formateada = f"{mes_str} {fecha_obj.day} ({dia_semana_str})"
            mes_ano = f"{mes_str} {fecha_obj.year}"
            
        def format_12h(time_str):
            if not time_str or time_str.strip() == '':
                return ''
            try:
                # Si ya tiene am/pm no hacer nada
                if 'am' in time_str.lower() or 'pm' in time_str.lower():
                    return time_str
                parts = time_str.split(':')
                h = int(parts[0])
                m = int(parts[1])
                suffix = 'am' if h < 12 else 'pm'
                h_12 = h if h <= 12 else h - 12
                if h_12 == 0: h_12 = 12
                return f"{h_12}:{m:02d} {suffix}"
            except:
                return time_str
                
        # Modificamos el diccionario de evento para mostrar las horas formateadas en la plantilla
        evento_dict = dict(evento)
        evento_dict['hora_inicio'] = format_12h(evento_dict.get('hora_inicio', ''))
        evento_dict['hora_finalizacion'] = format_12h(evento_dict.get('hora_finalizacion', ''))

        unidades = []
        if evento_dict.get('tipo_evento') == 'Operativo Completo':
            unidad_dict = {}
            for ing in integrantes:
                u_nombre = ing.get('unidad_nombre') or 'UNIDAD'
                if u_nombre not in unidad_dict:
                    unidad_dict[u_nombre] = []
                unidad_dict[u_nombre].append(ing)
            for k, v in unidad_dict.items():
                unidades.append({'nombre': k, 'integrantes': v})

        # Alternative date format: DOMINGO 24 DE MAYO
        fecha_completo = ""
        if isinstance(fecha_obj, datetime) or hasattr(fecha_obj, 'strftime'):
            fecha_completo = f"{dia_semana_str} {fecha_obj.day} DE {mes_str}"

        context = {
            'evento': evento_dict,
            'integrantes': integrantes,
            'unidades': unidades,
            'fecha_formateada': fecha_formateada,
            'fecha_completo': fecha_completo,
            'mes_ano': mes_ano
        }
        
        return render_template("programacion_operativa_imprimir.html", **context)

    @app.route("/programacion_operativa/confirmar", methods=["POST"])
    @login_required
    def programacion_operativa_confirmar():
        if not session.get("usuario") or (not session["usuario"].get("permiso_programacion_operativa") and str(session["usuario"].get("id")) != '1'):
            return "No autorizado", 403
            
        evento_id = request.form.get("evento_id")
        asistentes_ids = request.form.getlist("asistio[]")
        
        hora_inicio = request.form.get("hora_inicio", "").strip()
        hora_finalizacion = request.form.get("hora_finalizacion", "").strip()
        
        try:
            val_asis = request.form.get("tarifa_asistencial", "0").replace(".", "").replace(",", "")
            tarifa_asistencial = int(val_asis) if val_asis else 0
        except:
            tarifa_asistencial = 0
            
        try:
            val_cond = request.form.get("tarifa_conductor", "0").replace(".", "").replace(",", "")
            tarifa_conductor = int(val_cond) if val_cond else 0
        except:
            tarifa_conductor = 0
        
        if not evento_id:
            flash("Error: No se proporcionó el ID del evento.", "error")
            return redirect(url_for("programacion_operativa_explorador"))
            
        conn = get_db()
        try:
            # Marcar el evento como confirmado y guardar horas/tarifas
            conn.execute("""
                UPDATE programacion_operativa 
                SET confirmado = 1, hora_inicio = ?, hora_finalizacion = ?, tarifa_asistencial = ?, tarifa_conductor = ? 
                WHERE id = ?
            """, (hora_inicio, hora_finalizacion, tarifa_asistencial, tarifa_conductor, evento_id))
            
            # Todos los integrantes de este evento se marcan como no asistieron por defecto
            conn.execute("UPDATE programacion_operativa_integrantes SET asistio = 0 WHERE programacion_id = ?", (evento_id,))
            
            # Y los que vinieron en la lista (los que dejaron el checkbox marcado) se marcan como asistieron
            if asistentes_ids:
                placeholders = ",".join("?" * len(asistentes_ids))
                conn.execute(f"UPDATE programacion_operativa_integrantes SET asistio = 1 WHERE programacion_id = ? AND id IN ({placeholders})", [evento_id] + asistentes_ids)
                
            conn.commit()
            flash("Asistencia confirmada correctamente.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error al confirmar asistencia: {e}", "error")
        finally:
            conn.close()
            
        return redirect(url_for("programacion_operativa_explorador"))

    from flask import jsonify

    @app.route("/api/check_programacion_conflict", methods=["POST"])
    @login_required
    def check_programacion_conflict():
        data = request.get_json()
        if not data:
            return jsonify({"conflictos": []})
            
        fecha = data.get('fecha')
        hora_inicio = data.get('hora_inicio')
        hora_finalizacion = data.get('hora_finalizacion')
        nombres = data.get('nombres', [])
        ignore_evento_id = data.get('ignore_evento_id')
        
        if not fecha or not nombres:
            return jsonify({"conflictos": []})
            
        conn = get_db()
        try:
            query = """
                SELECT po.id, po.nombre_evento, po.hora_inicio, po.hora_finalizacion, poi.nombre 
                FROM programacion_operativa po
                JOIN programacion_operativa_integrantes poi ON po.id = poi.programacion_id
                WHERE po.fecha = ?
            """
            params = [fecha]
            
            if ignore_evento_id:
                query += " AND po.id != ?"
                params.append(ignore_evento_id)
                
            rows = conn.execute(query, params).fetchall()
            
            conflictos = []
            for r in rows:
                if r['nombre'] in nombres:
                    h_i = r['hora_inicio']
                    h_f = r['hora_finalizacion'] or "23:59"
                    
                    req_h_i = hora_inicio or "00:00"
                    req_h_f = hora_finalizacion or "23:59"
                    
                    if req_h_i < h_f and req_h_f > h_i:
                        conflictos.append({
                            "nombre": r['nombre'],
                            "evento": r['nombre_evento'],
                            "hora_inicio": h_i,
                            "hora_finalizacion": h_f
                        })
            return jsonify({"conflictos": conflictos})
        except Exception as e:
            print("Error checking conflict:", e)
            return jsonify({"conflictos": []})
        finally:
            conn.close()

    @app.route("/programacion_operativa/editar_integrantes", methods=["POST"])
    @login_required
    def programacion_operativa_editar_integrantes():
        if not session.get("usuario") or (not session["usuario"].get("permiso_programacion_operativa") and str(session["usuario"].get("id")) != '1'):
            return "No autorizado", 403
            
        evento_id = request.form.get("evento_id")
        if not evento_id:
            flash("Error: No se proporcionó el ID del evento.", "error")
            return redirect(url_for("programacion_operativa_explorador"))
            
        integrante_ids = request.form.getlist("integrante_id[]")
        nombres = request.form.getlist("nombre[]")
        roles = request.form.getlist("rol_variable[]")
        unidades = request.form.getlist("unidad_nombre[]")
        
        conn = get_db()
        try:
            # Delete those not in the current list
            valid_ids = [i for i in integrante_ids if i.isdigit() and i != '0']
            if valid_ids:
                placeholders = ",".join("?" * len(valid_ids))
                conn.execute(f"DELETE FROM programacion_operativa_integrantes WHERE programacion_id = ? AND id NOT IN ({placeholders})", [evento_id] + valid_ids)
            else:
                conn.execute("DELETE FROM programacion_operativa_integrantes WHERE programacion_id = ?", (evento_id,))
                
            # Update or Insert
            for i in range(len(nombres)):
                nombre = nombres[i].strip()
                if not nombre:
                    continue
                rol = roles[i].strip() if i < len(roles) else ""
                unidad = unidades[i].strip() if i < len(unidades) else ""
                i_id = integrante_ids[i] if i < len(integrante_ids) else "0"
                
                if i_id.isdigit() and i_id != '0':
                    # Update
                    conn.execute("""
                        UPDATE programacion_operativa_integrantes 
                        SET nombre = ?, rol_variable = ?, unidad_nombre = ?
                        WHERE id = ? AND programacion_id = ?
                    """, (nombre, rol, unidad, i_id, evento_id))
                else:
                    # Insert
                    conn.execute("""
                        INSERT INTO programacion_operativa_integrantes (programacion_id, nombre, rol_variable, unidad_nombre, orden)
                        VALUES (?, ?, ?, ?, ?)
                    """, (evento_id, nombre, rol, unidad, i+1))
                    
            conn.commit()
            flash("Integrantes actualizados correctamente.", "success")
        except Exception as e:
            conn.rollback()
            flash(f"Error al actualizar integrantes: {e}", "error")
        finally:
            conn.close()
            
        return redirect(url_for("programacion_operativa_explorador"))

    @app.route("/programacion_operativa/exportar_pagos")
    @login_required
    def programacion_operativa_exportar_pagos():
        fecha_inicio = request.args.get("fecha_inicio")
        fecha_fin = request.args.get("fecha_fin")
        
        if not fecha_inicio or not fecha_fin:
            flash("Debe seleccionar un rango de fechas.", "error")
            return redirect(url_for("programacion_operativa_explorador"))
            
        conn = get_db()
        query = """
            SELECT 
                po.id as evento_id,
                po.fecha,
                po.nombre_evento,
                po.tarifa_asistencial,
                po.tarifa_conductor,
                poi.nombre as integrante_nombre,
                poi.rol_variable as rol
            FROM programacion_operativa po
            JOIN programacion_operativa_integrantes poi ON po.id = poi.programacion_id
            WHERE po.confirmado = 1 
              AND poi.asistio = 1
              AND po.fecha >= ? 
              AND po.fecha <= ?
            ORDER BY po.fecha ASC, po.id ASC
        """
        filas = conn.execute(query, (fecha_inicio, fecha_fin)).fetchall()
        
        # Obtener datos del último archivo de nómina para mapear nombres a identificacion, nombres, apellidos
        ultima_nomina = conn.execute("SELECT id FROM nomina ORDER BY id DESC LIMIT 1").fetchone()
        mapa_empleados = {}
        if ultima_nomina:
            empleados = conn.execute("SELECT identificacion, nombres, apellidos, codigo FROM nomina_empleados WHERE nomina_id = ?", (ultima_nomina["id"],)).fetchall()
            for emp in empleados:
                # Usar el nombre completo como llave de busqueda simple (asumiendo que poi.nombre coincide con nombres + apellidos o solo nombres)
                llave1 = f"{emp['nombres']} {emp['apellidos']}".strip().upper()
                llave2 = emp['nombres'].strip().upper() if emp['nombres'] else ""
                mapa_empleados[llave1] = emp
                if llave2:
                    mapa_empleados[llave2] = emp

        # Agrupar datos por integrante y evento
        datos_agrupados = {}
        eventos_unicos = []
        eventos_set = set()
        
        for fila in filas:
            integrante = fila['integrante_nombre'].strip()
            fecha = fila['fecha']
            nombre_evento = fila['nombre_evento'] or "Evento"
            evento_id = fila['evento_id']
            rol = fila['rol'] or ""
            
            # Llave unica para la columna del evento
            llave_evento = f"{fecha} - {nombre_evento} (#{evento_id})"
            
            if llave_evento not in eventos_set:
                eventos_set.add(llave_evento)
                eventos_unicos.append(llave_evento)
            
            tarifa = 0
            if rol.upper() == 'COND' or rol.strip() == '':
                tarifa = fila['tarifa_conductor'] or 0
            else:
                tarifa = fila['tarifa_asistencial'] or 0
                
            if integrante not in datos_agrupados:
                datos_agrupados[integrante] = {}
                
            datos_agrupados[integrante][llave_evento] = datos_agrupados[integrante].get(llave_evento, 0) + tarifa

        conn.close()
        
        import io
        import openpyxl
        from flask import send_file
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Pagos"
        
        headers = ['CODIGO', 'IDENTIFICACION', 'NOMBRES', 'APELLIDOS'] + eventos_unicos + ['TOTAL']
        ws.append(headers)
        
        for integrante, pagos_por_evento in datos_agrupados.items():
            llave_busqueda = integrante.upper()
            emp_data = mapa_empleados.get(llave_busqueda)
            
            if emp_data:
                codigo = emp_data['codigo']
                identificacion = emp_data['identificacion']
                nombres = emp_data['nombres']
                apellidos = emp_data['apellidos']
            else:
                codigo = ""
                identificacion = ""
                # Intentar separar el nombre si no se encuentra
                partes = integrante.split(" ", 1)
                nombres = partes[0]
                apellidos = partes[1] if len(partes) > 1 else ""
                
            fila_excel = [codigo, identificacion, nombres, apellidos]
            
            total = 0
            for evento in eventos_unicos:
                valor = pagos_por_evento.get(evento, 0)
                fila_excel.append(valor)
                total += valor
                
            fila_excel.append(total)
            ws.append(fila_excel)
            
        excel_io = io.BytesIO()
        wb.save(excel_io)
        excel_io.seek(0)
        
        return send_file(
            excel_io,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'Exportar_Pagos_{fecha_inicio}_al_{fecha_fin}.xlsx'
        )
