#!/usr/bin/env python3
"""
Script para resetear contraseña del admin
Establece contraseña a: admin123
Uso: python reset_admin_password.py
"""

import os
import sys
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
from db import get_db

def main():
    load_dotenv()
    
    print("=" * 60)
    print("  RESETEAR CONTRASEÑA DEL ADMIN")
    print("=" * 60)
    
    try:
        conn = get_db()
        print("\n✓ Conexión a MySQL exitosa")
        
        # Verificar si existe admin
        admin = conn.execute(
            "SELECT * FROM usuarios WHERE identificacion = ?", 
            ("admin",)
        ).fetchone()
        
        if not admin:
            print("✗ El usuario 'admin' no existe")
            print("\n→ Ejecuta primero: python create_admin.py")
            conn.close()
            return 1
        
        # Generar nueva contraseña hasheada
        password = "admin123"
        hashed_password = generate_password_hash(password)
        
        # Actualizar contraseña
        conn.execute(
            "UPDATE usuarios SET contrasena = ?, requiere_cambio_clave = 0 WHERE identificacion = ?",
            (hashed_password, "admin")
        )
        
        conn.commit()
        conn.close()
        
        print("\n✓ Contraseña del admin restablecida")
        print("\n" + "=" * 60)
        print("  NUEVAS CREDENCIALES")
        print("=" * 60)
        print(f"Usuario:     admin")
        print(f"Contraseña:  {password}")
        print("=" * 60)
        print("\nPuedes acceder en: http://localhost:5000")
        
        return 0
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
