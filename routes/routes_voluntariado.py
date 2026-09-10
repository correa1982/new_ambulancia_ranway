from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from db import get_db

routes_voluntariado = Blueprint('voluntariado', __name__)

def check_permission():
    if 'usuario' not in session:
        return False
    # Para acceder al form de registros
    formularios = session['usuario'].get('formularios_acceso', [])
    return 'voluntariado' in formularios or 'voluntariado_admin' in formularios or session['usuario'].get('rol') == 'admin'

def is_admin_vol():
    if 'usuario' not in session:
        return False
    return 'voluntariado_admin' in session['usuario'].get('formularios_acceso', []) or session['usuario'].get('rol') == 'admin'

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
