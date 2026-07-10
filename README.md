# Sistema de Registro Médico - Ambulancia (Flask + MySQL)

## 📋 Requisitos Previos
- Python 3.8+
- MySQL 5.7+ o MariaDB
- pip (gestor de paquetes Python)

## 🚀 Instalación

### 1. Clonar/Descargar el Repositorio
```bash
cd ambulacia
```

### 2. Crear Entorno Virtual
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar Variables de Entorno
Copiar `.env.example` a `.env` y editar con tus credenciales:
```bash
cp .env.example .env
```

Editar `.env`:
```
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=tu_usuario
MYSQL_PASSWORD=tu_contraseña
MYSQL_DB=ambulancia_db
SECRET_KEY=tu_clave_secreta_aqui
```

### 5. Inicializar Base de Datos
```bash
python -c "from db import init_db; init_db()"
```

### 6. Crear Usuario Administrador
```bash
# Acceder a MySQL y ejecutar:
INSERT INTO usuarios (nombre, identificacion, registro_medico, rol, perfil, activo, contrasena, requiere_cambio_clave, formularios_acceso)
VALUES ('Administrador', 'admin', 'N/A', 'admin', '["Admin"]', 1, <hash_contraseña>, 0, '{}');
```

## 🏃 Ejecutar Aplicación
```bash
python app.py
```

Abrir en navegador: **http://localhost:5000**

## 📌 Credenciales Iniciales
- **Usuario**: admin
- **Contraseña**: (la que hayas establecido)

## ✨ Funcionalidades Principales

### 👥 Gestión de Usuarios
- Crear, editar, habilitar/deshabilitar usuarios
- Asignación de perfiles profesionales
- Acceso a formularios específicos
- Cambio de contraseña (primera vez obligatorio)

### 📝 Formularios
- **Historia Clínica**: datos completos del paciente
- **Eventos**: registro de eventos y emergencias
- **Atención Colectiva**: atención masiva de pacientes
- **Preoperacional**: checklist de vehículos
- **Checklists**: TAM, TAB, PASB, PASM

### 📊 Estadísticas
- KPIs de registros
- Gráficos por EPS, sexo y volumen
- Filtros por fecha

### ⚙️ Configuración
- Nombre de institución
- NIT y número de habilitación
- Gestión de aseguradoras
- Checklists dinámicos

## 🔒 Seguridad

✅ **Implementado:**
- Hash de contraseñas (werkzeug.security)
- Protección contra SQL Injection (parámetros)
- Autenticación obligatoria (@login_required)
- Control de roles (admin_required)
- Validación de campos obligatorios
- Timestamps de auditoría

⚠️ **Recomendaciones:**
- Usar HTTPS en producción
- Cambiar SECRET_KEY en .env
- Configurar backups automáticos
- Usar CORS si es necesario

## 📁 Estructura de Carpetas
```
ambulacia/
├── app.py                 # Aplicación principal
├── db.py                  # Conexión MySQL
├── utils.py               # Utilidades y decoradores
├── requirements.txt       # Dependencias
├── .env.example          # Template de variables
├── data/                 # Datos estáticos (CIE-10, etc.)
├── static/               # CSS, JS, imágenes
│   └── uploads/          # Archivos subidos (evidencias)
└── templates/            # Plantillas HTML Jinja2
```

## 🔧 Personalizar Listas

Editar en `app.py`:
- `TIPOS_DOCUMENTO`: CC, TI, CE, PA, RC, PEP, NIT, NN
- `TIPOS_AFILIACION`: Contributivo, Subsidiado, etc.
- `ASEGURADORAS`: Nueva EPS, Sura, Sanitas, etc. (también gestionar en admin)

## 🐛 Troubleshooting

### Error: "MYSQL_USER not in .env"
→ Copiar `.env.example` a `.env` y editar

### Error: "Connection refused to MySQL"
→ Verificar que MySQL está corriendo y credenciales son correctas

### Error: "ModuleNotFoundError: No module named 'pymysql'"
→ Ejecutar: `pip install -r requirements.txt`

## 📧 Soporte
Para reportar problemas o sugerencias, contactar al administrador del sistema.
