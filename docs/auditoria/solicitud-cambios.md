# Solicitud de cambios de base de datos

Fecha: 2026-11-11
De: DBA del equipo de desarrollo
Para: equipo de desarrollo de la aplicación de ambulancias de Grupo de Apoyo Medellín
Base (línea de comparación): commit `0459bc5` de la rama `verificacion_dba`
Adjuntos: `hallazgos.md` (hallazgos), `contexto.md` (reglas R1 a R10 del producto) y `politicas-base-de-datos-mysql.md` v1.0-MySQL (reglas de base de datos)
Estado: **borrador, pendiente de validación y firma del DBA**

---

## 1. Objetivo

Pedir al equipo de desarrollo las correcciones necesarias para que la base de datos cumpla la política, en un orden que proteja primero los datos de pacientes y que no detenga la operación.

Criterio usado para ordenar: primero lo que hoy puede causar pérdida o exposición de datos; después lo que impide confiar en los datos (relaciones y fechas); al final lo que es orden y mantenimiento (nombres, longitudes).

## 2. Reglas para todas las solicitudes

1. Ningún cambio de esta solicitud se aplica en producción sin respaldo previo verificado y sin haberse probado antes en el ambiente de pruebas (CAM-02, ELI-03).
2. Todo cambio de estructura llega con tres piezas: el cambio, el script de migración de datos y el script de reversa (CAM-03, CAM-04).
3. Los cambios en `pacientes` y en las tablas de formularios se programan con el DBA en una ventana acordada (CAM-05).
4. Desde la fecha de esta solicitud, toda tabla o columna **nueva** cumple la política completa. No se acepta deuda nueva.
5. **Un commit por solicitud**, con el ID al inicio del mensaje (`SOL-04: quitar CASCADE de las FK`). Si una solicitud se entrega en varias partes, cada commit lleva el mismo ID.
6. **No empeorar:** desde la fecha de esta solicitud, el código nuevo o modificado cumple la política y el contexto: ninguna consulta nueva con `SELECT *`, ningún `DELETE FROM` nuevo sobre tablas de negocio, ningún `datetime.now()` sin zona, ninguna columna nueva de fecha como texto, ningún secreto en archivos o en la base.
7. **Evidencia antes y después:** toda solicitud que toque datos existentes entrega el resultado de una consulta de control antes y después del cambio (conteo de filas, totales, valores nulos o inválidos). Sin esa evidencia no se marca como corregida. El proyecto no tiene pruebas automáticas; mientras no las tenga, la consulta de control y la verificación manual descrita en el criterio de aceptación reemplazan a la prueba.
8. Una solicitud se cierra cuando se cumple su criterio de aceptación y la respuesta se registra según la sección 8.

## 3. Resumen de solicitudes

| N.º | Solicitud | Prioridad | Hallazgos | Toca datos existentes |
|---|---|---|---|---|
| SOL-01 | Sacar la contraseña del correo de la base | Crítica | SEG-01 | Sí (una fila) |
| SOL-02 | Proteger los respaldos | Crítica | SEG-05 | No |
| SOL-03 | Retirar del repositorio archivos con datos reales | Crítica | SEG-05, SQL-07 | No |
| SOL-16 | Rotar los secretos expuestos en el historial de git | Crítica | SEG-01, R10, R3 | No |
| SOL-04 | Eliminar los borrados en cascada | Alta | INT-03, ELI-01 | No |
| SOL-05 | Ordenar la forma de cambiar el esquema | Alta | CAM-01, CAM-03, CAM-04, CAM-06, CAM-02 | No |
| SOL-06 | Zona horaria centralizada y collation única | Alta | Perfil, TIP-04, R6 | Sí |
| SOL-17 | Consulta de direcciones desde el backend | Alta | R5, SEG-05 | No |
| SOL-07 | Eliminación lógica | Alta | ELI-01, ELI-02, ESTD-01 | Sí (columnas nuevas) |
| SOL-08 | Usuario como relación y no como texto | Media | INT-05, NOM-04, SEG-06, INT-02 | Sí |
| SOL-09 | Llaves foráneas e índices | Media | INT-02, IDX-01, NOM-05, INT-10 | Sí (depuración) |
| SOL-10 | Fechas y horas con tipo de fecha | Media | TIP-01, TIP-02, IDX-08, TIP-11 | Sí |
| SOL-11 | Dinero, booleanos y texto con longitud | Media | TIP-07, TIP-06, TIP-03, TIP-05, INT-01 | Sí |
| SOL-12 | Consultas del código | Media | SQL-04, SQL-10, SQL-09, SQL-08, SEG-04 | No |
| SOL-13 | Binarios y firmas | Baja | ALM-01, TIP-09, INT-12, IDX-05 | Sí |
| SOL-14 | Unificar modelos paralelos | Baja | INT-16, INT-15, INT-13 | Sí |
| SOL-15 | Nombres | Baja | NOM-01, NOM-02, NOM-06 | Sí (renombrar) |

---

## 4. Detalle

### Fase 0 – Inmediato (seguridad)

#### SOL-01 Sacar la contraseña del correo de la base — Crítica

- **Hallazgo:** SEG-01. La clave `smtp_password` se guarda en texto plano en `configuracion` (`routes_admin.py` línea 748) y sale en cada respaldo.
- **Se solicita:**
  1. Leer la contraseña SMTP solo de la variable de entorno (`SMTP_PASSWORD`), que el código ya soporta.
  2. Quitar el campo de la pantalla de configuración, o cifrarlo desde la aplicación si el negocio necesita cambiarlo desde ahí.
  3. Borrar la fila `smtp_password` de `configuracion` en todos los ambientes.
  4. Cambiar la contraseña del correo, porque la actual ya quedó en respaldos enviados y en el historial de git (se hace junto con SOL-16).
- **Criterio de aceptación:** no existe la clave `smtp_password` en `configuracion`; el envío de correo sigue funcionando; la contraseña anterior ya no sirve.

#### SOL-02 Proteger los respaldos — Crítica

- **Hallazgo:** SEG-05. `backup_service.py` envía la base completa, sin cifrar, como adjunto de correo.
- **Se solicita:**
  1. Suspender el envío del respaldo por correo en cuanto el DBA confirme el respaldo alterno del punto 2.
  2. **[DBA]** Definir el respaldo oficial (respaldo administrado de Railway o copia a un almacenamiento privado), su retención y la prueba periódica de restauración.
  3. Si el correo debe seguir mientras tanto, cifrar el archivo con una clave que no viaje en el mismo correo.
- **Criterio de aceptación:** ningún respaldo sale sin cifrar; existe una restauración de prueba documentada.

#### SOL-03 Retirar del repositorio archivos con datos reales — Crítica

- **Hallazgo:** SEG-05, SQL-07. `static/uploads/archivador/*.pdf` y `ambulancia.db` están en git; `.gitignore` ignora `*.sql`.
- **Se solicita:**
  1. Confirmar si esos PDF contienen datos reales de personas.
  2. Dejar de versionarlos (`git rm --cached`), sin borrarlos del servidor.
  3. Si tienen datos reales, el responsable decide si se limpia el historial de git y quién tiene acceso al repositorio.
  4. Permitir en `.gitignore` una carpeta de scripts versionados (propuesta: `docs/auditoria/scripts/`), manteniendo ignorados los volcados.
- **Criterio de aceptación:** `git ls-files` no muestra archivos de `static/uploads/` ni bases locales; los scripts de reversa sí se pueden versionar.

#### SOL-16 Rotar los secretos expuestos en el historial de git — Crítica (nueva)

- **Hallazgo:** SEG-01, R10, R3. El `.env` con las contraseñas de MySQL y SMTP y la `SECRET_KEY` de Flask se subió en los commits `af6221e`, `f426519` y `ce5599b` (julio de 2026). Se retiró del repositorio en `fb481e0` (agosto), pero sigue en el historial. El repositorio está en una cuenta personal de GitHub.
- **Se solicita:**
  1. Cambiar ya la contraseña del usuario de MySQL de producción y la del correo, y generar una `SECRET_KEY` nueva (cerrará las sesiones abiertas). Actualizarlas en las variables de Railway y en los `.env` locales.
  2. Verificar si el repositorio es público. Si lo es, pasarlo a privado de inmediato.
  3. Purgar el historial. Recomendación: crear un repositorio nuevo y limpio (idealmente en una cuenta de Grupo de Apoyo Medellín, ver `contexto.md`), porque GitHub conserva copias en forks y en las solicitudes de cambio (PR) aunque se reescriba la rama.
  4. Revisar en los registros de acceso de MySQL si hubo conexiones desde lugares desconocidos. **[DBA]**
- **Criterio de aceptación:** ninguna de las tres claves que están en el historial funciona; el repositorio vigente no contiene `.env` en ningún commit (`git log --all -- .env` sin resultados).
- **Nota:** el paso 1 no depende de nada y debe hacerse primero. Los pasos 2 y 3 requieren decisión del responsable del producto.

### Fase 1 – Frenar el riesgo y la deuda

#### SOL-04 Eliminar los borrados en cascada — Alta

- **Hallazgo:** INT-03, ELI-01. Las 3 FK del modelo usan `ON DELETE CASCADE`: `nomina_empleados` → `nomina`, `programacion_operativa_integrantes` → `programacion_operativa`, `inventarios_historial` → `inventarios`. Borrar una nómina o un ítem de inventario elimina sin aviso sus pagos o su historial.
- **Se solicita:**
  1. Recrear las tres FK con `ON DELETE RESTRICT ON UPDATE RESTRICT` y nombre según NOM-05.
  2. Cambiar las rutas que borran el padre (`routes_nomina.py`, `routes_inventarios.py`, `routes_programacion_operativa.py`) para que desactiven en lugar de borrar (ver SOL-07).
- **Criterio de aceptación:** no existe ninguna FK con `CASCADE` en `information_schema.referential_constraints`; intentar borrar una nómina con empleados devuelve error controlado.
- **Nota:** se hace antes que SOL-07 completa porque es el único punto donde un clic borra datos de varias tablas.

#### SOL-05 Ordenar la forma de cambiar el esquema — Alta

- **Hallazgo:** CAM-01, CAM-02, CAM-03, CAM-04, CAM-06.
- **Se solicita:**
  1. Mover a `init_db()` el `ALTER TABLE usuarios` que está en `routes_auth.py` (línea 55).
  2. Reemplazar `DESCRIBE` / `SHOW INDEX` por consultas a `information_schema`, y quitar los `try/except` que ocultan errores de `ALTER`. Si un cambio falla, la aplicación no debe arrancar con el esquema a medias.
  3. Separar en `init_db()` los cambios de estructura de los cambios de datos (cargas de catálogos, correcciones de `usuarios`, reescritura de `datos_json`).
  4. Registrar cada cambio aplicado en una tabla de control (propuesta: `cambios_esquema` con identificador del cambio y `fecha_creacion`), para que un cambio no se vuelva a evaluar en cada arranque y se pueda saber qué versión tiene cada ambiente.
  5. Quitar las diferencias por ambiente (`RENDER`, creación de la base con otra collation).
- **Decisión del DBA (propuesta):** mantener `init_db()` como vía única por ahora, con la tabla de control. Pasar a scripts versionados cuando termine la Fase 2.
- **Criterio de aceptación:** ejecutar `init_db()` dos veces seguidas no cambia nada la segunda vez; un `ALTER` que falla detiene el arranque y se ve en el log; no hay sentencias de esquema fuera de `db.py`.

#### SOL-06 Zona horaria centralizada y collation única — Alta

- **Hallazgo:** perfil (zona horaria), TIP-04, R6. Existe un punto central (`utils.py`: `COL_TZ`, `ahora()`, `hoy()`), pero hay 25 llamadas a `datetime.now()` / `date.today()` sin zona en 9 archivos, conversiones `ZoneInfo` repetidas en `routes_inventarios.py` y formatos de fecha escritos en cada lugar.
- **Decisión del DBA (propuesta), zona horaria:** hora de Colombia (`America/Bogota`, UTC-5, sin cambio de horario) para todo el producto, porque es la que ya tienen los datos existentes. Para que los defaults de la base coincidan con la aplicación, la conexión fija la zona de la sesión al conectarse (`SET time_zone = '-05:00'` en `db.py`). No se cambia la configuración del servidor.
- **Decisión del DBA (propuesta), collation:** una sola, la de la base de producción (`utf8mb4_0900_ai_ci`).
- **Se solicita:**
  1. Leer la zona de una sola variable de configuración (`ZONA_HORARIA=America/Bogota`) en `utils.py`, y desde ahí: `COL_TZ`, `ahora()`, `hoy()` y la zona de la sesión de MySQL en `ConnectionPool._connect()`.
  2. Reemplazar las 25 llamadas sin zona por `ahora()` / `hoy()` y quitar las conversiones de `routes_inventarios.py` (líneas 1064 a 1111) una vez corregidos los datos del punto 5.
  3. Un solo helper para mostrar fechas en Python (filtro Jinja con formato colombiano) y uno en JavaScript con `es-CO`, en lugar de `strftime` y `toLocaleString()` dispersos.
  4. Quitar `COLLATE=...` de los `CREATE TABLE` de `db.py`; **[DBA]** convertir las 16 tablas que están en `utf8mb4_general_ci`, en ventana.
  5. Verificar qué fechas ya guardadas con `CURRENT_TIMESTAMP` quedaron en hora del servidor (tablas con `fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP`) y corregirlas con script.
- **Criterio de aceptación:** `SELECT NOW()` desde la aplicación devuelve hora de Colombia; `grep -rn -E "datetime\.now\(\)|date\.today\(\)" --include=*.py .` no devuelve resultados fuera de `utils.py`; `ZoneInfo(` solo aparece en `utils.py`; todas las tablas tienen la misma collation; el perfil de la política queda actualizado con la decisión.

#### SOL-17 Consulta de direcciones desde el backend — Alta (nueva)

- **Hallazgo:** R5, SEG-05. `templates/formulario.html` (línea 3664) y `static/mapa.js` (línea 144) llaman desde el navegador a Nominatim (OpenStreetMap) con las coordenadas del lugar de la atención.
- **Se solicita:**
  1. Crear una ruta del backend, con sesión iniciada, que reciba las coordenadas y consulte Nominatim; el navegador solo llama a esa ruta.
  2. No enviar a Nominatim ningún dato del paciente (solo coordenadas) y cumplir sus términos de uso: identificarse con `User-Agent` propio y no más de una consulta por segundo.
  3. Guardar en caché el resultado por coordenadas redondeadas, para no repetir consultas.
- **Criterio de aceptación:** las herramientas del navegador no muestran llamadas a `nominatim.openstreetmap.org`; sin sesión, la ruta nueva responde 401 o redirige al inicio de sesión.

### Fase 2 – Integridad

#### SOL-07 Eliminación lógica — Alta

- **Hallazgo:** ELI-01, ELI-02, ESTD-01. 30 `DELETE FROM` sobre 25 tablas; 35 tablas sin `activo`.
- **Se solicita:**
  1. Agregar `activo` y `fecha_eliminacion` a las tablas donde hoy se borra. Orden: `archivador`, `atencion_vehiculo`, `reporte_gasto`, `nomina`, `inventarios`, `vehiculos`, `personal_operativo`, `ths_*`; después catálogos.
  2. Cambiar cada `DELETE` por `UPDATE ... SET activo = 0, fecha_eliminacion = NOW(3)`.
  3. Agregar `activo = 1` a las consultas de esas tablas.
- **Excepciones que el DBA acepta, documentadas:** `imagenes` (reemplazo de logo) y `programacion_operativa_integrantes` (se reescribe la lista al editar), mientras no se rediseñen.
- **Criterio de aceptación:** en el código solo quedan los `DELETE FROM` de las excepciones; un registro "eliminado" desde la aplicación sigue existiendo en la base con `activo = 0`.

#### SOL-08 Usuario como relación y no como texto — Media

- **Hallazgo:** INT-05, NOM-04, SEG-06. 29 tablas guardan `registrado_por` y `registrado_por_identificacion` como texto.
- **Se solicita:**
  1. Agregar `usuario_creacion_id INT NULL` a cada tabla.
  2. Llenarlo con script, cruzando `registrado_por_identificacion` contra `usuarios.identificacion`. Entregar al DBA la lista de registros que no cruzan antes de continuar.
  3. Crear la FK a `usuarios` y pasar la columna a `NOT NULL` cuando el DBA apruebe el resultado del cruce.
  4. La aplicación empieza a escribir `usuario_creacion_id` desde una función común (SQL-08). Las columnas de texto se conservan hasta que el DBA autorice retirarlas.
  5. Lo mismo para `avalado_por` → `usuario_aval_id` y `aceptado_por` → `usuario_aceptacion_id`.
- **Decisión de negocio pendiente:** si el nombre, perfil y registro médico de quien firmó deben conservarse tal como eran al momento de la atención (historia clínica). Si es así, se mantienen como copia histórica documentada (INT-06) además de la FK.
- **Criterio de aceptación:** 100 % de los registros con `usuario_creacion_id` válido, o lista de excepciones aprobada.

#### SOL-09 Llaves foráneas e índices — Media

- **Hallazgo:** INT-02, IDX-01, NOM-05, INT-10, IDX-07.
- **Se solicita**, para cada relación, primero la consulta de registros huérfanos y después la FK con su índice:

  | Hija | Columna | Padre |
  |---|---|---|
  | `pacientes` | `atencion_colectiva_id` | `atencion_colectiva` |
  | `archivador_formularios` | `categoria_id` | `archivador_categorias` |
  | `registro_pagos_nomina_empleados` | `item_id` | `items_nomina_empleados` |
  | `registro_pagos_varios` | `item_id` | `items_pagos_varios` |
  | `checklist_pasb_traslados` | `item_inventario_id` | `inventarios` |
  | `checklist_pasb_traslados` | `checklist_id` | `checklist_pasb` |
  | `programacion_operativa` | `registrado_por` | `usuarios` |
  | `personal_operativo` | `registrado_por` | `usuarios` |

  Además: renombrar los 18 índices `idx_` a `ix_`, nombrar los únicos (`ux_usuarios_identificacion`, `ux_vehiculos_placa`, etc.) y crear el índice por fecha de `inventarios_historial`.
- **Información que desarrollo debe entregar al DBA:** qué llaves naturales no se pueden repetir según el negocio (cédula en `personal_operativo` y `ths_*_records`, código de barras en `inventarios`, consecutivo en `archivador`).
- **Criterio de aceptación:** las 8 FK existen con nombre `fk_...`, `RESTRICT` e índice `ix_...`; cero huérfanos.

### Fase 3 – Tipos de datos

#### SOL-10 Fechas y horas con tipo de fecha — Media

- **Hallazgo:** TIP-01, TIP-02, IDX-08, TIP-11. Al menos 69 columnas de fecha u hora guardadas como texto.
- **Se solicita**, por tabla y en este orden: `pacientes`, `eventos`, `atencion_colectiva`, `atencion_vehiculo`, `preoperacional`, checklists, `archivador`, voluntariado y reporte de actividades:
  1. Reporte de formatos encontrados en cada columna (cuántos valores hay con cada formato, cuántos vacíos, cuántos inválidos). El DBA lo revisa antes de convertir.
  2. Columna nueva con el tipo correcto, script de conversión, validación de conteos y cambio del código para que lea y escriba la nueva.
  3. Retiro de la columna de texto en un cambio posterior, autorizado por el DBA.
  4. Reemplazar los filtros `substr(fecha_registro, 1, 10)` y `fecha_registro LIKE ?` por rangos de fecha, y recrear los índices sin prefijo.
- **Criterio de aceptación:** ninguna columna de fecha u hora es `TEXT` o `VARCHAR`; los reportes y la exportación RIPS dan los mismos totales antes y después.
- **Riesgo:** es el cambio de mayor impacto de la solicitud. No se hace en una sola entrega.

#### SOL-11 Dinero, booleanos y texto con longitud — Media

- **Hallazgo:** TIP-07, TIP-06, TIP-03, TIP-05, INT-01.
- **Se solicita:**
  1. `nomina_empleados.valor_total` de `VARCHAR(255)` a `DECIMAL`, con reporte previo de valores que no son número. `tarifa_asistencial` y `tarifa_conductor` a `DECIMAL`.
  2. Booleanos a `TINYINT(1) NOT NULL` con default, previa corrección de vacíos.
  3. Para cada tabla, reporte de la longitud máxima real de cada columna `TEXT` (`MAX(CHAR_LENGTH(col))`). Con ese reporte el DBA define la longitud del `VARCHAR`.
  4. `NOT NULL` en las columnas que el negocio confirme como obligatorias.
- **Criterio de aceptación:** solo quedan en `TEXT` las columnas de texto libre que el DBA apruebe por escrito.

#### SOL-12 Consultas del código — Media

- **Hallazgo:** SQL-04, SQL-10, SQL-09, SQL-08, SEG-04.
- **Se solicita:**
  1. Quitar `SELECT *`, empezando por las consultas sobre `pacientes` (100 columnas con firmas) en `routes_patients.py` y `routes_admin.py`.
  2. Cambiar los 18 `REPLACE INTO` por `INSERT ... ON DUPLICATE KEY UPDATE`.
  3. Paginar los listados sin `LIMIT`.
  4. Función común para las columnas de auditoría.
  5. En `routes_inventarios.py` línea 431, tomar el nombre de la tabla de un diccionario fijo.
- **Criterio de aceptación:** cero `SELECT *` en `routes/` y cero `REPLACE INTO` en `routes/` y `db.py`.
- **Nota:** no cambia la estructura de la base; puede avanzar en paralelo con las fases 1 y 2.

### Fase 4 – Rediseño

Estas tres solicitudes cambian la forma del modelo. No se inician hasta cerrar las fases 0 a 2, y cada una requiere un diseño aprobado por el DBA antes de escribir código.

#### SOL-13 Binarios y firmas — Baja

- **Hallazgo:** ALM-01, TIP-09, INT-12, IDX-05. `imagenes` mezcla metadatos y `LONGBLOB` con PK de texto; las firmas van como texto base64 dentro de cada formulario.
- **Se solicita:** propuesta de diseño con tabla de metadatos (`id`, nombre, mime, tamaño), tabla de contenido 1:1 y tablas puente por entidad. **[DBA]** define almacenamiento y tamaño máximo por archivo (ALM-02).

#### SOL-14 Unificar modelos paralelos — Baja

- **Hallazgo:** INT-16, INT-15, INT-13.
- **Se solicita:** propuesta de diseño para: checklists (7 tablas), `ths_*_records` (3 tablas), pagos de nómina (3 formas), personas (4 lugares), aseguradoras (2 catálogos) y separación de `pacientes` (100 columnas) en grupos 1:1.
- **Decisión de negocio pendiente:** cuál de los tres registros de pago de nómina es el vigente.

#### SOL-15 Nombres — Baja

- **Hallazgo:** NOM-01, NOM-02, NOM-06.
- **Se solicita:** aplicar los nombres de la política en tablas y columnas nuevas desde ya. Las existentes se renombran solo cuando la tabla se toque por otra solicitud (por ejemplo, `fecha_registro` → `fecha_creacion` junto con SOL-10), nunca como cambio aislado.

---

## 5. Lo que el DBA necesita para avanzar

| Necesidad | De quién | Para qué |
|---|---|---|
| Acceso de solo lectura a producción | Arquitecto / responsable de Railway | Comparar el esquema real con `init_db()`, medir tamaños y ver consultas lentas |
| Versión exacta de MySQL en producción | Arquitecto | Cerrar el perfil de la política (el respaldo de julio indica 9.4; `README.md` dice 5.7+) |
| Conteo de filas por tabla | Desarrollo | Saber qué cambios requieren ventana (CAM-05) |
| Usuario de MySQL que usa la aplicación y sus permisos | Arquitecto | SEG-03 |
| Confirmación de si los PDF del repositorio tienen datos reales | Responsable del producto | SOL-03 |
| Visibilidad del repositorio de GitHub y si debe pasar a una cuenta de Grupo de Apoyo Medellín | Responsable del producto / arquitecto | SOL-16 |
| Respuesta a las decisiones de negocio de SOL-08 y SOL-14 | Responsable del producto | Diseño |

## 6. Decisiones del DBA incluidas en este borrador

Quedan como propuesta hasta que el DBA las confirme:

1. Vía de cambio: `init_db()` con tabla de control (SOL-05).
2. Zona horaria: hora de Colombia, fijada en la sesión de la conexión (SOL-06).
3. Collation única: `utf8mb4_0900_ai_ci` (SOL-06).
4. Excepciones a la eliminación lógica: `imagenes` y `programacion_operativa_integrantes` (SOL-07).
5. Conversión de columnas en dos pasos: columna nueva, y retiro de la anterior en un cambio posterior (SOL-08, SOL-10).

## 7. Aprobación

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| DBA | | | |
| Responsable del producto | | | |
| Arquitecto | | | |

---

## 8. Qué devolver

Un solo archivo, `docs/auditoria/respuestas-solicitud.md`, que se actualiza en cada entrega:

```markdown
# Respuestas a la solicitud de cambios de base de datos

Commit: `<hash>` en `<rama>`.
Verificado el AAAA-MM-DD HH:MM en el ambiente de pruebas.

| ID | Estado | Commit | Evidencia | Comentario |
|---|---|---|---|---|
| SOL-04 | Corregido | abc1234 | `db.py:NN`; consulta a `information_schema.referential_constraints` sin `CASCADE` | — |
```

Reglas:

- **Estado:** `Corregido`, `En curso` (decir qué falta), `Duda` (pregunta concreta) o `No aplica` (con la decisión que lo respalda).
- **Evidencia:** `archivo:línea`, un comando o una consulta con su resultado. Sin evidencia no se marca `Corregido`.
- Para las solicitudes que cambian datos (SOL-06 a SOL-11, SOL-13, SOL-14), incluir el resultado de la consulta de control antes y después.
- No editar `hallazgos.md`, `contexto.md` ni la política. No escribir el valor de ningún secreto, ni siquiera parcial.

