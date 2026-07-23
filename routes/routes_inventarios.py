from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import io
import pandas as pd
from db import get_db
from utils import login_required

bp_inventarios = Blueprint('inventarios', __name__, url_prefix='/inventarios')

def has_inventarios_access():
    if not session.get('usuario'):
        return False
    if session['usuario'].get('rol') == 'admin':
        return True
    
    acceso = session['usuario'].get('formularios_acceso', [])
    if isinstance(acceso, str):
        import json
        try:
            acceso = json.loads(acceso)
        except:
            acceso = []
            
    # Formularios de acceso can be a list or a dict by profile
    if isinstance(acceso, dict):
        # Flatten all values
        flat_list = []
        for v in acceso.values():
            if isinstance(v, list):
                flat_list.extend(v)
        acceso = flat_list

    return 'inventarios' in acceso

@bp_inventarios.before_request
@login_required
def check_access():
    if not has_inventarios_access():
        flash("No tiene permisos para acceder al Módulo de Inventarios.", "error")
        return redirect(url_for('dashboard'))

@bp_inventarios.route('/', methods=['GET'])
def inventarios_index():
    conn = get_db()
    items = conn.execute("SELECT * FROM inventarios ORDER BY tipo, nombre").fetchall()
    conn.close()
    return render_template('inventarios.html', items=items)

@bp_inventarios.route('/add', methods=['POST'])
def inventarios_add():
    codigo_barras = request.form.get('codigo_barras', '')
    tipo = request.form.get('tipo')
    nombre = request.form.get('nombre')
    invima = request.form.get('invima', '')
    cantidad = int(request.form.get('cantidad', 0))
    unidad_medida = request.form.get('unidad_medida', 'Unidades')
    lote = request.form.get('lote', '')
    fecha_vencimiento = request.form.get('fecha_vencimiento')
    observaciones = request.form.get('observaciones', '')
    
    if not fecha_vencimiento:
        fecha_vencimiento = None
        
    registrado_por = session['usuario']['nombre']
    
    conn = get_db()
    # Check if barcode already exists
    if codigo_barras:
        existing = conn.execute("SELECT id FROM inventarios WHERE codigo_barras = %s", (codigo_barras,)).fetchone()
        if existing:
            flash("El código de barras ya está asignado a otro producto.", "error")
            return redirect(url_for('inventarios.inventarios_index'))

    conn.execute("""
        INSERT INTO inventarios (codigo_barras, tipo, nombre, invima, cantidad, unidad_medida, lote, fecha_vencimiento, observaciones, registrado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (codigo_barras, tipo, nombre, invima, cantidad, unidad_medida, lote, fecha_vencimiento, observaciones, registrado_por))
    conn.commit()
    conn.close()
    
    flash("Ítem agregado exitosamente.", "success")
    return redirect(url_for('inventarios.inventarios_index'))

@bp_inventarios.route('/edit/<int:item_id>', methods=['POST'])
def inventarios_edit(item_id):
    codigo_barras = request.form.get('codigo_barras', '')
    tipo = request.form.get('tipo')
    nombre = request.form.get('nombre')
    invima = request.form.get('invima', '')
    cantidad = int(request.form.get('cantidad', 0))
    unidad_medida = request.form.get('unidad_medida', 'Unidades')
    lote = request.form.get('lote', '')
    fecha_vencimiento = request.form.get('fecha_vencimiento')
    observaciones = request.form.get('observaciones', '')
    
    if not fecha_vencimiento:
        fecha_vencimiento = None
        
    conn = get_db()
    if codigo_barras:
        existing = conn.execute("SELECT id FROM inventarios WHERE codigo_barras = %s AND id != %s", (codigo_barras, item_id)).fetchone()
        if existing:
            flash("El código de barras ya está asignado a otro producto.", "error")
            return redirect(url_for('inventarios.inventarios_index'))

    conn.execute("""
        UPDATE inventarios 
        SET codigo_barras=%s, tipo=%s, nombre=%s, invima=%s, cantidad=%s, unidad_medida=%s, lote=%s, fecha_vencimiento=%s, observaciones=%s
        WHERE id=%s
    """, (codigo_barras, tipo, nombre, invima, cantidad, unidad_medida, lote, fecha_vencimiento, observaciones, item_id))
    conn.commit()
    conn.close()
    
    flash("Ítem actualizado exitosamente.", "success")
    return redirect(url_for('inventarios.inventarios_index'))

@bp_inventarios.route('/scan', methods=['POST'])
def inventarios_scan():
    codigo = request.form.get('codigo_barras')
    accion = request.form.get('accion') # 'ingreso' o 'egreso' o 'nuevo'
    cantidad_op = int(request.form.get('cantidad', 1))
    tipo_egreso = request.form.get('tipo_egreso', '')
    destino = request.form.get('destino', '')
    item_id = request.form.get('item_id')

    conn = get_db()
    
    if item_id:
        # User selected a specific batch
        item = conn.execute("SELECT * FROM inventarios WHERE id = %s", (item_id,)).fetchone()
        items = [item] if item else []
    else:
        if accion == 'egreso':
            # For egress, find batches with stock > 0
            items = conn.execute("SELECT * FROM inventarios WHERE codigo_barras = %s AND cantidad > 0", (codigo,)).fetchall()
            # If none have stock > 0, maybe just fetch one to show insufficient stock error
            if not items:
                items = conn.execute("SELECT * FROM inventarios WHERE codigo_barras = %s", (codigo,)).fetchmany(1)
        else:
            items = conn.execute("SELECT * FROM inventarios WHERE codigo_barras = %s", (codigo,)).fetchall()

    if not items:
        conn.close()
        return jsonify({
            "status": "error", 
            "message": "Producto no encontrado. Registre este nuevo producto a continuación.",
            "is_new": True,
            "codigo": codigo
        })

    if accion == 'egreso' and len(items) > 1 and not item_id:
        conn.close()
        return jsonify({
            "status": "multiple_batches",
            "message": "Múltiples lotes encontrados. Seleccione uno.",
            "items": [dict(item) for item in items]
        })

    item = items[0]
    nueva_cantidad = item['cantidad']
    
    if accion == 'ingreso':
        nueva_cantidad += cantidad_op
    elif accion == 'egreso':
        nueva_cantidad -= cantidad_op
        if nueva_cantidad < 0:
            conn.close()
            return jsonify({"status": "error", "message": f"Inventario insuficiente. Stock actual: {item['cantidad']}"})
    elif accion == 'nuevo':
        conn.close()
        return jsonify({"status": "error", "message": "El producto ya está registrado en el sistema."})
    else:
        conn.close()
        return jsonify({"status": "error", "message": "Acción inválida."})

    registrado_por = session['usuario']['nombre']
    
    conn.execute("UPDATE inventarios SET cantidad = %s WHERE id = %s", (nueva_cantidad, item['id']))
    
    # Log to history
    conn.execute("""
        INSERT INTO inventarios_historial 
        (item_id, codigo_barras, nombre, lote, accion, cantidad, tipo_egreso, destino, registrado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        item['id'], item.get('codigo_barras', ''), item['nombre'], item.get('lote', ''), 
        accion, cantidad_op, tipo_egreso if accion == 'egreso' else '', 
        destino if accion == 'egreso' else '', registrado_por
    ))
    
    conn.commit()
    conn.close()

    operacion = "añadido" if accion == 'ingreso' else "retirado"
    return jsonify({"status": "success", "message": f"Se ha {operacion} {cantidad_op} del producto '{item['nombre']}'. Nuevo stock: {nueva_cantidad}"})

@bp_inventarios.route('/manual_update', methods=['POST'])
def inventarios_manual_update():
    item_id = request.form.get('item_id')
    accion = request.form.get('accion') # 'ingreso' o 'egreso'
    cantidad_op = int(request.form.get('cantidad', 1))
    tipo_egreso = request.form.get('tipo_egreso', '')
    destino = request.form.get('destino', '')

    conn = get_db()
    item = conn.execute("SELECT * FROM inventarios WHERE id = %s", (item_id,)).fetchone()
    
    if not item:
        flash("Producto no encontrado.", "error")
        return redirect(url_for('inventarios.inventarios_index'))

    nueva_cantidad = item['cantidad']
    if accion == 'ingreso':
        nueva_cantidad += cantidad_op
    elif accion == 'egreso':
        nueva_cantidad -= cantidad_op
        if nueva_cantidad < 0:
            flash(f"Inventario insuficiente. Stock actual: {item['cantidad']}", "error")
            return redirect(url_for('inventarios.inventarios_index'))

    registrado_por = session['usuario']['nombre']
    
    conn.execute("UPDATE inventarios SET cantidad = %s WHERE id = %s", (nueva_cantidad, item['id']))
    
    # Log to history
    conn.execute("""
        INSERT INTO inventarios_historial 
        (item_id, codigo_barras, nombre, lote, accion, cantidad, tipo_egreso, destino, registrado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        item['id'], item.get('codigo_barras', ''), item['nombre'], item.get('lote', ''), 
        accion, cantidad_op, tipo_egreso if accion == 'egreso' else '', 
        destino if accion == 'egreso' else '', registrado_por
    ))
    
    conn.commit()
    conn.close()

    flash(f"Stock actualizado. Nuevo stock de '{item['nombre']}': {nueva_cantidad}", "success")
    return redirect(url_for('inventarios.inventarios_index'))

@bp_inventarios.route('/delete/<int:item_id>', methods=['POST'])
def inventarios_delete(item_id):
    conn = get_db()
    conn.execute("DELETE FROM inventarios WHERE id=%s", (item_id,))
    conn.commit()
    conn.close()
    
    flash("Ítem eliminado exitosamente.", "success")
    return redirect(url_for('inventarios.inventarios_index'))
@bp_inventarios.route('/exportar_excel', methods=['GET'])
def inventarios_exportar_excel():
    conn = get_db()
    items = conn.execute("SELECT codigo_barras, nombre, tipo, invima, lote, fecha_vencimiento, cantidad, unidad_medida, observaciones FROM inventarios ORDER BY tipo, nombre").fetchall()
    conn.close()
    
    data = []
    for item in items:
        data.append({
            "Código de Barras": item['codigo_barras'] or '',
            "Nombre": item['nombre'],
            "Tipo": item['tipo'],
            "Registro Invima": item['invima'] or '',
            "Lote": item['lote'] or '',
            "Fecha Vencimiento": item['fecha_vencimiento'] or '',
            "Cantidad": item['cantidad'],
            "Unidad de Medida": item['unidad_medida'] or '',
            "Observaciones": item['observaciones'] or ''
        })
        
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Inventarios", index=False)
        
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="Reporte_Inventarios.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
@bp_inventarios.route('/movimientos', methods=['GET'])
def inventarios_movimientos():
    conn = get_db()
    movimientos = conn.execute("SELECT * FROM inventarios_historial ORDER BY fecha_registro DESC").fetchall()
    conn.close()
    return render_template('inventarios_movimientos.html', movimientos=movimientos)

@bp_inventarios.route('/movimientos/exportar', methods=['GET'])
def inventarios_movimientos_exportar():
    conn = get_db()
    movimientos = conn.execute("SELECT * FROM inventarios_historial ORDER BY fecha_registro DESC").fetchall()
    conn.close()
    
    data = []
    for mov in movimientos:
        fecha_str = mov['fecha_registro'].strftime('%Y-%m-%d %H:%M:%S') if mov['fecha_registro'] else 'N/A'
        data.append({
            "Fecha / Hora": fecha_str,
            "Producto": mov['nombre'],
            "Código de Barras": mov['codigo_barras'] or '',
            "Lote": mov['lote'] or '',
            "Acción": "Ingreso" if mov['accion'] == 'ingreso' else "Egreso",
            "Cantidad": mov['cantidad'],
            "Tipo de Egreso": mov['tipo_egreso'] or '',
            "Destino": mov['destino'] or '',
            "Responsable": mov['registrado_por'] or 'Sistema'
        })
        
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name="Movimientos", index=False)
        
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="Reporte_Movimientos_Inventario.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
def register_routes(app):
    app.register_blueprint(bp_inventarios)
