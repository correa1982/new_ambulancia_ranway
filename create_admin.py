#!/usr/bin/env python3
"""
Script para crear usuario administrador
Uso: python create_admin.py
"""

import os
import sys
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from db import get_db

def main():
    load_dotenv()
    
    print("=" * 60)
    print("  CREAR USUARIO ADMINISTRADOR")
    print("=" * 60)
    
    try:
        conn = get_db()
        print("\n✓ Conexión a MySQL exitosa")
        
        # Verificar si ya existe admin
        existing = conn.execute(
            "SELECT * FROM usuarios WHERE identificacion = ?", 
            ("admin",)
        ).fetchone()
        
        if existing:
            print("✗ El usuario 'admin' ya existe")
            print(f"  ID: {existing['id']}")
            print(f"  Nombre: {existing['nombre']}")
            print(f"  Rol: {existing['rol']}")
            print("\n→ Para resetear contraseña, usa la opción de admin en la aplicación")
            conn.close()
            return 1
        
        # Crear hash de contraseña
        password = "admin123"
        hashed_password = generate_password_hash(password)
        
        # Insertar admin
        conn.execute("""
            INSERT INTO usuarios 
            (nombre, identificacion, registro_medico, rol, perfil, activo, contrasena, requiere_cambio_clave, formularios_acceso)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'Administrador',
            'admin',
            'N/A',
            'admin',
            '["Admin"]',
            1,
            hashed_password,
            0,  # No requiere cambio de clave
            '{}'
        ))
        
        conn.commit()
        conn.close()
        
        print("\n✓ Usuario administrador creado exitosamente")
        print("\n" + "=" * 60)
        print("  CREDENCIALES")
        print("=" * 60)
        print(f"Usuario:     admin")
        print(f"Contraseña:  {password}")
        print("=" * 60)
        print("\nPuedes acceder en: http://localhost:5000")
        print("\nPara ejecutar la aplicación:")
        print("  python app.py")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nVerifica que:")
        print("  1. MySQL está corriendo")
        print("  2. Archivo .env está configurado correctamente")
        print("  3. La base de datos existe")
        print("  4. Tienes permisos de inserción")
        return 1

if __name__ == '__main__':
    sys.exit(main())
