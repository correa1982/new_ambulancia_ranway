# CHANGELOG - Ambulancia Sistema de Registro Médico

## [2.0.0] - 2026-06-16

### 🔒 Seguridad (CRÍTICO)
- **IMPLEMENTADO**: Hash de contraseñas con `werkzeug.security`
  - Login: ahora verifica contra hash con `check_password_hash()`
  - Registro: nuevas contraseñas hasheadas con `generate_password_hash()`
  - Cambio de clave: contraseña hasheada antes de guardar
  - Reset: contraseña hasheada al restablecer

### 📦 Dependencias Actualizadas
- Agregados: `pymysql>=1.0.0`, `python-dotenv>=0.19.0`, `werkzeug>=3.0.0`, `cryptography>=41.0.0`
- requirements.txt completado (antes solo tenía Flask)

### 📝 Configuración
- **NUEVO**: Archivo `.env.example` con variables de entorno
- **NUEVO**: `setup_check.py` - Script de verificación de instalación
- **ACTUALIZADO**: README.md con guía completa de instalación
- **ACTUALIZADO**: Documentación de seguridad

### 📋 Documentación
- README mejorado con:
  - Pasos detallados de instalación
  - Configuración de MySQL
  - Estructura de carpetas
  - Troubleshooting
  - Recomendaciones de seguridad

### ✨ Características sin Cambios
- Login con autenticación
- Formularios: Historia Clínica, Eventos, Atención Colectiva
- Checklists: TAM, TAB, PASB, PASM
- Preoperacional de vehículos
- Gestión de usuarios (admin)
- Estadísticas y gráficos
- API CIE-10

### 🛠️ Cambios Técnicos

#### En `app.py`:
```python
# ANTES (INSEGURO):
if user["contrasena"] != contrasena:
    flash("Credenciales incorrectas.")

# AHORA (SEGURO):
from werkzeug.security import check_password_hash
if not check_password_hash(user["contrasena"], contrasena):
    flash("Credenciales incorrectas.")
```

```python
# ANTES (INSEGURO):
conn.execute("INSERT INTO usuarios (...) VALUES (...)", 
    (..., identificacion, ...))  # Contraseña sin hash

# AHORA (SEGURO):
hashed_password = generate_password_hash(identificacion)
conn.execute("INSERT INTO usuarios (...) VALUES (...)", 
    (..., hashed_password, ...))
```

### 🔍 Próximas Mejoras (v2.1)
- [ ] Implementar rate limiting en endpoints sensibles
- [ ] Agregar 2FA (two-factor authentication) para admin
- [ ] Implementar CSRF protection en formularios
- [ ] Agregar logging centralizado
- [ ] Configurar HTTPS automático
- [ ] Agregar pruebas unitarias
- [ ] Implementar respaldos automáticos
- [ ] API REST mejorada (GraphQL opcional)

### ⚠️ Notas Importantes

**Migración desde versión anterior:**
- Las contraseñas existentes en la BD NO son compatibles
- Recomendado: Crear nuevo admin y resetear usuarios
- O ejecutar: `python -c "from db import init_db; init_db()"`

**Variables de entorno obligatorias:**
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_DB=ambulancia_db
SECRET_KEY=cambiar_en_produccion
```

### 📞 Verificar Instalación
```bash
python setup_check.py
```

---

## Versiones Anteriores

### v1.0.0 - Inicial
- Sistema base con Flask
- Formularios médicos
- Checklists
- Gestión de usuarios (básica)
