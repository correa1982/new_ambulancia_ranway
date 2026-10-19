import os
import uuid
from datetime import datetime, date
from flask import Blueprint, request, jsonify, render_template, current_app, send_from_directory, flash, redirect, url_for
from werkzeug.utils import secure_filename
from db import get_db
from utils import login_required, get_user_info, LimitadorIntentos, validar_upload_excel, ahora

_limite_consulta_nomina = LimitadorIntentos(5, 900)

def register_routes(app):
    nomina_bp = Blueprint('nomina', __name__)

    # Ensure upload directory exists
    UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads', 'nomina')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # We will only allow Excel extensions for safety
    ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}

    def allowed_file(filename):
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    def _tiene_acceso_nomina():
        from flask import session
        u = session.get('usuario') or {}
        acceso = u.get('formularios_acceso', [])
        if isinstance(acceso, dict):
            acceso = [x for v in acceso.values() if isinstance(v, list) for x in v]
        return u.get('rol_real') == 'admin' or 'nomina' in (acceso or [])

    def _denegar_nomina():
        flash('Acceso no autorizado al módulo de honorarios.', 'error')
        return redirect(url_for('dashboard'))

    # Los archivos de nomina viven bajo /static: se bloquea el acceso directo sin permiso
    @app.route('/static/uploads/nomina/<path:filename>')
    @login_required
    def nomina_static_protegido(filename):
        if not _tiene_acceso_nomina():
            return _denegar_nomina()
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

    @nomina_bp.route('/nomina', methods=['GET'])
    @login_required
    def nomina_index():
        from flask import session
        user_info = session['usuario']
        if user_info.get('rol_real') != 'admin' and 'nomina' not in user_info.get('formularios_acceso', []):
            flash('Acceso no autorizado al módulo de honorarios.', 'error')
            return redirect(url_for('dashboard'))
        conn = get_db()
        try:
            cursor = conn.execute("SELECT * FROM nomina ORDER BY fecha_subida DESC")
            archivos = cursor.fetchall()
        except Exception as e:
            current_app.logger.error(f"Error fetching nomina records: {e}")
            archivos = []
        finally:
            conn.close()

        return render_template('nomina.html', user_info=user_info, archivos=archivos)

    @nomina_bp.route('/nomina/upload', methods=['POST'])
    @login_required
    def nomina_upload():
        from flask import session
        user_info = session['usuario']
        if user_info.get('rol_real') != 'admin' and 'nomina' not in user_info.get('formularios_acceso', []):
            flash('Acceso no autorizado al módulo de honorarios.', 'error')
            return redirect(url_for('dashboard'))

        if 'file' not in request.files:
            flash('No se seleccionó ningún archivo.', 'error')
            return redirect(url_for('nomina.nomina_index'))
            
        file = request.files['file']
        if file.filename == '':
            flash('El nombre del archivo está vacío.', 'error')
            return redirect(url_for('nomina.nomina_index'))
            
        if file and allowed_file(file.filename) and validar_upload_excel(file):
            original_filename = secure_filename(file.filename)
            # Make the filename unique to prevent overwriting
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}_{original_filename}"
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            
            try:
                file.save(file_path)
                
                # Save to database
                from flask import session
                import json
                import openpyxl
                user_info = session['usuario']
                conn = get_db()
                try:
                    now_bogota = ahora().replace(tzinfo=None)
                    cursor = conn.execute("""
                        INSERT INTO nomina (fecha_subida, nombre_archivo, archivo_url, registrado_por, registrado_por_identificacion)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        now_bogota,
                        original_filename,
                        unique_filename,
                        user_info['nombre'],
                        user_info['identificacion']
                    ))
                    nomina_id = cursor.lastrowid
                    
                    # Parse logic
                    wb = openpyxl.load_workbook(file_path, data_only=True)
                    ws = wb.active
                    
                    try:
                        conn.execute("ALTER TABLE nomina ADD COLUMN periodo VARCHAR(255)")
                    except Exception:
                        pass
                        
                    u2_val = ws['U2'].value
                    if isinstance(u2_val, (datetime, date)):
                        periodo_val = u2_val.strftime('%d/%m/%Y')
                    else:
                        periodo_val = str(u2_val).strip() if u2_val is not None and str(u2_val).strip().lower() != 'none' else ""
                    conn.execute("UPDATE nomina SET periodo = ? WHERE id = ?", (periodo_val, nomina_id))

                    # Cargar pagos previos registrados para este mismo período (celda U2) para conservar su validación
                    pagos_previos_map = {}
                    if periodo_val:
                        try:
                            # 1. De la tabla nomina_pagos
                            rows_np = conn.execute("""
                                SELECT identificacion, pago_realizado, fecha_pago, registrado_por, documento_equivalente
                                FROM nomina_pagos
                                WHERE periodo = ? AND (pago_realizado = 1 OR (documento_equivalente IS NOT NULL AND documento_equivalente != ''))
                            """, (periodo_val,)).fetchall()
                            for r in rows_np:
                                pagos_previos_map[str(r['identificacion']).strip()] = r

                            # 2. De nóminas anteriores con el mismo período
                            rows_ne = conn.execute("""
                                SELECT ne.identificacion, ne.pago_realizado, ne.fecha_pago, ne.usuario_pago AS registrado_por, ne.documento_equivalente
                                FROM nomina_empleados ne
                                JOIN nomina n ON ne.nomina_id = n.id
                                WHERE n.periodo = ? AND (ne.pago_realizado = 1 OR (ne.documento_equivalente IS NOT NULL AND ne.documento_equivalente != ''))
                                ORDER BY ne.fecha_pago ASC
                            """, (periodo_val,)).fetchall()
                            for r in rows_ne:
                                cc_key = str(r['identificacion']).strip()
                                if cc_key not in pagos_previos_map:
                                    pagos_previos_map[cc_key] = r
                                    # Sincronizar en nomina_pagos
                                    conn.execute("""
                                        INSERT INTO nomina_pagos (periodo, identificacion, pago_realizado, fecha_pago, registrado_por, documento_equivalente, fecha_actualizacion)
                                        VALUES (?, ?, ?, ?, ?, ?, NOW())
                                        ON DUPLICATE KEY UPDATE
                                            pago_realizado=VALUES(pago_realizado),
                                            fecha_pago=VALUES(fecha_pago),
                                            registrado_por=VALUES(registrado_por),
                                            documento_equivalente=VALUES(documento_equivalente)
                                    """, (periodo_val, cc_key, r.get('pago_realizado', 0), r['fecha_pago'], r['registrado_por'], r.get('documento_equivalente')))
                        except Exception as err_p:
                            current_app.logger.warning(f"Error consultando pagos previos por periodo U2: {err_p}")
                    
                    header_row_idx = None
                    headers = []
                    for idx, row in enumerate(ws.iter_rows(values_only=True)):
                        row_strs = [str(c).strip().upper() for c in row if c is not None]
                        if any('CODIGO' in c for c in row_strs) or any('IDENTIFICACI' in c for c in row_strs):
                            header_row_idx = idx
                            headers = [str(c).strip() if c is not None else f"Col_{i}" for i, c in enumerate(row)]
                            break
                    
                    if header_row_idx is not None:
                        cc_idx, nombres_idx, apellidos_idx, codigo_idx, total_idx = -1, -1, -1, -1, -1
                        for i, h in enumerate(headers):
                            hu = h.upper()
                            if 'IDENTIFICACI' in hu: cc_idx = i
                            elif 'NOMBRES' in hu: nombres_idx = i
                            elif 'APELLIDOS' in hu: apellidos_idx = i
                            elif 'CODIGO' in hu: codigo_idx = i
                            elif 'TOTAL' in hu: total_idx = i

                        if total_idx == -1 and len(headers) > 20:
                            total_idx = 20  # Columna U (0-indexed)
                        
                        for idx, row in enumerate(ws.iter_rows(values_only=True)):
                            if idx <= header_row_idx:
                                continue
                            if not row or cc_idx == -1 or len(row) <= cc_idx or row[cc_idx] is None:
                                continue
                            cc_val = str(row[cc_idx]).strip()
                            if not cc_val or cc_val.lower() == 'none':
                                continue
                                
                            nombres_val = str(row[nombres_idx]).strip() if nombres_idx != -1 and len(row) > nombres_idx and row[nombres_idx] is not None else ""
                            apellidos_val = str(row[apellidos_idx]).strip() if apellidos_idx != -1 and len(row) > apellidos_idx and row[apellidos_idx] is not None else ""
                            
                            codigo_val_raw = row[codigo_idx] if codigo_idx != -1 and len(row) > codigo_idx else None
                            if isinstance(codigo_val_raw, datetime):
                                codigo_val = codigo_val_raw.strftime('%d/%m/%Y')
                            else:
                                codigo_val = str(codigo_val_raw).strip() if codigo_val_raw is not None else ""

                            total_val = str(row[total_idx]).strip() if total_idx != -1 and len(row) > total_idx and row[total_idx] is not None else ""
                            
                            detalle_dict = {}
                            for i, cell_val in enumerate(row):
                                if i not in (cc_idx, nombres_idx, apellidos_idx, codigo_idx, total_idx) and i < len(headers):
                                    h_name = headers[i]
                                    if cell_val is not None and h_name and not h_name.startswith('Col_'):
                                        # Format floats properly
                                        val_str = str(cell_val)
                                        if isinstance(cell_val, float):
                                            val_str = f"{cell_val:,.2f}"
                                        detalle_dict[h_name] = val_str
                                        
                                    detalle_json = json.dumps(detalle_dict, ensure_ascii=False)
                            
                            # Conservar validación de pago previa si ya existía para este periodo U2 y documento
                            prev_pago = pagos_previos_map.get(cc_val)
                            if prev_pago and (prev_pago.get('pago_realizado') or prev_pago.get('documento_equivalente')):
                                pago_realizado_val = 1 if prev_pago.get('pago_realizado') else 0
                                fecha_pago_val = prev_pago.get('fecha_pago')
                                usuario_pago_val = prev_pago.get('registrado_por')
                                doc_equiv_val = prev_pago.get('documento_equivalente') or None
                            else:
                                pago_realizado_val = 0
                                fecha_pago_val = None
                                usuario_pago_val = None
                                doc_equiv_val = None

                            conn.execute("""
                                INSERT INTO nomina_empleados (
                                    nomina_id, identificacion, nombres, apellidos, codigo, valor_total, detalle,
                                    pago_realizado, fecha_pago, usuario_pago, documento_equivalente
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (nomina_id, cc_val, nombres_val, apellidos_val, codigo_val, total_val, detalle_json,
                                  pago_realizado_val, fecha_pago_val, usuario_pago_val, doc_equiv_val))
                            
                    conn.commit()
                    flash('Archivo de honorarios subido y procesado exitosamente.', 'success')
                except Exception as db_error:
                    conn.close()
                    # Clean up the file if db insert fails
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    current_app.logger.error(f"Error saving nomina to db: {db_error}")
                    flash('Error al guardar el registro en la base de datos.', 'error')
                finally:
                    conn.close()
                    
            except Exception as save_error:
                current_app.logger.error(f"Error saving nomina file: {save_error}")
                flash('Error al guardar el archivo en el servidor.', 'error')
                
        else:
            flash('Tipo de archivo no permitido. Solo se permiten archivos Excel o CSV (.xlsx, .xls, .csv).', 'error')
            
        return redirect(url_for('nomina.nomina_index'))

    @nomina_bp.route('/nomina/download/<filename>')
    @login_required
    def download_nomina(filename):
        if not _tiene_acceso_nomina():
            return _denegar_nomina()
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

    @nomina_bp.route('/nomina/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_nomina(id):
        if not _tiene_acceso_nomina():
            return _denegar_nomina()
        conn = get_db()
        try:
            cursor = conn.execute("SELECT archivo_url FROM nomina WHERE id = ?", (id,))
            record = cursor.fetchone()
            if record:
                file_path = os.path.join(UPLOAD_FOLDER, os.path.basename(record['archivo_url'] or ''))
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    
                conn.execute("DELETE FROM nomina WHERE id = ?", (id,))
                conn.commit()
                flash('Registro eliminado exitosamente.', 'success')
            else:
                flash('Registro no encontrado.', 'error')
        except Exception as e:
            current_app.logger.error(f"Error deleting nomina record: {e}")
            flash('Error al eliminar el registro.', 'error')
        finally:
            conn.close()
            
        return redirect(url_for('nomina.nomina_index'))

    @nomina_bp.route('/nomina/consulta', methods=['GET', 'POST'])
    def nomina_consulta():
        import json
        if request.method == 'POST':
            cedula = request.form.get('cedula', '').strip()
            codigo = request.form.get('codigo', '').strip()
            
            if not cedula or not codigo:
                flash('Debe ingresar la cédula y el código.', 'error')
                return render_template('nomina_consulta.html', resultado=None)

            clave_ip = request.remote_addr or '?'
            if _limite_consulta_nomina.bloqueado(clave_ip) or _limite_consulta_nomina.bloqueado('c:' + cedula):
                flash('Demasiados intentos. Espere unos minutos e intente de nuevo.', 'error')
                return render_template('nomina_consulta.html', resultado=None)
                
            conn = get_db()
            try:
                # Find the latest nomina uploaded
                cursor = conn.execute("SELECT id, fecha_subida, periodo FROM nomina ORDER BY fecha_subida DESC LIMIT 1")
                latest_nomina = cursor.fetchone()
                
                if not latest_nomina:
                    flash('No hay registros de honorarios en el sistema.', 'error')
                    return render_template('nomina_consulta.html', resultado=None)
                    
                nomina_id = latest_nomina['id']
                
                # Check for employee in this nomina
                codigo_variants = [codigo]
                import re
                match = re.match(r'^(\d{2})/(\d{2})/(\d{4})$', codigo)
                if match:
                    d, m, y = match.groups()
                    codigo_variants.append(f"{y}-{m}-{d} 00:00:00")
                    codigo_variants.append(f"{y}-{m}-{d}")
                
                placeholders = ','.join(['?'] * len(codigo_variants))
                cursor = conn.execute(f"""
                    SELECT * FROM nomina_empleados 
                    WHERE nomina_id = ? AND identificacion = ? AND codigo IN ({placeholders})
                """, (nomina_id, cedula, *codigo_variants))
                empleado = cursor.fetchone()
                
                if empleado:
                    # Parse detalle json
                    if empleado['detalle']:
                        try:
                            empleado['detalle_dict'] = json.loads(empleado['detalle'])
                        except:
                            empleado['detalle_dict'] = {}
                    else:
                        empleado['detalle_dict'] = {}
                        
                    return render_template('nomina_consulta.html', resultado=empleado, fecha_nomina=latest_nomina['fecha_subida'], periodo_nomina=latest_nomina.get('periodo', ''))
                else:
                    _limite_consulta_nomina.registrar(clave_ip)
                    _limite_consulta_nomina.registrar('c:' + cedula)
                    flash('Cédula o código incorrectos, o no se encontró en los honorarios actuales.', 'error')
            except Exception as e:
                current_app.logger.error(f"Error querying nomina: {e}")
                flash('Error de servidor al consultar los honorarios.', 'error')
            finally:
                conn.close()
                
        return render_template('nomina_consulta.html', resultado=None)

    def _parse_monto(val):
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip().replace('$', '').replace(' ', '')
        if ',' in s and '.' in s:
            if s.rfind(',') > s.rfind('.'):
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '')
        elif ',' in s:
            parts = s.split(',')
            if len(parts) == 2 and len(parts[1]) in (1, 2):
                s = parts[0] + '.' + parts[1]
            else:
                s = s.replace(',', '')
        elif '.' in s:
            parts = s.split('.')
            if len(parts) > 2:
                s = s.replace('.', '')
            elif len(parts) == 2 and len(parts[1]) == 3:
                s = s.replace('.', '')
        try:
            return float(s)
        except Exception:
            return 0.0

    def _get_bogota_now():
        return ahora()

    def _calcular_alertas(conn, nomina_id, es_admin=False):
        cursor_all = conn.execute("""
            SELECT ne.id, ne.identificacion, ne.nombres, ne.apellidos, ne.valor_total,
                   COALESCE(np.pago_realizado, ne.pago_realizado, 0) AS pago_realizado,
                   COALESCE(np.fecha_pago, ne.fecha_pago) AS fecha_pago,
                   COALESCE(np.registrado_por, ne.usuario_pago) AS usuario_pago,
                   COALESCE(np.documento_equivalente, ne.documento_equivalente, '') AS documento_equivalente
            FROM nomina_empleados ne
            JOIN nomina n ON ne.nomina_id = n.id
            LEFT JOIN nomina_pagos np ON (np.periodo = n.periodo AND np.identificacion = ne.identificacion)
            WHERE ne.nomina_id = ?
        """, (nomina_id,))
        todos_empleados = cursor_all.fetchall()

        tot_personas = 0
        tot_pagadas = 0
        tot_pendientes = 0
        sum_valor_total = 0.0
        sum_valor_cancelado = 0.0
        sum_valor_pendiente = 0.0
        lista_pendientes = []
        lista_pagados = []

        for emp in todos_empleados:
            monto = _parse_monto(emp.get('valor_total'))
            # Solo considerar filas con valor en columna U mayor a 0
            if monto > 0:
                tot_personas += 1
                sum_valor_total += monto
                nombre_full = f"{emp.get('nombres', '')} {emp.get('apellidos', '')}".strip().title()

                if emp.get('pago_realizado'):
                    tot_pagadas += 1
                    sum_valor_cancelado += monto
                    if es_admin:
                        fp = emp.get('fecha_pago')
                        if isinstance(fp, datetime):
                            fp_str = fp.strftime('%d/%m/%Y %I:%M:%S %p')
                        elif fp:
                            fp_str = str(fp)
                        else:
                            fp_str = '-'
                        lista_pagados.append({
                            'identificacion': emp['identificacion'],
                            'nombre_completo': nombre_full,
                            'valor_total': monto,
                            'valor_formateado': f"${monto:,.0f}".replace(',', '.'),
                            'documento_equivalente': emp.get('documento_equivalente', ''),
                            'fecha_pago': fp_str,
                            'usuario_pago': emp.get('usuario_pago', '')
                        })
                else:
                    tot_pendientes += 1
                    sum_valor_pendiente += monto
                    if es_admin:
                        lista_pendientes.append({
                            'identificacion': emp['identificacion'],
                            'nombre_completo': nombre_full,
                            'valor_total': monto,
                            'valor_formateado': f"${monto:,.0f}".replace(',', '.'),
                            'documento_equivalente': emp.get('documento_equivalente', '')
                        })

        pct_pagado = round((tot_pagadas / tot_personas * 100), 1) if tot_personas > 0 else 0
        return {
            'total_personas': tot_personas,
            'personas_pagadas': tot_pagadas,
            'personas_pendientes': tot_pendientes,
            'valor_total': sum_valor_total,
            'valor_total_formateado': f"${sum_valor_total:,.0f}".replace(',', '.'),
            'valor_cancelado': sum_valor_cancelado,
            'valor_cancelado_formateado': f"${sum_valor_cancelado:,.0f}".replace(',', '.'),
            'valor_pendiente': sum_valor_pendiente,
            'valor_pendiente_formateado': f"${sum_valor_pendiente:,.0f}".replace(',', '.'),
            'pct_pagado': pct_pagado,
            'pendientes_lista': lista_pendientes if es_admin else [],
            'pagados_lista': lista_pagados if es_admin else []
        }
    @nomina_bp.route('/nomina/pagos', methods=['GET', 'POST'])
    @login_required
    def nomina_pagos():
        from flask import session
        user_info = session['usuario']
        tiene_acceso_pagos = (
            user_info.get('rol_real') == 'admin' or
            user_info.get('rol') == 'admin' or
            bool(user_info.get('permiso_verificacion_pagos')) or
            'nomina' in user_info.get('formularios_acceso', []) or
            'pagos' in user_info.get('formularios_acceso', [])
        )
        if not tiene_acceso_pagos:
            flash('Acceso no autorizado al módulo de verificación de pagos.', 'error')
            return redirect(url_for('dashboard'))

        es_admin = (user_info.get('rol_real') == 'admin')
        conn = get_db()
        archivos = []
        selected_nomina_id = None
        selected_nomina = None
        cedula = (request.args.get('cedula') or request.form.get('cedula') or '').strip()
        resultado = None

        alertas = {
            'total_personas': 0,
            'personas_pagadas': 0,
            'personas_pendientes': 0,
            'valor_total': 0.0,
            'valor_total_formateado': '$0',
            'valor_cancelado': 0.0,
            'valor_cancelado_formateado': '$0',
            'valor_pendiente': 0.0,
            'valor_pendiente_formateado': '$0',
            'pct_pagado': 0,
            'pendientes_lista': [],
            'pagados_lista': []
        }

        try:
            cursor = conn.execute("SELECT id, fecha_subida, nombre_archivo, periodo FROM nomina ORDER BY fecha_subida DESC")
            archivos = cursor.fetchall()

            raw_nomina_id = request.args.get('nomina_id') or request.form.get('nomina_id')
            if raw_nomina_id:
                try:
                    selected_nomina_id = int(raw_nomina_id)
                except (ValueError, TypeError):
                    selected_nomina_id = archivos[0]['id'] if archivos else None
            elif archivos:
                selected_nomina_id = archivos[0]['id']

            if selected_nomina_id and archivos:
                for a in archivos:
                    if a['id'] == selected_nomina_id:
                        selected_nomina = a
                        break

            # Calcular las alertas y métricas para el Excel seleccionado
            if selected_nomina_id:
                alertas = _calcular_alertas(conn, selected_nomina_id, es_admin=es_admin)

            # Si se consultó una cédula puntual
            if cedula and selected_nomina_id:
                cursor = conn.execute("""
                    SELECT ne.*, n.periodo, n.nombre_archivo, n.fecha_subida,
                           COALESCE(np.pago_realizado, ne.pago_realizado, 0) AS pago_realizado,
                           COALESCE(np.fecha_pago, ne.fecha_pago) AS fecha_pago,
                           COALESCE(np.registrado_por, ne.usuario_pago) AS usuario_pago,
                           COALESCE(np.documento_equivalente, ne.documento_equivalente, '') AS documento_equivalente
                    FROM nomina_empleados ne
                    JOIN nomina n ON ne.nomina_id = n.id
                    LEFT JOIN nomina_pagos np ON (np.periodo = n.periodo AND np.identificacion = ne.identificacion)
                    WHERE ne.nomina_id = ? AND ne.identificacion = ?
                    LIMIT 1
                """, (selected_nomina_id, cedula))
                row = cursor.fetchone()
                if row:
                    resultado = dict(row)
                    monto_individual = _parse_monto(resultado.get('valor_total', ''))
                    if monto_individual > 0:
                        resultado['valor_total_formateado'] = f"${monto_individual:,.0f}".replace(',', '.')
                    else:
                        resultado['valor_total_formateado'] = resultado.get('valor_total') or "$0"
                        
                    # Unificar nombres y apellidos
                    nombres = resultado.get('nombres', '') or ''
                    apellidos = resultado.get('apellidos', '') or ''
                    resultado['nombre_completo'] = f"{nombres} {apellidos}".strip().title()
                    resultado['documento_equivalente'] = (resultado.get('documento_equivalente') or '').strip()

                    # Formatear fecha_pago en horario de Bogotá
                    fp = resultado.get('fecha_pago')
                    if isinstance(fp, datetime):
                        resultado['fecha_pago_formateada'] = fp.strftime('%d/%m/%Y %I:%M:%S %p')
                    elif fp:
                        resultado['fecha_pago_formateada'] = str(fp)
                    else:
                        resultado['fecha_pago_formateada'] = None
                else:
                    flash(f'No se encontró ningún registro para la cédula {cedula} en la cuenta de cobro seleccionada.', 'warning')
        except Exception as e:
            current_app.logger.error(f"Error consultando pagos: {e}")
            flash('Error al consultar los registros de pagos.', 'error')
        finally:
            conn.close()

        return render_template(
            'nomina_pagos.html',
            user_info=user_info,
            es_admin=es_admin,
            archivos=archivos,
            selected_nomina_id=selected_nomina_id,
            selected_nomina=selected_nomina,
            cedula=cedula,
            resultado=resultado,
            alertas=alertas
        )

    @nomina_bp.route('/nomina/pagos/guardar', methods=['POST'])
    @login_required
    def nomina_guardar_pago():
        from flask import session
        user_info = session['usuario']
        tiene_acceso_pagos = (
            user_info.get('rol_real') == 'admin' or
            user_info.get('rol') == 'admin' or
            bool(user_info.get('permiso_verificacion_pagos')) or
            'nomina' in user_info.get('formularios_acceso', []) or
            'pagos' in user_info.get('formularios_acceso', [])
        )
        if not tiene_acceso_pagos:
            if request.is_json:
                return jsonify({'success': False, 'message': 'Acceso no autorizado'}), 403
            flash('Acceso no autorizado.', 'error')
            return redirect(url_for('dashboard'))

        if request.is_json:
            data = request.get_json(silent=True) or {}
            nomina_id = data.get('nomina_id')
            identificacion = str(data.get('identificacion', '')).strip()
            pago_realizado = 1 if str(data.get('pago_realizado', '')).lower() in ('1', 'true', 'on', 'yes') else 0
            doc_equivalente = str(data.get('documento_equivalente', '')).strip()
        else:
            nomina_id = request.form.get('nomina_id')
            identificacion = request.form.get('identificacion', '').strip()
            pago_realizado = 1 if request.form.get('pago_realizado') in ('1', 'true', 'on', 'yes') else 0
            doc_equivalente = str(request.form.get('documento_equivalente', '')).strip()

        doc_equivalente_val = doc_equivalente if doc_equivalente else None

        if not nomina_id or not identificacion:
            if request.is_json:
                return jsonify({'success': False, 'message': 'Cédula o cuenta de cobro inválida.'}), 400
            flash('Datos incompletos para guardar el pago.', 'error')
            return redirect(url_for('nomina.nomina_pagos'))

        conn = get_db()
        try:
            nom_row = conn.execute("SELECT id, periodo FROM nomina WHERE id = ?", (nomina_id,)).fetchone()
            if not nom_row:
                if request.is_json:
                    return jsonify({'success': False, 'message': 'Cuenta de cobro no encontrada.'}), 404
                flash('Cuenta de cobro no encontrada.', 'error')
                return redirect(url_for('nomina.nomina_pagos'))

            periodo = nom_row['periodo'] or ''
            now_bogota = _get_bogota_now()
            now_naive = now_bogota.replace(tzinfo=None)
            fecha_pago_str = now_bogota.strftime('%d/%m/%Y %I:%M:%S %p')
            usuario_nombre = user_info.get('nombre', 'Personal de Pagos')
            usuario_id = user_info.get('identificacion', '')

            if pago_realizado == 1:
                # Guardar en nomina_pagos con hora de Bogotá
                if periodo:
                    conn.execute("""
                        INSERT INTO nomina_pagos (
                            periodo, identificacion, pago_realizado, fecha_pago,
                            registrado_por, registrado_por_identificacion, fecha_actualizacion, documento_equivalente
                        )
                        VALUES (?, ?, 1, ?, ?, ?, ?, ?)
                        ON DUPLICATE KEY UPDATE
                            pago_realizado = 1,
                            fecha_pago = VALUES(fecha_pago),
                            registrado_por = VALUES(registrado_por),
                            registrado_por_identificacion = VALUES(registrado_por_identificacion),
                            fecha_actualizacion = VALUES(fecha_actualizacion),
                            documento_equivalente = VALUES(documento_equivalente)
                    """, (periodo, identificacion, now_naive, usuario_nombre, usuario_id, now_naive, doc_equivalente_val))

                    # Actualizar todos los registros de ese empleado en cualquier nómina del mismo período
                    conn.execute("""
                        UPDATE nomina_empleados ne
                        JOIN nomina n ON ne.nomina_id = n.id
                        SET ne.pago_realizado = 1, ne.fecha_pago = ?, ne.usuario_pago = ?, ne.documento_equivalente = ?
                        WHERE ne.identificacion = ? AND (n.id = ? OR n.periodo = ?)
                    """, (now_naive, usuario_nombre, doc_equivalente_val, identificacion, nomina_id, periodo))
                else:
                    conn.execute("""
                        UPDATE nomina_empleados
                        SET pago_realizado = 1, fecha_pago = ?, usuario_pago = ?, documento_equivalente = ?
                        WHERE nomina_id = ? AND identificacion = ?
                    """, (now_naive, usuario_nombre, doc_equivalente_val, nomina_id, identificacion))

                conn.commit()
                alertas_actualizadas = _calcular_alertas(conn, nomina_id, es_admin=(user_info.get('rol_real') == 'admin'))
                if request.is_json:
                    return jsonify({
                        'success': True,
                        'pago_realizado': 1,
                        'fecha_pago': fecha_pago_str,
                        'usuario_pago': usuario_nombre,
                        'documento_equivalente': doc_equivalente,
                        'alertas': alertas_actualizadas,
                        'message': '¡Verificación de pago guardada exitosamente!'
                    })
                flash('¡Verificación de pago guardada exitosamente!', 'success')
            else:
                # Desmarcar pago
                if periodo:
                    conn.execute("""
                        INSERT INTO nomina_pagos (
                            periodo, identificacion, pago_realizado, fecha_pago,
                            registrado_por, registrado_por_identificacion, fecha_actualizacion, documento_equivalente
                        )
                        VALUES (?, ?, 0, NULL, ?, ?, ?, ?)
                        ON DUPLICATE KEY UPDATE
                            pago_realizado = 0,
                            fecha_pago = NULL,
                            registrado_por = VALUES(registrado_por),
                            registrado_por_identificacion = VALUES(registrado_por_identificacion),
                            fecha_actualizacion = VALUES(fecha_actualizacion),
                            documento_equivalente = VALUES(documento_equivalente)
                    """, (periodo, identificacion, usuario_nombre, usuario_id, now_naive, doc_equivalente_val))

                    conn.execute("""
                        UPDATE nomina_empleados ne
                        JOIN nomina n ON ne.nomina_id = n.id
                        SET ne.pago_realizado = 0, ne.fecha_pago = NULL, ne.usuario_pago = ?, ne.documento_equivalente = ?
                        WHERE ne.identificacion = ? AND (n.id = ? OR n.periodo = ?)
                    """, (usuario_nombre, doc_equivalente_val, identificacion, nomina_id, periodo))
                else:
                    conn.execute("""
                        UPDATE nomina_empleados
                        SET pago_realizado = 0, fecha_pago = NULL, usuario_pago = ?, documento_equivalente = ?
                        WHERE nomina_id = ? AND identificacion = ?
                    """, (usuario_nombre, doc_equivalente_val, nomina_id, identificacion))

                conn.commit()
                alertas_actualizadas = _calcular_alertas(conn, nomina_id, es_admin=(user_info.get('rol_real') == 'admin'))
                if request.is_json:
                    return jsonify({
                        'success': True,
                        'pago_realizado': 0,
                        'fecha_pago': None,
                        'usuario_pago': usuario_nombre,
                        'documento_equivalente': doc_equivalente,
                        'alertas': alertas_actualizadas,
                        'message': 'Estado de pago actualizado a pendiente.'
                    })
                flash('Estado de pago actualizado a pendiente.', 'info')
        except Exception as e:
            current_app.logger.error(f"Error al guardar estado de pago: {e}")
            if request.is_json:
                return jsonify({'success': False, 'message': f'Error en el servidor: {str(e)}'}), 500
            flash('Error al guardar el estado del pago.', 'error')
        finally:
            conn.close()

        return redirect(url_for('nomina.nomina_pagos', nomina_id=nomina_id, cedula=identificacion))

    app.register_blueprint(nomina_bp)
