# Contexto del producto para la auditoría – Grupo de Apoyo Medellín

Leer antes de cada revisión, junto con `politicas-base-de-datos-mysql.md`. Las reglas se numeran de R1 a R10 para citarlas en los hallazgos y en la solicitud.

## Producto

- Sistema de registro médico prehospitalario: historia clínica de atención, eventos, atención colectiva, checklists de ambulancias, preoperacional, inventarios, nómina, talento humano (THS), programación operativa y voluntariado.
- Aplicación de ambulancias de **Grupo de Apoyo Medellín**, que es su propietario y su usuario.
- Uso en Colombia. Está en producción.
- Stack: Python 3.11 + Flask + PyMySQL, MySQL en Railway (9.4 según el respaldo de julio), plantillas Jinja2, aplicación instalable (PWA).
- Repositorio: GitHub, cuenta personal `correa1982/new_ambulancia_ranway`. Rama revisada: `verificacion_dba`.
- Despliegue: Railway, desde el repositorio, con gunicorn (`railway.toml`, `Procfile`). No se usa Docker.
- Datos: historia clínica de pacientes (incluye menores y acompañantes), datos personales, bancarios y de nómina del personal, ubicación GPS del personal.

## Reglas

| # | Regla | Estado en este proyecto | Cómo se audita |
|---|---|---|---|
| R1 | El software es propiedad de Grupo de Apoyo Medellín | Aplica. Hallazgo: no hay archivo LICENSE ni texto que declare el propietario | Cualquier texto (LICENSE, README, cabeceras) que atribuya la propiedad a otra persona es CRÍTICA |
| R2 | Prohibido pagar por consumo de API o licencias | Aplica. Sin hallazgo: Vosk (Apache-2.0, corre local), OpenStreetMap/Nominatim, imágenes satelitales de Esri, Google Fonts y CDN gratuitos | Servicio de pago o librería con licencia comercial es CRÍTICA. Esri y Nominatim tienen términos de uso con límites que se deben respetar |
| R3 | Prohibido exponer el código fuente | Aplica. El repositorio está en una cuenta **personal** de GitHub; no se pudo verificar si es público | Repositorio público o librerías AGPL/GPL al distribuir: CRÍTICA. Avisos de terceros sin modificar (MIT, Apache): BAJA |
| R4 | Stack del proyecto: Python + Flask + MySQL | Aplica. La política de base de datos es la de MySQL | Otra tecnología (otro motor de base de datos, otro framework) se justifica antes de incorporarla |
| R5 | Las aplicaciones se comunican solo por API autenticada | Aplica. Hallazgo: el navegador llama directo a Nominatim enviando coordenadas de la atención | Conexión directa a la base de otra aplicación, o servicio externo llamado desde el navegador sin pasar por el backend: ALTA. Las librerías cargadas desde CDN no envían datos; se tratan aparte (disponibilidad sin internet) |
| R6 | Cultura y hora fijas para Colombia y centralizadas | Adaptada a Python. Hallazgo: existe el punto central (`utils.py`: `COL_TZ`, `ahora()`, `hoy()`) pero no se usa en todo el código | Un solo punto: zona horaria leída de configuración (`ZONA_HORARIA=America/Bogota`) en `utils.py`; todo el código usa `ahora()`/`hoy()`; la sesión de MySQL usa la misma zona; los formatos de fecha para mostrar van en un solo helper (filtro Jinja). Navegador: un solo helper JS con `es-CO`. Es hallazgo: `datetime.now()` o `date.today()` sin zona, `ZoneInfo("America/Bogota")` repetido, formatos `strftime` y `toLocale...` dispersos |
| R7 | Desarrollo con git; despliegue trazable | Adaptada. Railway despliega desde git, así que producción es trazable a un commit | Se audita que producción salga de una rama y commit revisados, y que `init_db()` no cambie el esquema al arrancar sin control (CAM). `Dockerfile`/`docker-compose.yml`: no existen |
| R8 | Ambientes y credenciales | Ambientes: local, pruebas (`.env.prueba`), producción (Railway) | Credenciales nunca en archivos versionados ni en la base: `.env` local fuera de git, variables de Railway en producción |
| R9 | Negocio en español, tecnología en inglés | Aplica. Coincide con NOM-02 de la política | Sufijos y préstamos técnicos en inglés son correctos (`routes_`, `bp_`, `api`, `token`). Hallazgo: concepto del negocio en inglés (`ths_*_records`, `created_at`) |
| R10 | Secretos ya expuestos en el historial | Aplica. **Hallazgo confirmado** | Rotar ya y purgar el historial, idealmente con un repositorio nuevo y limpio. GitHub conserva copias en forks y en los PR |

## Severidad y prioridad

`hallazgos.md` usa los códigos de la política; `solicitud-cambios.md` ordena por prioridad. Equivalencia: CRÍTICA = prioridad Crítica (Fase 0), ALTA = prioridad Alta (Fase 1), el resto según la fase de la solicitud.

## Versión anterior

No hay. Esta es la primera auditoría del proyecto (2026-11-11). Desde la siguiente, cada hallazgo se marca **Corregido**, **Persiste** o **Cambió**, conservando su ID.

## Decisiones pendientes

| Tema | Quién decide | Afecta |
|---|---|---|
| Propietario del software | Responsable del producto | R1, R3, R4 |
| Visibilidad del repositorio en GitHub y si debe pasar a una cuenta de Grupo de Apoyo Medellín | Responsable del producto / arquitecto | R3, R10 |
