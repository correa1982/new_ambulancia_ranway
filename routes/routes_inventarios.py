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
    items_raw = conn.execute("SELECT * FROM inventarios ORDER BY tipo, nombre").fetchall()
    catalogo = conn.execute("SELECT * FROM inventarios_catalogo ORDER BY nombre").fetchall()
    conn.close()
    
    # Pre-calculate max quantity for each product name
    max_quantities = {}
    for row in items_raw:
        nombre = row['nombre']
        qty = row['cantidad']
        if nombre not in max_quantities:
            max_quantities[nombre] = qty
        elif qty > max_quantities[nombre]:
            max_quantities[nombre] = qty
            
    items = []
    seen_zero_names = set()
    for row in items_raw:
        item = dict(row)
        
        if item.get('fecha_vencimiento') and hasattr(item['fecha_vencimiento'], 'strftime'):
            item['fecha_vencimiento'] = item['fecha_vencimiento'].strftime('%Y-%m-%d')
            
        nombre = item['nombre']
        
        if item['cantidad'] == 0:
            if max_quantities.get(nombre, 0) > 0:
                # Hide this lot because there is another lot with quantity > 0
                continue
            else:
                # No lots have quantity > 0. Show this one but without lot and expiration date
                item['lote'] = ''
                item['fecha_vencimiento'] = ''
                # Only show one entry if there are multiple 0-quantity lots for the same product
                if nombre in seen_zero_names:
                    continue
                seen_zero_names.add(nombre)
                
        items.append(item)
        
    return render_template('inventarios.html', items=items, catalogo=catalogo)

@bp_inventarios.route('/catalogo/add', methods=['POST'])
def catalogo_add():
    nombre = request.form.get('nombre', '').strip().upper()
    tipo = request.form.get('tipo', '')
    invima = request.form.get('invima', '')
    cum = request.form.get('cum', '')
    
    if not nombre:
        flash("El nombre es requerido.", "error")
        return redirect(url_for('inventarios.inventarios_index'))
        
    conn = get_db()
    existing = conn.execute("SELECT id FROM inventarios_catalogo WHERE nombre = %s AND invima = %s", (nombre, invima)).fetchone()
    if existing:
        conn.close()
        flash("Este ítem ya existe en el catálogo con el mismo registro Invima.", "error")
        return redirect(url_for('inventarios.inventarios_index'))
        
    conn.execute("INSERT INTO inventarios_catalogo (nombre, tipo, invima, cum) VALUES (%s, %s, %s, %s)", (nombre, tipo, invima, cum))
    conn.commit()
    conn.close()
    
    flash("Ítem agregado al catálogo exitosamente.", "success")
    return redirect(url_for('inventarios.inventarios_index'))

@bp_inventarios.route('/catalogo/edit/<int:item_id>', methods=['POST'])
def catalogo_edit(item_id):
    nombre = request.form.get('nombre', '').strip().upper()
    tipo = request.form.get('tipo', '')
    invima = request.form.get('invima', '')
    cum = request.form.get('cum', '')
    
    if not nombre:
        flash("El nombre es requerido.", "error")
        return redirect(url_for('inventarios.inventarios_index'))
        
    conn = get_db()
    existing = conn.execute("SELECT id FROM inventarios_catalogo WHERE nombre = %s AND invima = %s AND id != %s", (nombre, invima, item_id)).fetchone()
    if existing:
        conn.close()
        flash("Este ítem ya existe en el catálogo con el mismo registro Invima.", "error")
        return redirect(url_for('inventarios.inventarios_index'))
        
    conn.execute("UPDATE inventarios_catalogo SET nombre = %s, tipo = %s, invima = %s, cum = %s WHERE id = %s", (nombre, tipo, invima, cum, item_id))
    conn.commit()
    conn.close()
    
    flash("Ítem del catálogo actualizado exitosamente.", "success")
    return redirect(url_for('inventarios.inventarios_index'))

@bp_inventarios.route('/catalogo/delete/<int:item_id>', methods=['POST'])
def catalogo_delete(item_id):
    conn = get_db()
    conn.execute("DELETE FROM inventarios_catalogo WHERE id = %s", (item_id,))
    conn.commit()
    conn.close()
    
    flash("Ítem eliminado del catálogo.", "success")
    return redirect(url_for('inventarios.inventarios_index'))


@bp_inventarios.route('/add', methods=['POST'])
def inventarios_add():
    codigo_barras = request.form.get('codigo_barras', '')
    codigo_secundario = request.form.get('codigo_secundario', '')
    tipo = request.form.get('tipo')
    nombre = request.form.get('nombre')
    invima = request.form.get('invima', '')
    cum = request.form.get('cum', '')
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
            flash("El código principal ya está asignado a otro producto.", "error")
            return redirect(url_for('inventarios.inventarios_index'))
    if codigo_secundario:
        existing = conn.execute("SELECT id FROM inventarios WHERE codigo_secundario = %s", (codigo_secundario,)).fetchone()
        if existing:
            flash("El código secundario ya está asignado a otro producto.", "error")
            return redirect(url_for('inventarios.inventarios_index'))

    conn.execute("""
        INSERT INTO inventarios (codigo_barras, codigo_secundario, tipo, nombre, invima, cum, cantidad, unidad_medida, lote, fecha_vencimiento, observaciones, registrado_por)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (codigo_barras, codigo_secundario, tipo, nombre, invima, cum, cantidad, unidad_medida, lote, fecha_vencimiento, observaciones, registrado_por))
    conn.commit()
    conn.close()
    
    flash("Ítem agregado exitosamente.", "success")
    return redirect(url_for('inventarios.inventarios_index'))

@bp_inventarios.route('/edit/<int:item_id>', methods=['POST'])
def inventarios_edit(item_id):
    codigo_barras = request.form.get('codigo_barras', '')
    codigo_secundario = request.form.get('codigo_secundario', '')
    tipo = request.form.get('tipo')
    nombre = request.form.get('nombre')
    invima = request.form.get('invima', '')
    cum = request.form.get('cum', '')
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
            flash("El código principal ya está asignado a otro producto.", "error")
            return redirect(url_for('inventarios.inventarios_index'))
            
    if codigo_secundario:
        existing = conn.execute("SELECT id FROM inventarios WHERE codigo_secundario = %s AND id != %s", (codigo_secundario, item_id)).fetchone()
        if existing:
            flash("El código secundario ya está asignado a otro producto.", "error")
            return redirect(url_for('inventarios.inventarios_index'))

    conn.execute("""
        UPDATE inventarios 
        SET codigo_barras = %s, codigo_secundario = %s, tipo = %s, nombre = %s, invima = %s, cum = %s, cantidad = %s, unidad_medida = %s, lote = %s, fecha_vencimiento = %s, observaciones = %s
        WHERE id = %s
    """, (codigo_barras, codigo_secundario, tipo, nombre, invima, cum, cantidad, unidad_medida, lote, fecha_vencimiento, observaciones, item_id))
    
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
            items = conn.execute("SELECT * FROM inventarios WHERE (codigo_barras = %s OR codigo_secundario = %s) AND cantidad > 0", (codigo, codigo)).fetchall()
            # If none have stock > 0, maybe just fetch one to show insufficient stock error
            if not items:
                items = conn.execute("SELECT * FROM inventarios WHERE codigo_barras = %s OR codigo_secundario = %s", (codigo, codigo)).fetchmany(1)
        else:
            items = conn.execute("SELECT * FROM inventarios WHERE codigo_barras = %s OR codigo_secundario = %s", (codigo, codigo)).fetchall()

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

@bp_inventarios.route('/scan/info', methods=['POST'])
def inventarios_scan_info():
    codigo = request.form.get('codigo_barras')
    conn = get_db()
    items = conn.execute("SELECT * FROM inventarios WHERE codigo_barras = %s OR codigo_secundario = %s", (codigo, codigo)).fetchall()
    conn.close()
    
    if not items:
        return jsonify({
            "status": "not_found", 
            "message": "Producto no encontrado. Registre este nuevo producto a continuación.",
            "is_new": True,
            "codigo": codigo
        })
    
    batches_list = []
    for item in items:
        b_dict = dict(item)
        if b_dict.get('fecha_vencimiento') and hasattr(b_dict['fecha_vencimiento'], 'strftime'):
            b_dict['fecha_vencimiento'] = b_dict['fecha_vencimiento'].strftime('%Y-%m-%d')
        elif b_dict.get('fecha_vencimiento') and isinstance(b_dict['fecha_vencimiento'], str):
            # Try to handle strings if any
            try:
                # If it's already a string in some other format, try to format it, or leave as is if it's YYYY-MM-DD
                if len(b_dict['fecha_vencimiento']) > 10:
                    import datetime
                    # simple fallback if it's not YYYY-MM-DD
                    pass
            except Exception:
                pass
        batches_list.append(b_dict)

    return jsonify({
        "status": "success",
        "product": {
            "nombre": items[0]['nombre'],
            "tipo": items[0]['tipo'],
            "invima": items[0]['invima'],
            "cum": items[0]['cum']
        },
        "batches": batches_list
    })

@bp_inventarios.route('/scan/process_ingreso', methods=['POST'])
def inventarios_scan_process_ingreso():
    try:
        codigo = request.form.get('codigo_barras')
        item_id = request.form.get('item_id')
        cantidad = int(request.form.get('cantidad', 1))
        nuevo_lote = request.form.get('nuevo_lote')
        fecha_vencimiento = request.form.get('fecha_vencimiento')
        
        # Convert empty strings to None to avoid MySQL strict mode errors
        if not fecha_vencimiento:
            fecha_vencimiento = None
            
        registrado_por = session['usuario']['nombre']
        
        conn = get_db()
        
        if item_id == 'nuevo_lote':
            # Get base product info
            base_item = conn.execute("SELECT * FROM inventarios WHERE codigo_barras = %s OR codigo_secundario = %s LIMIT 1", (codigo, codigo)).fetchone()
            if not base_item:
                conn.close()
                return jsonify({"status": "error", "message": "Producto base no encontrado."})
                
            if not nuevo_lote and base_item['tipo'] not in ['Cosméticos y Aseo', 'Material Esteril']:
                conn.close()
                return jsonify({"status": "error", "message": "Debe especificar un número de lote."})
                
            cursor = conn.execute("""
                INSERT INTO inventarios (codigo_barras, codigo_secundario, tipo, nombre, invima, cum, cantidad, unidad_medida, lote, fecha_vencimiento, observaciones)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (base_item['codigo_barras'], base_item['codigo_secundario'], base_item['tipo'], base_item['nombre'], base_item['invima'], base_item['cum'], cantidad, base_item['unidad_medida'], nuevo_lote, fecha_vencimiento, base_item['observaciones']))
            new_id = cursor.lastrowid
            
            # Log to history
            conn.execute("""
                INSERT INTO inventarios_historial 
                (item_id, codigo_barras, nombre, lote, accion, cantidad, registrado_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (new_id, codigo, base_item['nombre'], nuevo_lote, 'ingreso', cantidad, registrado_por))
            
            message = f"Se ha añadido {cantidad} del producto '{base_item['nombre']}' con nuevo lote '{nuevo_lote}'."
        else:
            item = conn.execute("SELECT * FROM inventarios WHERE id = %s", (item_id,)).fetchone()
            if not item:
                conn.close()
                return jsonify({"status": "error", "message": "Lote no encontrado."})
                
            nueva_cantidad = item['cantidad'] + cantidad
            conn.execute("UPDATE inventarios SET cantidad = %s WHERE id = %s", (nueva_cantidad, item_id))
            
            # Log to history
            conn.execute("""
                INSERT INTO inventarios_historial 
                (item_id, codigo_barras, nombre, lote, accion, cantidad, registrado_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (item_id, codigo, item['nombre'], item['lote'], 'ingreso', cantidad, registrado_por))
            
            message = f"Se ha añadido {cantidad} al lote '{item['lote']}' del producto '{item['nombre']}'. Nuevo stock: {nueva_cantidad}."
            
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success", "message": message})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error interno: {str(e)}"})

@bp_inventarios.route('/manual_update', methods=['POST'])
def inventarios_manual_update():
    item_id_raw = request.form.get('item_id', '')
    accion = request.form.get('accion') # 'ingreso' o 'egreso'
    cantidad_op = int(request.form.get('cantidad', 1))
    tipo_egreso = request.form.get('tipo_egreso', '')
    destino = request.form.get('destino', '')
    lote = request.form.get('lote', '')
    fecha_vencimiento = request.form.get('fecha_vencimiento')

    if not fecha_vencimiento:
        fecha_vencimiento = None

    conn = get_db()
    
    is_catalog = item_id_raw.startswith('cat_')
    real_id = item_id_raw.replace('inv_', '').replace('cat_', '')
    
    if is_catalog:
        if accion == 'egreso':
            flash("No puede hacer egreso de un producto que aún no está en el inventario.", "error")
            return redirect(url_for('inventarios.inventarios_index'))
            
        cat_item = conn.execute("SELECT * FROM inventarios_catalogo WHERE id = %s", (real_id,)).fetchone()
        if not cat_item:
            flash("Producto de catálogo no encontrado.", "error")
            return redirect(url_for('inventarios.inventarios_index'))
            
        registrado_por = session['usuario']['nombre']
        cursor = conn.execute("""
            INSERT INTO inventarios (codigo_barras, codigo_secundario, tipo, nombre, invima, cum, cantidad, unidad_medida, lote, fecha_vencimiento, observaciones, registrado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, ('', '', cat_item['tipo'], cat_item['nombre'], cat_item['invima'], cat_item['cum'], cantidad_op, 'Unidades', lote, fecha_vencimiento, '', registrado_por))
        new_id = cursor.lastrowid
        
        conn.execute("""
            INSERT INTO inventarios_historial 
            (item_id, codigo_barras, nombre, lote, accion, cantidad, tipo_egreso, destino, registrado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            new_id, '', cat_item['nombre'], lote, 
            accion, cantidad_op, '', '', registrado_por
        ))
        conn.commit()
        conn.close()
        flash(f"Producto '{cat_item['nombre']}' ingresado desde el catálogo exitosamente. Stock: {cantidad_op}", "success")
        return redirect(url_for('inventarios.inventarios_index'))

    item = conn.execute("SELECT * FROM inventarios WHERE id = %s", (real_id,)).fetchone()
    
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
    items = conn.execute("SELECT codigo_barras, nombre, tipo, invima, cum, lote, fecha_vencimiento, cantidad, unidad_medida, observaciones FROM inventarios ORDER BY tipo, nombre").fetchall()
    conn.close()
    
    data = []
    for item in items:
        data.append({
            "Código de Barras": item['codigo_barras'] or '',
            "Nombre": item['nombre'],
            "Tipo": item['tipo'],
            "Registro Invima": item['invima'] or '',
            "CUM": item['cum'] or '',
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
