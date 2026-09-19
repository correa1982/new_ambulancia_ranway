from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, send_file
import io
import pandas as pd
import zoneinfo
from datetime import datetime
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

def obtener_alertas_unidades_operativas(conn, hoy):
    """
    Obtiene los artículos vencidos y próximos a vencer (<= 30 días)
    desde el checklist finalizado más reciente de cada unidad operativa:
    - PASB (por pasb_numero)
    - PASM (por pasm_numero)
    - Botiquín de Avanzada (por botiquin)
    - Ambulancia TAM (por placa)
    - Ambulancia TAB (por placa)
    """
    import json
    from datetime import date
    
    vencidos = []
    proximos = []
    
    configs = [
        {
            "tipo_key": "pasb",
            "ubicacion_tipo": "PASB",
            "badge_class": "badge-pasb",
            "label_template": "PASB ({})",
            "query": """
                SELECT c.id, c.pasb_numero AS unit_id, c.datos_json, c.ubicacion, c.fecha
                FROM checklist_pasb c
                INNER JOIN (
                    SELECT pasb_numero, MAX(id) AS max_id
                    FROM checklist_pasb
                    WHERE finalizado = 1 AND pasb_numero IS NOT NULL AND TRIM(pasb_numero) != ''
                    GROUP BY pasb_numero
                ) latest ON c.id = latest.max_id
            """
        },
        {
            "tipo_key": "pasm",
            "ubicacion_tipo": "PASM",
            "badge_class": "badge-pasm",
            "label_template": "PASM ({})",
            "query": """
                SELECT c.id, c.pasm_numero AS unit_id, c.datos_json, c.ubicacion, c.fecha
                FROM checklist_pasm c
                INNER JOIN (
                    SELECT pasm_numero, MAX(id) AS max_id
                    FROM checklist_pasm
                    WHERE finalizado = 1 AND pasm_numero IS NOT NULL AND TRIM(pasm_numero) != ''
                    GROUP BY pasm_numero
                ) latest ON c.id = latest.max_id
            """
        },
        {
            "tipo_key": "avanzada",
            "ubicacion_tipo": "Botiquín Avanzada",
            "badge_class": "badge-avanzada",
            "label_template": "Avanzada ({})",
            "query": """
                SELECT c.id, c.botiquin AS unit_id, c.datos_json, c.evento, c.fecha
                FROM checklist_avanzada c
                INNER JOIN (
                    SELECT botiquin, MAX(id) AS max_id
                    FROM checklist_avanzada
                    WHERE finalizado = 1 AND botiquin IS NOT NULL AND TRIM(botiquin) != ''
                    GROUP BY botiquin
                ) latest ON c.id = latest.max_id
            """
        },
        {
            "tipo_key": "tam",
            "ubicacion_tipo": "Ambulancia TAM",
            "badge_class": "badge-tam",
            "label_template": "Ambulancia TAM ({})",
            "query": """
                SELECT c.id, c.placa AS unit_id, c.datos_json, c.fecha
                FROM checklist_tam c
                INNER JOIN (
                    SELECT UPPER(TRIM(placa)) AS placa_norm, MAX(id) AS max_id
                    FROM checklist_tam
                    WHERE finalizado = 1 AND placa IS NOT NULL AND TRIM(placa) != ''
                    GROUP BY UPPER(TRIM(placa))
                ) latest ON c.id = latest.max_id
            """
        },
        {
            "tipo_key": "tab",
            "ubicacion_tipo": "Ambulancia TAB",
            "badge_class": "badge-tab",
            "label_template": "Ambulancia TAB ({})",
            "query": """
                SELECT c.id, c.placa AS unit_id, c.datos_json, c.fecha
                FROM checklist_tab c
                INNER JOIN (
                    SELECT UPPER(TRIM(placa)) AS placa_norm, MAX(id) AS max_id
                    FROM checklist_tab
                    WHERE finalizado = 1 AND placa IS NOT NULL AND TRIM(placa) != ''
                    GROUP BY UPPER(TRIM(placa))
                ) latest ON c.id = latest.max_id
            """
        },
    ]

    for cfg in configs:
        try:
            rows = conn.execute(cfg["query"]).fetchall()
        except Exception:
            continue

        for r in rows:
            unit_id = (r.get("unit_id") or "").strip()
            if not unit_id:
                continue
            ubicacion_label = cfg["label_template"].format(unit_id)
            datos_raw = r.get("datos_json")
            if not datos_raw:
                continue

            try:
                datos = json.loads(datos_raw) if isinstance(datos_raw, str) else datos_raw
            except Exception:
                continue

            if not isinstance(datos, dict):
                continue

            for field_name, item_data in datos.items():
                if not isinstance(item_data, dict):
                    continue
                if field_name.startswith("_"):
                    continue

                nombre_articulo = item_data.get("nombre") or field_name
                raw_venc = item_data.get("fecha_vencimiento")
                if not raw_venc:
                    continue

                # Procesar múltiples lotes o string individual
                if isinstance(raw_venc, str) and raw_venc.strip().startswith("["):
                    try:
                        raw_venc = json.loads(raw_venc)
                    except Exception:
                        pass

                venc_entries = []
                if isinstance(raw_venc, list):
                    for v_item in raw_venc:
                        if isinstance(v_item, dict):
                            f_str = str(v_item.get("fecha") or "").strip()
                            if f_str:
                                try:
                                    cant_val = int(v_item.get("cant") or 1)
                                except Exception:
                                    cant_val = 1
                                venc_entries.append({
                                    "cant": cant_val,
                                    "fecha": f_str[:10],
                                    "lote": str(v_item.get("lote") or "").strip()
                                })
                elif isinstance(raw_venc, str):
                    f_str = raw_venc.strip()[:10]
                    if f_str:
                        cant_val = item_data.get("cant_actual") or item_data.get("cantidad") or 1
                        try:
                            cant_val = int(cant_val)
                        except Exception:
                            cant_val = 1
                        venc_entries.append({
                            "cant": cant_val,
                            "fecha": f_str,
                            "lote": str(item_data.get("lote") or "").strip()
                        })

                for entry in venc_entries:
                    if entry["cant"] <= 0:
                        continue
                    try:
                        fv = date.fromisoformat(entry["fecha"])
                    except Exception:
                        continue

                    dias = (fv - hoy).days
                    item_alert = {
                        "id": None,
                        "checklist_id": r.get("id"),
                        "field_key": field_name,
                        "origen": cfg["tipo_key"],
                        "ubicacion_tipo": cfg["ubicacion_tipo"],
                        "ubicacion_detalle": ubicacion_label,
                        "ubicacion_badge_class": cfg["badge_class"],
                        "nombre": nombre_articulo,
                        "lote": entry["lote"] or "N/A",
                        "cantidad": entry["cant"],
                        "fecha_vencimiento": fv.strftime('%Y-%m-%d'),
                        "dias": dias
                    }

                    if dias < 0:
                        vencidos.append(item_alert)
                    elif dias <= 30:
                        proximos.append(item_alert)

    return vencidos, proximos

@bp_inventarios.route('/', methods=['GET'])
def inventarios_index():
    conn = get_db()
    items_raw = conn.execute("SELECT * FROM inventarios ORDER BY tipo, nombre").fetchall()
    catalogo = conn.execute("SELECT * FROM inventarios_catalogo ORDER BY nombre").fetchall()
    
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
        
    is_superadmin = False
    if session.get("usuario") and session["usuario"].get("rol_real") == "admin":
        is_superadmin = True
        
    # Calcular alertas de stock mínimo
    total_stocks = {}
    for row in items_raw:
        nombre = row['nombre']
        total_stocks[nombre] = total_stocks.get(nombre, 0) + row['cantidad']
        
    min_stocks = {c['nombre']: c.get('existencia_minima', 0) for c in catalogo}
    alertas = []
    for nombre, qty in total_stocks.items():
        min_stock = min_stocks.get(nombre, 0)
        if min_stock > 0 and qty <= min_stock:
            alertas.append({
                "nombre": nombre,
                "cantidad": qty,
                "minimo": min_stock
            })

    # Calcular próximos a vencer (0-30 días) y vencidos (< 0 días) de Bodega Central
    from datetime import date
    hoy = date.today()
    proximos_vencer = []
    vencidos = []
    for row in items_raw:
        if row['cantidad'] <= 0:
            continue
        fv = row['fecha_vencimiento']
        if not fv:
            continue
        # Normalizar a date
        if hasattr(fv, 'date'):
            fv = fv.date()
        elif isinstance(fv, str):
            try:
                fv = date.fromisoformat(fv[:10])
            except Exception:
                continue
        dias = (fv - hoy).days
        entry = {
            "id": row['id'],
            "origen": "bodega",
            "ubicacion_tipo": "Bodega Central",
            "ubicacion_detalle": "Bodega Central",
            "ubicacion_badge_class": "badge-bodega",
            "nombre": row['nombre'],
            "lote": row.get('lote') or '',
            "cantidad": row['cantidad'],
            "fecha_vencimiento": fv.strftime('%Y-%m-%d'),
            "dias": dias
        }
        if dias < 0:
            vencidos.append(entry)
        elif dias <= 30:
            proximos_vencer.append(entry)

    # Consolidar alertas desde Unidades Operativas (PASB, PASM, Botiquines Avanzada, Ambulancias TAM y TAB)
    unidades_vencidos, unidades_proximos = obtener_alertas_unidades_operativas(conn, hoy)
    conn.close()

    vencidos.extend(unidades_vencidos)
    proximos_vencer.extend(unidades_proximos)

    proximos_vencer.sort(key=lambda x: x['dias'])
    vencidos.sort(key=lambda x: x['dias'])
        
    return render_template('inventarios.html', items=items, catalogo=catalogo, is_superadmin=is_superadmin,
                           alertas=alertas, proximos_vencer=proximos_vencer, vencidos=vencidos)



@bp_inventarios.route('/descarte', methods=['POST'])
def inventarios_descarte():
    """Registra el descarte/egreso de un item vencido (Bodega o Unidad Operativa)."""
    origen = request.form.get('origen', 'bodega')
    registrado_por = session.get('usuario', {}).get('nombre', 'Sistema')
    conn = get_db()
    
    if origen == 'bodega':
        item_id = request.form.get('item_id')
        if not item_id:
            conn.close()
            return jsonify({"status": "error", "message": "item_id requerido."}), 400
        item = conn.execute("SELECT * FROM inventarios WHERE id = %s", (item_id,)).fetchone()
        if not item:
            conn.close()
            return jsonify({"status": "error", "message": "Ítem no encontrado."}), 404
        cantidad_descartada = item['cantidad']
        conn.execute("UPDATE inventarios SET cantidad = 0 WHERE id = %s", (item_id,))
        conn.execute("""
            INSERT INTO inventarios_historial
            (item_id, codigo_barras, nombre, lote, accion, cantidad, tipo_egreso, destino, registrado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            item['id'], item.get('codigo_barras', ''), item['nombre'], item.get('lote', ''),
            'egreso', cantidad_descartada, 'Descarte por vencimiento', 'Baja Bodega Central', registrado_por
        ))
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "message": f"'{item['nombre']}' descartado de Bodega Central. {cantidad_descartada} unidades dadas de baja."})

    elif origen in ('pasb', 'pasm', 'avanzada', 'tam', 'tab'):
        import json
        from datetime import date
        hoy = date.today()
        
        checklist_id = request.form.get('checklist_id')
        field_key = request.form.get('field_key')
        fecha_venc_descartar = request.form.get('fecha_vencimiento', '').strip()
        nombre_art = request.form.get('nombre', '').strip()
        
        if not checklist_id or not field_key:
            conn.close()
            return jsonify({"status": "error", "message": "checklist_id y field_key son requeridos para descarte en unidades operativas."}), 400
            
        table_name = f"checklist_{origen}"
        row = conn.execute(f"SELECT * FROM {table_name} WHERE id = %s", (checklist_id,)).fetchone()
        if not row:
            conn.close()
            return jsonify({"status": "error", "message": "Checklist de la unidad no encontrado."}), 404
            
        datos_raw = row.get('datos_json')
        try:
            datos = json.loads(datos_raw) if isinstance(datos_raw, str) else (datos_raw or {})
        except Exception:
            datos = {}
            
        if field_key not in datos or not isinstance(datos[field_key], dict):
            conn.close()
            return jsonify({"status": "error", "message": "El artículo no fue encontrado en los datos del checklist."}), 404
            
        item_info = datos[field_key]
        if not nombre_art:
            nombre_art = item_info.get('nombre') or field_key
            
        # Determinar ubicación legible para trazabilidad
        ubicacion_str = f"Unidad {origen.upper()} (Checklist #{checklist_id})"
        if origen == 'pasb':
            ubicacion_str = f"PASB ({row.get('pasb_numero') or ''})"
        elif origen == 'pasm':
            ubicacion_str = f"PASM ({row.get('pasm_numero') or ''})"
        elif origen == 'avanzada':
            ubicacion_str = f"Botiquín Avanzada ({row.get('botiquin') or ''})"
        elif origen in ('tam', 'tab'):
            ubicacion_str = f"Ambulancia {origen.upper()} ({row.get('placa') or ''})"
            
        # Limpiar fecha de vencimiento:
        # Si tenía lista de lotes, remover el lote vencido (o vaciar si todos eran vencidos)
        raw_venc = item_info.get('fecha_vencimiento')
        if isinstance(raw_venc, str) and raw_venc.strip().startswith('['):
            try:
                raw_venc = json.loads(raw_venc)
            except Exception:
                pass
                
        if isinstance(raw_venc, list):
            lotes_restantes = []
            for v_lot in raw_venc:
                if isinstance(v_lot, dict):
                    f_date_str = str(v_lot.get('fecha') or '').strip()
                    try:
                        fv_d = date.fromisoformat(f_date_str[:10])
                        if fecha_venc_descartar and f_date_str[:10] == fecha_venc_descartar:
                            continue
                        elif fv_d < hoy:
                            continue
                        lotes_restantes.append(v_lot)
                    except Exception:
                        continue
            if lotes_restantes:
                item_info['fecha_vencimiento'] = lotes_restantes
            else:
                item_info['fecha_vencimiento'] = ''
                item_info['cant_actual'] = ''
        else:
            # String simple
            item_info['fecha_vencimiento'] = ''
            item_info['cant_actual'] = ''
            
        # Actualizar datos_json en la tabla de la unidad
        conn.execute(f"UPDATE {table_name} SET datos_json = %s WHERE id = %s", (json.dumps(datos, ensure_ascii=False), checklist_id))
        
        # Registrar trazabilidad en inventarios_historial si el ítem existe en inventarios
        item_match = conn.execute("SELECT id, codigo_barras, lote FROM inventarios WHERE UPPER(TRIM(nombre)) = UPPER(TRIM(%s)) LIMIT 1", (nombre_art,)).fetchone()
        if item_match:
            try:
                conn.execute("""
                    INSERT INTO inventarios_historial
                    (item_id, codigo_barras, nombre, lote, accion, cantidad, tipo_egreso, destino, registrado_por)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    item_match['id'], item_match.get('codigo_barras', ''), nombre_art, item_info.get('lote') or item_match.get('lote', ''),
                    'egreso', 0, 'Descarte por vencimiento en unidad', ubicacion_str, registrado_por
                ))
            except Exception:
                pass
        
        conn.commit()
        conn.close()
        return jsonify({
            "status": "success",
            "message": f"'{nombre_art}' en {ubicacion_str} descartado correctamente. La fecha de vencimiento quedó vacía para ser verificada en el próximo checklist."
        })
    else:
        conn.close()
        return jsonify({"status": "error", "message": "Origen no válido."}), 400

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

@bp_inventarios.route('/catalogo/update_min_stock', methods=['POST'])
def catalogo_update_min_stock():
    if not (session.get("usuario") and session["usuario"].get("rol_real") == "admin"):
        flash("No tiene permisos para realizar esta acción.", "error")
        return redirect(url_for('inventarios.inventarios_index'))
        
    conn = get_db()
    for key, value in request.form.items():
        if key.startswith('min_stock_'):
            try:
                item_id = int(key.replace('min_stock_', ''))
                min_stock = int(value)
                conn.execute("UPDATE inventarios_catalogo SET existencia_minima = %s WHERE id = %s", (min_stock, item_id))
            except Exception:
                continue
    
    conn.commit()
    conn.close()
    flash("Existencias mínimas actualizadas exitosamente.", "success")
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

    # Integración con Checklists (PASB, PASM, TAM, TAB, AVANZADA) si el destino corresponde
    if accion == 'egreso' and destino and any(p in str(destino).upper() for p in ('PASB', 'PASM', 'TAM', 'TAB', 'AVANZADA', 'BOTIQUIN')):
        conn.execute("""
            INSERT INTO checklist_pasb_traslados
            (item_inventario_id, nombre, cantidad, fecha_vencimiento, destino, estado, registrado_por)
            VALUES (%s, %s, %s, %s, %s, 'pendiente', %s)
        """, (item['id'], item['nombre'], cantidad_op, item.get('fecha_vencimiento'), destino, registrado_por))
    
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
    
    invima_form = request.form.get('invima')

    if is_catalog:
        if accion == 'egreso':
            flash("No puede hacer egreso de un producto que aún no está en el inventario.", "error")
            return redirect(url_for('inventarios.inventarios_index'))
            
        cat_item = conn.execute("SELECT * FROM inventarios_catalogo WHERE id = %s", (real_id,)).fetchone()
        if not cat_item:
            flash("Producto de catálogo no encontrado.", "error")
            return redirect(url_for('inventarios.inventarios_index'))
            
        registrado_por = session['usuario']['nombre']
        
        # Usar el invima del formulario si se proporcionó, si no usar el del catálogo
        invima_final = invima_form if invima_form is not None else cat_item['invima']
        
        cursor = conn.execute("""
            INSERT INTO inventarios (codigo_barras, codigo_secundario, tipo, nombre, invima, cum, cantidad, unidad_medida, lote, fecha_vencimiento, observaciones, registrado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, ('', '', cat_item['tipo'], cat_item['nombre'], invima_final, cat_item['cum'], cantidad_op, 'Unidades', lote, fecha_vencimiento, '', registrado_por))
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

    # Integración con Checklists (PASB, PASM, TAM, TAB, AVANZADA) si el destino corresponde
    if accion == 'egreso' and destino and any(p in str(destino).upper() for p in ('PASB', 'PASM', 'TAM', 'TAB', 'AVANZADA', 'BOTIQUIN')):
        conn.execute("""
            INSERT INTO checklist_pasb_traslados
            (item_inventario_id, nombre, cantidad, fecha_vencimiento, destino, estado, registrado_por)
            VALUES (%s, %s, %s, %s, %s, 'pendiente', %s)
        """, (item['id'], item['nombre'], cantidad_op, item.get('fecha_vencimiento'), destino, registrado_por))
    
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
    try:
        conn = get_db()
        
        page = request.args.get('page', 1, type=int)
        per_page = 50
        offset = (page - 1) * per_page
        
        row = conn.execute("""
            SELECT COUNT(ih.id) as total 
            FROM inventarios_historial ih
            LEFT JOIN inventarios i ON ih.item_id = i.id
            WHERE i.tipo != 'Control Especial' OR i.tipo IS NULL
        """).fetchone()
        total = int(row['total']) if row and row.get('total') is not None else 0
        
        movimientos_raw = conn.execute(f"""
            SELECT ih.* 
            FROM inventarios_historial ih
            LEFT JOIN inventarios i ON ih.item_id = i.id
            WHERE i.tipo != 'Control Especial' OR i.tipo IS NULL
            ORDER BY ih.fecha_registro DESC LIMIT {per_page} OFFSET {offset}
        """).fetchall()
        
        conn.close()
        
        movimientos = []
        for mov in movimientos_raw:
            mov_dict = dict(mov)
            if mov_dict.get('fecha_registro'):
                fecha = mov_dict['fecha_registro']
                if hasattr(fecha, 'strftime'):
                    if fecha.tzinfo is None:
                        fecha = fecha.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                    fecha_str = fecha.astimezone(zoneinfo.ZoneInfo("America/Bogota")).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    try:
                        dt = datetime.strptime(str(fecha).split('.')[0], '%Y-%m-%d %H:%M:%S')
                        dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                        fecha_str = dt.astimezone(zoneinfo.ZoneInfo("America/Bogota")).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception:
                        fecha_str = str(fecha)
                mov_dict['fecha_registro_fmt'] = fecha_str
            else:
                mov_dict['fecha_registro_fmt'] = 'N/A'
            movimientos.append(mov_dict)
        
        import math
        total_pages = math.ceil(total / per_page) if total > 0 else 1
        
        return render_template('inventarios_movimientos.html', movimientos=movimientos, page=page, total_pages=total_pages)
    except Exception as e:
        import traceback
        return f"<h3>Error in /movimientos:</h3><pre>{traceback.format_exc()}</pre>", 500

@bp_inventarios.route('/movimientos/exportar', methods=['GET'])
def inventarios_movimientos_exportar():
    conn = get_db()
    movimientos = conn.execute("""
        SELECT ih.* 
        FROM inventarios_historial ih
        LEFT JOIN inventarios i ON ih.item_id = i.id
        WHERE i.tipo != 'Control Especial' OR i.tipo IS NULL
        ORDER BY ih.fecha_registro DESC
    """).fetchall()
    conn.close()
    
    data = []
    for mov in movimientos:
        if mov.get('fecha_registro'):
            fecha = mov['fecha_registro']
            if hasattr(fecha, 'strftime'):
                if fecha.tzinfo is None:
                    fecha = fecha.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                fecha_str = fecha.astimezone(zoneinfo.ZoneInfo("America/Bogota")).strftime('%Y-%m-%d %H:%M:%S')
            else:
                try:
                    dt = datetime.strptime(str(fecha).split('.')[0], '%Y-%m-%d %H:%M:%S')
                    dt = dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
                    fecha_str = dt.astimezone(zoneinfo.ZoneInfo("America/Bogota")).strftime('%Y-%m-%d %H:%M:%S')
                except Exception:
                    fecha_str = str(fecha)
        else:
            fecha_str = 'N/A'
            
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
