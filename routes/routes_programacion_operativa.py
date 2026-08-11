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
            recursos_tecnicos = request.form.get("recursos_tecnicos", "").strip()
            registrado_por = session["usuario"]["id"]
            
            columnas_layout = request.form.get("columnas_layout", "3")
            try:
                columnas_layout = int(columnas_layout)
            except:
                columnas_layout = 3
            
            cursor = conn.execute("""
                INSERT INTO programacion_operativa 
                (tipo_evento, nombre_evento, fecha, hora_inicio, hora_finalizacion, lugar, contacto, recursos_tecnicos, registrado_por, columnas_layout)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tipo_evento, nombre_evento, fecha, hora_inicio, hora_finalizacion, lugar, contacto, recursos_tecnicos, registrado_por, columnas_layout))
            programacion_id = cursor.lastrowid
            
            if tipo_evento == "Tripulacion Basica":
                nombres = request.form.getlist("integrante_nombre[]")
                roles = request.form.getlist("integrante_rol[]")
                
                for i, nombre in enumerate(nombres):
                    if nombre.strip():
                        rol = roles[i] if i < len(roles) else ""
                        conn.execute("""
                            INSERT INTO programacion_operativa_integrantes (programacion_id, nombre, rol_variable, orden)
                            VALUES (?, ?, ?, ?)
                        """, (programacion_id, nombre.strip(), rol.strip(), i+1))
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
                                    (programacion_id, nombre, rol_variable, orden, unidad_nombre, unidad_tipo)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (programacion_id, nombre, rol, i+1, u_nombre, u_tipo))
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
        fecha_filtro = request.args.get('fecha_filtro', '').strip()
        
        if fecha_filtro:
            eventos = conn.execute("SELECT * FROM programacion_operativa WHERE fecha = ? ORDER BY id DESC", (fecha_filtro,)).fetchall()
        else:
            eventos = conn.execute("SELECT * FROM programacion_operativa ORDER BY id DESC").fetchall()
        
        for evento in eventos:
            evento["integrantes"] = conn.execute("SELECT * FROM programacion_operativa_integrantes WHERE programacion_id = ? ORDER BY orden", (evento["id"],)).fetchall()
            
        conn.close()
        return render_template("programacion_operativa_explorador.html", eventos=eventos, usuario=session["usuario"], fecha_filtro=fecha_filtro)

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
            tarifa_asistencial = int(request.form.get("tarifa_asistencial", 0))
        except:
            tarifa_asistencial = 0
            
        try:
            tarifa_conductor = int(request.form.get("tarifa_conductor", 0))
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
                po.hora_inicio,
                po.hora_finalizacion,
                po.tarifa_asistencial,
                po.tarifa_conductor,
                poi.nombre as integrante_nombre,
                poi.rol_variable as rol,
                poi.unidad_nombre
            FROM programacion_operativa po
            JOIN programacion_operativa_integrantes poi ON po.id = poi.programacion_id
            WHERE po.confirmado = 1 
              AND poi.asistio = 1
              AND po.fecha >= ? 
              AND po.fecha <= ?
            ORDER BY po.fecha ASC, po.id ASC
        """
        filas = conn.execute(query, (fecha_inicio, fecha_fin)).fetchall()
        conn.close()
        
        import csv
        import io
        from flask import Response
        
        si = io.StringIO()
        cw = csv.writer(si, delimiter=';')
        
        cw.writerow(['ID Evento', 'Fecha', 'Evento', 'Unidad', 'Integrante', 'Rol', 'Duracion (Horas)', 'Total a Pagar'])
        
        for fila in filas:
            h_inicio = fila['hora_inicio']
            h_fin = fila['hora_finalizacion']
            horas = 0
            if h_inicio and h_fin:
                try:
                    h1, m1 = map(int, h_inicio.split(':'))
                    h2, m2 = map(int, h_fin.split(':'))
                    mins1 = h1 * 60 + m1
                    mins2 = h2 * 60 + m2
                    if mins2 < mins1:
                        mins2 += 24 * 60
                    horas = (mins2 - mins1) / 60.0
                except:
                    pass
                    
            rol = fila['rol'] or ""
            tarifa = 0
            if rol.upper() == 'COND' or rol.strip() == '':
                tarifa = fila['tarifa_conductor'] or 0
            else:
                tarifa = fila['tarifa_asistencial'] or 0
                
            cw.writerow([
                f"#{fila['evento_id']}",
                fila['fecha'],
                fila['nombre_evento'],
                fila['unidad_nombre'] or 'Básica',
                fila['integrante_nombre'],
                rol,
                round(horas, 2),
                tarifa
            ])
            
        output = si.getvalue().encode('utf-8-sig')
        return Response(
            output,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=Pagos_Operativos_{fecha_inicio}_a_{fecha_fin}.csv"}
        )
