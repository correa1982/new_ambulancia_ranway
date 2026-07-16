import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template, current_app, send_from_directory, flash, redirect, url_for
from werkzeug.utils import secure_filename
from db import get_db
from utils import login_required, get_user_info

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

    @nomina_bp.route('/nomina', methods=['GET'])
    @login_required
    def nomina_index():
        from flask import session
        user_info = session['usuario']
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
        if 'file' not in request.files:
            flash('No se seleccionó ningún archivo.', 'error')
            return redirect(url_for('nomina.nomina_index'))
            
        file = request.files['file']
        if file.filename == '':
            flash('El nombre del archivo está vacío.', 'error')
            return redirect(url_for('nomina.nomina_index'))
            
        if file and allowed_file(file.filename):
            original_filename = secure_filename(file.filename)
            # Make the filename unique to prevent overwriting
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}_{original_filename}"
            file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
            
            try:
                file.save(file_path)
                
                # Save to database
                from flask import session
                user_info = session['usuario']
                conn = get_db()
                try:
                    conn.execute("""
                        INSERT INTO nomina (fecha_subida, nombre_archivo, archivo_url, registrado_por, registrado_por_identificacion)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        datetime.now(),
                        original_filename,
                        unique_filename,
                        user_info['nombre'],
                        user_info['identificacion']
                    ))
                    conn.commit()
                    flash('Archivo de nómina subido exitosamente.', 'success')
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
        return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)

    @nomina_bp.route('/nomina/delete/<int:id>', methods=['POST'])
    @login_required
    def delete_nomina(id):
        conn = get_db()
        try:
            cursor = conn.execute("SELECT archivo_url FROM nomina WHERE id = ?", (id,))
            record = cursor.fetchone()
            if record:
                file_path = os.path.join(UPLOAD_FOLDER, record['archivo_url'])
                if os.path.exists(file_path):
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

    app.register_blueprint(nomina_bp)
