from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file
from datetime import datetime
from db import get_db

routes_voluntariado = Blueprint('voluntariado', __name__)

def check_permission():
    if 'usuario' not in session:
        return False
    if session['usuario'].get('rol') == 'admin':
        return True
    formularios = session['usuario'].get('formularios_acceso', [])
    if isinstance(formularios, dict):
        for perfiles_acc in formularios.values():
            if 'voluntariado' in perfiles_acc or 'voluntariado_admin' in perfiles_acc:
                return True
    elif isinstance(formularios, list):
        if 'voluntariado' in formularios or 'voluntariado_admin' in formularios:
            return True
    return False

def is_admin_vol():
    if 'usuario' not in session:
        return False
    if session['usuario'].get('rol') == 'admin':
        return True
    formularios = session['usuario'].get('formularios_acceso', [])
    if isinstance(formularios, dict):
        for perfiles_acc in formularios.values():
            if 'voluntariado_admin' in perfiles_acc:
                return True
    elif isinstance(formularios, list):
        if 'voluntariado_admin' in formularios:
            return True
    return False

def get_configuracion():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT clave, valor FROM configuracion")
    rows = cursor.fetchall()
    conn.close()
    cfg = {}
    for row in rows:
        if isinstance(row, dict):
            cfg[row['clave']] = row['valor']
        else:
            cfg[row[0]] = row[1]
    # Expose as object-like dict with common keys mapped to attribute names
    return {
        'logo_url': cfg.get('logo'),
        'nombre_institucion': cfg.get('nombre_institucion', ''),
        'subtitulo_institucion': cfg.get('subtitulo_institucion', ''),
        'nit': cfg.get('nit', ''),
        'nombre_sistema': cfg.get('nombre_sistema', ''),
        'marca_agua': cfg.get('marca_agua'),
        **cfg
    }

@routes_voluntariado.route('/voluntariado', methods=['GET', 'POST'])
def form_voluntariado():
    if not check_permission():
        flash("No tienes permisos para acceder a este módulo.", "danger")
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        fecha = request.form.get('fecha')
        hora_inicio = request.form.get('hora_inicio')
        hora_fin = request.form.get('hora_fin')
        disponibilidad = request.form.get('disponibilidad')
        disponibilidad_otro = request.form.get('disponibilidad_otro')
        total_horas = request.form.get('total_horas')
        actividad_realizada = request.form.get('actividad_realizada')
        observaciones = request.form.get('observaciones')
        
        usuario = session['usuario']
        registrado_por = usuario.get('nombre')
        registrado_por_identificacion = usuario.get('identificacion')
        perfil_registrador = usuario.get('perfil_seleccionado', 'Usuario')
        firma_registrador = usuario.get('firma_digital', '')
        fecha_registro = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db()
        cursor = conn.cursor()
        query = """
            INSERT INTO registro_voluntariado 
            (fecha, hora_inicio, hora_fin, disponibilidad, disponibilidad_otro, total_horas,
            actividad_realizada, observaciones, registrado_por, registrado_por_identificacion,
            perfil_registrador, firma_registrador, fecha_registro, estado)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pendiente')
        """
        valores = (fecha, hora_inicio, hora_fin, disponibilidad, disponibilidad_otro, total_horas,
                   actividad_realizada, observaciones, registrado_por, registrado_por_identificacion,
                   perfil_registrador, firma_registrador, fecha_registro)
        cursor.execute(query, valores)
        conn.commit()
        conn.close()
        
        flash("Registro de voluntariado guardado exitosamente.", "success")
        if is_admin_vol():
            return redirect(url_for('voluntariado.registros_voluntariado'))
        return redirect(url_for('dashboard'))

    return render_template('form_voluntariado.html', es_admin_vol=is_admin_vol())

@routes_voluntariado.route('/voluntariado/registros')
def registros_voluntariado():
    if not check_permission():
        flash("No tienes permisos para ver estos registros.", "danger")
        return redirect(url_for('dashboard'))
        
    conn = get_db()
    cursor = conn.cursor()
    
    if is_admin_vol():
        cursor.execute("SELECT * FROM registro_voluntariado WHERE estado NOT IN ('Inactivo', 'Anulado') ORDER BY id DESC")
        registros = cursor.fetchall()
    else:
        ident = session['usuario'].get('identificacion')
        cursor.execute("SELECT * FROM registro_voluntariado WHERE registrado_por_identificacion = %s AND estado NOT IN ('Inactivo', 'Anulado') ORDER BY id DESC", (ident,))
        registros = cursor.fetchall()
    
    conn.close()
    
    if registros and type(registros[0]) is tuple:
        cols = [column[0] for column in cursor.description]
        registros = [dict(zip(cols, row)) for row in registros]
    
    return render_template('registros_voluntariado.html', registros=registros, es_admin_vol=is_admin_vol())

@routes_voluntariado.route('/voluntariado/avalar/<int:record_id>', methods=['POST'])
def avalar_registro(record_id):
    if not is_admin_vol():
        flash("Permiso denegado.", "danger")
        return redirect(url_for('voluntariado.registros_voluntariado'))
        
    usuario = session['usuario']
    avalado_por = usuario.get('nombre')
    avalado_por_identificacion = usuario.get('identificacion')
    firma_avalador = usuario.get('firma_digital', '')
    fecha_aval = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cursor = conn.cursor()
    query = """
        UPDATE registro_voluntariado 
        SET estado = 'Avalado', avalado_por = %s, avalado_por_identificacion = %s,
            firma_avalador = %s, fecha_aval = %s
        WHERE id = %s
    """
    cursor.execute(query, (avalado_por, avalado_por_identificacion, firma_avalador, fecha_aval, record_id))
    conn.commit()
    conn.close()
    
    flash(f"Registro #{record_id} avalado correctamente.", "success")
    return redirect(url_for('voluntariado.registros_voluntariado'))

@routes_voluntariado.route('/voluntariado/anular/<int:record_id>', methods=['POST'])
def anular_registro(record_id):
    if not is_admin_vol():
        flash("Permiso denegado.", "danger")
        return redirect(url_for('voluntariado.registros_voluntariado'))
    
    usuario = session['usuario']
    anulado_por = usuario.get('nombre')
    fecha_anulacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cursor = conn.cursor()
    # Guardamos quién anuló y cuándo en el campo de observaciones si existe, o simplemente cambiamos el estado
    cursor.execute(
        "UPDATE registro_voluntariado SET estado = 'Anulado' WHERE id = %s",
        (record_id,)
    )
    conn.commit()
    conn.close()
    
    flash(f"Registro #{record_id} anulado por {anulado_por}. No afecta estadísticas.", "warning")
    return redirect(url_for('voluntariado.registros_voluntariado'))

@routes_voluntariado.route('/voluntariado/anulados')
def anulados_voluntariado():
    if not is_admin_vol():
        flash("Solo administradores pueden ver registros anulados.", "danger")
        return redirect(url_for('voluntariado.registros_voluntariado'))
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registro_voluntariado WHERE estado = 'Anulado' ORDER BY id DESC")
    registros = cursor.fetchall()
    conn.close()
    
    if registros and type(registros[0]) is tuple:
        cols = [column[0] for column in cursor.description]
        registros = [dict(zip(cols, row)) for row in registros]
    
    return render_template('anulados_voluntariado.html', registros=registros)

@routes_voluntariado.route('/voluntariado/estadisticas')
def estadisticas_voluntariado():
    if not is_admin_vol():
        flash("Solo administradores pueden ver estadísticas.", "danger")
        return redirect(url_for('voluntariado.registros_voluntariado'))
        
    conn = get_db()
    cursor = conn.cursor()
    
    # Conteos globales por estado
    cursor.execute("SELECT COUNT(*) as total FROM registro_voluntariado")
    row = cursor.fetchone()
    total_realizados = (row['total'] if isinstance(row, dict) else row[0]) if row else 0
    
    cursor.execute("SELECT COUNT(*) as total FROM registro_voluntariado WHERE estado = 'Avalado'")
    row = cursor.fetchone()
    total_avalados = (row['total'] if isinstance(row, dict) else row[0]) if row else 0
    
    cursor.execute("SELECT COUNT(*) as total FROM registro_voluntariado WHERE estado = 'Anulado'")
    row = cursor.fetchone()
    total_anulados = (row['total'] if isinstance(row, dict) else row[0]) if row else 0
    
    # Todos los registros con datos de usuario para agrupar
    cursor.execute("""
        SELECT registrado_por, registrado_por_identificacion, estado, total_horas
        FROM registro_voluntariado
        ORDER BY registrado_por
    """)
    todos = cursor.fetchall()
    conn.close()
    
    if todos and type(todos[0]) is tuple:
        cols = [c[0] for c in cursor.description]
        todos = [dict(zip(cols, r)) for r in todos]
    elif todos and type(todos[0]) is not dict:
        todos = [dict(r) for r in todos]
    
    def parsear_minutos(horas_str):
        """Convierte total_horas a minutos. Soporta: 'H:MM', 'H:MM:SS', 'Xh Ym', 'Xh', 'Ym'"""
        if not horas_str:
            return 0
        horas_str = str(horas_str).strip()
        try:
            # Formato H:MM o H:MM:SS
            if ':' in horas_str:
                partes = horas_str.split(':')
                h = int(partes[0]) if partes[0] else 0
                m = int(partes[1]) if len(partes) > 1 and partes[1] else 0
                return h * 60 + m
            # Formato "Xh Ym" o "Xh" o "Ym"
            import re
            h = 0
            m = 0
            match_h = re.search(r'(\d+)\s*h', horas_str)
            match_m = re.search(r'(\d+)\s*m', horas_str)
            if match_h:
                h = int(match_h.group(1))
            if match_m:
                m = int(match_m.group(1))
            if match_h or match_m:
                return h * 60 + m
        except Exception:
            pass
        return 0

    # Agrupar por usuario
    stats_usuarios = {}
    for r in todos:
        usuario = r.get('registrado_por', 'Desconocido')
        identificacion = r.get('registrado_por_identificacion', '-')
        estado = r.get('estado', '')
        horas_str = r.get('total_horas', '')
        
        if usuario not in stats_usuarios:
            stats_usuarios[usuario] = {
                'identificacion': identificacion,
                'realizados': 0,
                'avalados': 0,
                'anulados': 0,
                'minutos': 0
            }
        
        stats_usuarios[usuario]['realizados'] += 1
        if estado == 'Avalado':
            stats_usuarios[usuario]['avalados'] += 1
            stats_usuarios[usuario]['minutos'] += parsear_minutos(horas_str)
        elif estado == 'Anulado':
            stats_usuarios[usuario]['anulados'] += 1
    
    # Formatear horas por usuario y calcular total global
    total_minutos = 0
    for u in stats_usuarios:
        m = stats_usuarios[u]['minutos']
        total_minutos += m
        stats_usuarios[u]['horas_str'] = f"{m // 60}:{m % 60:02d}"
    
    horas_totales = total_minutos // 60
    mins_restantes = total_minutos % 60
    total_horas_str = f"{horas_totales}:{mins_restantes:02d}"
    
    return render_template('estadisticas_voluntariado.html',
                           total_realizados=total_realizados,
                           total_avalados=total_avalados,
                           total_anulados=total_anulados,
                           total_horas=total_horas_str,
                           stats_usuarios=stats_usuarios)

@routes_voluntariado.route('/voluntariado/exportar_excel')
def exportar_excel_voluntariado():
    if not is_admin_vol():
        flash("Solo administradores pueden exportar registros.", "danger")
        return redirect(url_for('voluntariado.registros_voluntariado'))

    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()

    conn = get_db()
    cursor = conn.cursor()

    sql = "SELECT * FROM registro_voluntariado"
    params = []
    where_clauses = []
    if fecha_desde:
        where_clauses.append("fecha >= %s")
        params.append(fecha_desde)
    if fecha_hasta:
        where_clauses.append("fecha <= %s")
        params.append(fecha_hasta)

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    sql += " ORDER BY fecha DESC, id DESC"

    cursor.execute(sql, tuple(params))
    registros = cursor.fetchall()
    conn.close()

    if registros and type(registros[0]) is tuple:
        cols = [c[0] for c in cursor.description]
        registros = [dict(zip(cols, r)) for r in registros]
    elif registros and type(registros[0]) is not dict:
        registros = [dict(r) for r in registros]

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Voluntariado"
    ws.views.sheetView[0].showGridLines = True

    # Title block
    ws.merge_cells('A1:Q1')
    title_cell = ws['A1']
    title_cell.value = "REPORTE DE REGISTROS DE VOLUNTARIADO"
    title_cell.font = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
    title_cell.fill = PatternFill("solid", fgColor="1E6FBF")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    # Subtitle / info block
    ws.merge_cells('A2:Q2')
    info_cell = ws['A2']
    rango_texto = "Histórico Completo"
    if fecha_desde and fecha_hasta:
        rango_texto = f"Desde: {fecha_desde}   Hasta: {fecha_hasta}"
    elif fecha_desde:
        rango_texto = f"Desde: {fecha_desde}"
    elif fecha_hasta:
        rango_texto = f"Hasta: {fecha_hasta}"
    info_cell.value = f"Rango: {rango_texto}   |   Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}   |   Total Registros: {len(registros)}"
    info_cell.font = Font(name="Calibri", size=10, italic=True, color="1E3A8A")
    info_cell.fill = PatternFill("solid", fgColor="EFF6FF")
    info_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 22

    headers = [
        ("ID", 8),
        ("Fecha", 13),
        ("Hora Inicio", 13),
        ("Hora Fin", 13),
        ("Total Horas", 13),
        ("Disponibilidad", 18),
        ("Detalle Disp.", 22),
        ("Actividad Realizada", 35),
        ("Observaciones", 35),
        ("Estado", 14),
        ("Voluntario", 28),
        ("Documento Voluntario", 20),
        ("Perfil Voluntario", 20),
        ("Fecha Registro", 20),
        ("Avalado Por", 28),
        ("Documento Avalador", 20),
        ("Fecha Aval", 20)
    ]

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="185999")
    thin_border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1")
    )
    align_center = Alignment(horizontal="center", vertical="center")
    align_left = Alignment(horizontal="left", vertical="center")

    ws.row_dimensions[4].height = 26
    for col_idx, (header_text, _) in enumerate(headers, 1):
        cell = ws.cell(row=4, column=col_idx, value=header_text)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center
        cell.border = thin_border

    fill_white = PatternFill("solid", fgColor="FFFFFF")
    fill_zebra = PatternFill("solid", fgColor="F8FAFC")

    font_avalado = Font(name="Calibri", size=10, bold=True, color="065F46")
    fill_avalado = PatternFill("solid", fgColor="D1FAE5")
    font_anulado = Font(name="Calibri", size=10, bold=True, color="991B1B")
    fill_anulado = PatternFill("solid", fgColor="FEE2E2")
    font_pendiente = Font(name="Calibri", size=10, bold=True, color="92400E")
    fill_pendiente = PatternFill("solid", fgColor="FEF3C7")

    data_font = Font(name="Calibri", size=10)

    for row_idx, r in enumerate(registros, 5):
        ws.row_dimensions[row_idx].height = 22
        current_fill = fill_zebra if row_idx % 2 == 0 else fill_white

        row_values = [
            r.get("id"),
            r.get("fecha"),
            r.get("hora_inicio"),
            r.get("hora_fin"),
            r.get("total_horas"),
            r.get("disponibilidad"),
            r.get("disponibilidad_otro") or "—",
            r.get("actividad_realizada"),
            r.get("observaciones") or "—",
            r.get("estado") or "Pendiente",
            r.get("registrado_por"),
            r.get("registrado_por_identificacion"),
            r.get("perfil_registrador") or "—",
            r.get("fecha_registro"),
            r.get("avalado_por") or "—",
            r.get("avalado_por_identificacion") or "—",
            r.get("fecha_aval") or "—"
        ]

        for col_idx, val in enumerate(row_values, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val if val is not None else "—")
            cell.font = data_font
            cell.border = thin_border
            cell.fill = current_fill

            if col_idx in (1, 2, 3, 4, 5, 10, 12, 14, 16, 17):
                cell.alignment = align_center
            else:
                cell.alignment = align_left

            if col_idx == 10:
                estado = str(val).strip()
                if estado == "Avalado":
                    cell.font = font_avalado
                    cell.fill = fill_avalado
                elif estado in ("Anulado", "Inactivo"):
                    cell.font = font_anulado
                    cell.fill = fill_anulado
                else:
                    cell.font = font_pendiente
                    cell.fill = fill_pendiente

    for col_idx, (_, width) in enumerate(headers, 1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = width

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    fecha_archivo = datetime.now().strftime("%Y%m%d")
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Reportes_Voluntariado_{fecha_archivo}.xlsx"
    )

@routes_voluntariado.route('/voluntariado/imprimir/<int:record_id>')
def imprimir_voluntariado(record_id):
    if not check_permission():
        return "Acceso denegado"
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registro_voluntariado WHERE id = %s", (record_id,))
    registro = cursor.fetchone()
    
    if registro and type(registro) is tuple:
        cols = [column[0] for column in cursor.description]
        registro = dict(zip(cols, registro))
    
    if not registro:
        conn.close()
        return "Registro no encontrado"
        
    if not is_admin_vol() and registro['registrado_por_identificacion'] != session['usuario'].get('identificacion'):
        conn.close()
        return "No tienes permiso para ver este registro"

    # Obtener firma actualizada del registrador desde la tabla usuarios
    firma_registrador = registro.get('firma_registrador', '')
    ident_reg = registro.get('registrado_por_identificacion', '')
    if ident_reg:
        u_reg = conn.execute("SELECT firma FROM usuarios WHERE identificacion = ?", (ident_reg,)).fetchone()
        if u_reg and u_reg['firma']:
            firma_registrador = u_reg['firma']

    # Obtener firma actualizada del avalador desde la tabla usuarios
    firma_avalador = registro.get('firma_avalador', '')
    ident_aval = registro.get('avalado_por_identificacion', '')
    if ident_aval:
        u_aval = conn.execute("SELECT firma FROM usuarios WHERE identificacion = ?", (ident_aval,)).fetchone()
        if u_aval and u_aval['firma']:
            firma_avalador = u_aval['firma']

    cfg = get_configuracion()
    conn.close()
    
    return render_template('imprimir_voluntariado.html',
                           registro=registro,
                           cfg=cfg,
                           firma_registrador=firma_registrador,
                           firma_avalador=firma_avalador)

def register_routes(app):
    app.register_blueprint(routes_voluntariado)
