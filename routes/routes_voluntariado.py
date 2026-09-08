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
    cursor.execute("SELECT * FROM configuracion ORDER BY id DESC LIMIT 1")
    # Para obtener un diccionario (usamos conn.cursor(dictionary=True) no está disponible en este wrapper, así que obtenemos los nombres de columnas manual si falla, o usamos el index)
    # Sin embargo, el CustomConnection de este repo tiene un método execute o devuelve un cursor mysql?
    cfg = cursor.fetchone()
    conn.close()
    if cfg:
        # Si es tuple, lo convertimos (sabemos que id, logo_url son columnas). Para simplificar, mejor retornamos dict si es posible.
        pass
    return cfg

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
        cursor.execute("SELECT * FROM registro_voluntariado WHERE estado != 'Inactivo' ORDER BY id DESC")
        registros = cursor.fetchall()
    else:
        ident = session['usuario'].get('identificacion')
        cursor.execute("SELECT * FROM registro_voluntariado WHERE registrado_por_identificacion = %s AND estado != 'Inactivo' ORDER BY id DESC", (ident,))
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

@routes_voluntariado.route('/voluntariado/estadisticas')
def estadisticas_voluntariado():
    if not is_admin_vol():
        flash("Solo administradores pueden ver estadísticas.", "danger")
        return redirect(url_for('voluntariado.registros_voluntariado'))
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT total_horas, registrado_por FROM registro_voluntariado WHERE estado = 'Avalado'")
    registros = cursor.fetchall()
    conn.close()
    
    if registros and type(registros[0]) is tuple:
        cols = [column[0] for column in cursor.description]
        registros = [dict(zip(cols, row)) for row in registros]
    elif registros and type(registros[0]) is not dict:
        registros = [dict(r) for r in registros]
    
    # Calcular total horas y agrupar por usuario
    total_minutos = 0
    stats_usuarios = {}
    
    for r in registros:
        horas_str = r.get('total_horas', '0:0')
        usuario = r.get('registrado_por', 'Desconocido')
        
        if usuario not in stats_usuarios:
            stats_usuarios[usuario] = {'cantidad': 0, 'minutos': 0}
            
        stats_usuarios[usuario]['cantidad'] += 1
        
        mins = 0
        if horas_str and ':' in horas_str:
            try:
                h, m = map(int, horas_str.split(':'))
                mins = h * 60 + m
                total_minutos += mins
            except:
                pass
        
        stats_usuarios[usuario]['minutos'] += mins
                
    horas_totales = total_minutos // 60
    minutos_restantes = total_minutos % 60
    total_str = f"{horas_totales}:{minutos_restantes:02d}"
    
    # Format user stats
    for u in stats_usuarios:
        m = stats_usuarios[u]['minutos']
        stats_usuarios[u]['horas_str'] = f"{m // 60}:{m % 60:02d}"
    
    return render_template('estadisticas_voluntariado.html', 
                           total_horas=total_str,
                           total_registros=len(registros),
                           stats_usuarios=stats_usuarios)

@routes_voluntariado.route('/voluntariado/imprimir/<int:record_id>')
def imprimir_voluntariado(record_id):
    if not check_permission():
        return "Acceso denegado"
        
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM registro_voluntariado WHERE id = %s", (record_id,))
    registro = cursor.fetchone()
    conn.close()
    
    if registro and type(registro) is tuple:
        cols = [column[0] for column in cursor.description]
        registro = dict(zip(cols, registro))
    
    if not registro:
        return "Registro no encontrado"
        
    if not is_admin_vol() and registro['registrado_por_identificacion'] != session['usuario'].get('identificacion'):
        return "No tienes permiso para ver este registro"
        
    cfg = get_configuracion()
    return render_template('imprimir_voluntariado.html', registro=registro, cfg=cfg)

def register_routes(app):
    app.register_blueprint(routes_voluntariado)
