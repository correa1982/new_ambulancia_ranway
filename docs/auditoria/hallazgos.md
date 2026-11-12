# Hallazgos – revisión de base de datos contra la política MySQL

Fecha: 2026-11-11
Proyecto: aplicación de ambulancias de Grupo de Apoyo Medellín (`new_ambulancia_ranway`)
Rama y commit revisados: `verificacion_dba`, `0459bc5`
Política aplicada: `docs/auditoria/politicas-base-de-datos-mysql.md` v1.0-MySQL
Contexto: `docs/auditoria/contexto.md` (reglas R1 a R10)
Formato: `Código | Objeto | Hallazgo | Cambio requerido` (sección 12 de la política)

---

## 1. Resumen

El modelo no cumple la política en casi ninguna tabla. No es un problema de unas pocas columnas: la base se creó guardando casi todo como texto libre y sin relaciones entre tablas, y la política pide lo contrario.

| Tema | Estado actual |
|---|---|
| Tablas | 49 |
| Columnas | Al menos 784 |
| Columnas `TEXT` | Al menos 441 (TIP-03, TIP-05) |
| Fechas y horas guardadas como texto | Al menos 69 (TIP-01) |
| Columnas que aceptan vacío (NULL) | 520 de las 685 analizadas, 76 % (INT-01) |
| Llaves foráneas | 3 en todo el modelo, las tres con `CASCADE` (INT-02, INT-03) |
| Tablas con las columnas estándar completas | 0 de 49 (ESTD-01) |
| Tablas que guardan el usuario como texto | 29 (INT-05) |
| `DELETE FROM` en el código | 30, sobre 25 tablas (ELI-01) |
| `SELECT *` en el código | 157 (SQL-04) |
| Contraseña del correo (SMTP) en texto plano en la base | Sí (SEG-01) |
| Contraseñas en el historial de git | Sí: MySQL, SMTP y `SECRET_KEY` (SEG-01, R10) |

Lo que sí está bien:

- Las contraseñas de usuarios se guardan como hash (SEG-02).
- No encontré inyección de SQL: las 74 consultas armadas con f-string insertan nombres de tabla o columna que salen de listas fijas del código, y los valores del usuario van como parámetros (SEG-04). Ver 4.2.
- Todas las tablas son InnoDB y `utf8mb4`.
- `.env` está fuera de git.

Prioridad sugerida para el DBA (de mayor a menor riesgo):

1. Seguridad y datos de pacientes: sección 5.
2. Borrados físicos y cascadas: ELI-01, INT-03.
3. Fechas como texto y zona horaria: TIP-01 y perfil. Afecta filtros, reportes y RIPS.
4. Relaciones sin llave foránea: INT-02, INT-05.
5. El resto (nombres, longitudes, columnas estándar) conviene aplicarlo tabla por tabla cuando se toque cada módulo.

---

## 2. Alcance y límites

- Revisé el código: `db.py` (función `init_db()`), `app.py`, `utils.py`, `backup_service.py` y los 20 archivos de `routes/`.
- No me conecté a ninguna base de datos. Lo que existe hoy en producción puede diferir de lo que `init_db()` describe (columnas creadas a mano, índices, datos).
- Los conteos de columnas son mínimos: `init_db()` agrega columnas dentro de ciclos que el análisis automático no cuenta.
- No revisé rendimiento con planes de ejecución (IDX-06) ni consultas repetidas en ciclos (SQL-09); eso requiere la base real.
- No se modificó código ni base de datos.

---

## 3. Hallazgos del modelo

### 3.1 Generales (aplican a todas o casi todas las tablas)

| Código | Objeto | Hallazgo | Cambio requerido |
|---|---|---|---|
| ESTD-01 | Las 49 tablas | Ninguna tiene el juego completo de columnas estándar. 35 no tienen `activo`; solo 2 tienen `fecha_creacion`; ninguna tiene `usuario_creacion_id`, `usuario_actualizacion_id` ni `fecha_eliminacion` | Agregar las columnas estándar al modificar cada tabla |
| INT-01 | Todo el modelo | 520 de 685 columnas aceptan NULL sin regla de negocio que lo justifique | Definir `NOT NULL` por defecto; depurar datos antes (CAM-04) |
| INT-02 | Todo el modelo | Solo 3 FK. Las relaciones entre formularios, usuarios, vehículos, pacientes y catálogos son solo lógicas | Crear las FK (detalle por tabla en 3.3) |
| NOM-05 | Todo el modelo | Las 3 FK y los únicos en línea (`UNIQUE` en la columna) no tienen nombre; los 18 índices usan prefijo `idx_` en lugar de `ix_` | Nombrar según la tabla de formatos de NOM-05 |
| NOM-01 | `archivador`, `nomina`, `configuracion`, `preoperacional`, `atencion_vehiculo`, `atencion_colectiva`, `reporte_gasto`, `personal_operativo`, `programacion_operativa`, `registro_voluntariado`, `calif_atencion`, `segur_paciente`, los `checklist_*`, entre otras | Tablas en singular y con abreviaturas (`calif_`, `segur_`, `ths_`) | Plural y nombre completo en tablas nuevas; renombrar las existentes solo con plan aprobado por el DBA |
| NOM-02 | `ths_sga_records`, `ths_trip_records`, `ths_soc_records`; columna `created_at` | Inglés mezclado con español | Nombres en español |
| NOM-06 | 29 tablas | El mismo dato se llama `fecha_registro`, `fecha_subida`, `fecha_salida`, `creado_en`, `created_at` o `fecha_creacion` | Unificar en `fecha_creacion` |
| TIP-04 | 16 tablas | Declaran `COLLATE=utf8mb4_general_ci`; las otras 33 heredan la de la base (`utf8mb4_0900_ai_ci` en producción) y `init_db()` crea la base local con `utf8mb4_unicode_ci`. Tres collations en el mismo producto | No declarar collation en tablas nuevas. **[DBA]** unificar las existentes |
| IDX-04, IDX-03 | 15 de los 18 índices (`idx_pacientes_fecha_registro`, `idx_preop_placa`, `idx_vehiculos_placa`, etc.) | Son índices de prefijo `(255)` sobre columnas `TEXT` o `VARCHAR(255)` | Corregir primero el tipo de la columna (TIP-01, TIP-03) y recrear el índice sin prefijo |
| IDX-01 | Todas las relaciones de 3.3 | Al no existir la FK tampoco existe su índice (salvo `pacientes.atencion_colectiva_id`) | Crear el índice `ix_` junto con cada FK |
| INT-10 | `pacientes`, `personal_operativo`, `ths_*_records`, `inventarios`, `archivador` | Llaves naturales sin índice único: identificación del personal, consecutivo por formulario, código de barras | Crear `ux_` donde el negocio confirme que no se repite |
| INT-16 | Ver 3.2 | Varias familias de tablas con la misma estructura | Dejar un solo modelo por concepto |
| ELI-04 | `inventarios`, `nomina_pagos`, `registro_pagos_*`, `programacion_operativa`, formularios que se guardan por partes | Se actualizan desde varios usuarios y no tienen `version_fila` | Agregar `version_fila` y validarla al actualizar |
| IDX-07 | `inventarios_historial` | Tabla de historial sin índice por fecha | Crear `ix_inventarios_historial_fecha_creacion` |

### 3.2 Modelos paralelos (INT-16)

| Código | Objeto | Hallazgo | Cambio requerido |
|---|---|---|---|
| INT-16 | `checklist_tam`, `checklist_tab`, `checklist_pasb`, `checklist_pasm`, `checklist_avanzada`, `checklist_equipos`, `preoperacional` | Siete tablas para el mismo concepto (encabezado + `datos_json` + firma), que el código ya trata como una sola cambiando el nombre de la tabla | Una tabla de checklists con tipo (FK a catálogo) y una tabla hija de respuestas |
| INT-16 | `ths_sga_records`, `ths_trip_records`, `ths_soc_records` | Tres tablas idénticas creadas en un ciclo | Una tabla con columna de tipo (FK a catálogo) |
| INT-16 | `registro_pagos_nomina_empleados` y `registro_pagos_varios`; `items_nomina_empleados` e `items_pagos_varios` | Dos pares de tablas con las mismas columnas | Una tabla por concepto con tipo de pago |
| INT-16 | `nomina_empleados`, `nomina_pagos`, `registro_pagos_nomina_empleados` | Tres formas de registrar el pago de nómina (`pago_realizado` y `fecha_pago` en las tres) | Definir cuál es la vigente y retirar las otras |
| INT-16 | `aseguradoras` y `aseguradoras_soat` | Dos catálogos iguales | Un catálogo con tipo |
| INT-16 | `personal_operativo`, `usuarios`, `ths_*_records`, `items_nomina_empleados` | La misma persona (cédula, nombres) se guarda en cuatro lugares sin relación entre ellos | Una tabla de personas y FK desde las demás (INT-05, INT-06) |

### 3.3 Por tabla

Solo se listan los hallazgos propios de cada tabla; los generales de 3.1 aplican a todas.

### `usuarios` (18 columnas, `db.py` línea 207)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (1): `ultima_actualizacion_gps` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 10 de 18 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo`, `requiere_cambio_clave`, `permiso_programacion_operativa`, `permiso_verificacion_pagos` | `TINYINT(1) NOT NULL` con default |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| NOM-05 | Único sin nombre de política: `identificacion` | Nombrar `ux_{tabla}_{columnas}` |

### `archivador` (12 columnas, `db.py` línea 215)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (2): `fecha_registro`, `fecha_documento` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 9 de 12 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| INT-05, INT-06 | Texto en lugar de FK: `categoria`, `nombre_formulario` (catálogos como texto) | Reemplazar por la FK a la tabla correspondiente |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |

### `nomina` (7 columnas, `db.py` línea 228)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_subida` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03, TIP-05 | Columnas `TEXT`: 3 de 7 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_subida` | Renombrar a `fecha_creacion` (ESTD-01) |

### `nomina_empleados` (12 columnas, `db.py` línea 239)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_pago` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03, TIP-05 | Columnas `TEXT`: 1 de 12 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-03 | 7 columnas `VARCHAR(255)` por defecto: `identificacion`, `nombres`, `apellidos`, `codigo`, `valor_total` y 2 más | Ajustar la longitud al dato real |
| TIP-07 | Dinero sin `DECIMAL`: `valor_total VARCHAR(255)` | Cambiar a `DECIMAL(19,4)` o la precisión que defina el negocio |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `pago_realizado` | `TINYINT(1) NOT NULL` con default |
| INT-03 | `FOREIGN KEY(nomina_id) REFERENCES nomina(id) ON DELETE CASCADE` | Quitar `CASCADE` (usar `RESTRICT`) y dar nombre a la FK (NOM-05); excepción solo con aprobación del DBA |
| INT-05, INT-06 | Texto en lugar de FK: `identificacion`, `usuario_pago` (persona y usuario como texto) | Reemplazar por la FK a la tabla correspondiente |

### `pacientes` (100 columnas, `db.py` línea 252)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (8): `fecha_nacimiento`, `fecha_registro`, `fecha_inicio_atencion`, `triage_fecha_hora`, `fecha_finalizacion_registro`, `hora_despacho`, `hora_arribo`, `soat_vigencia` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 94 de 100 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `finalizado` | `TINYINT(1) NOT NULL` con default |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador`, `consentimiento_firma` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-02 | Relación sin FK: atencion_colectiva_id → atencion_colectiva | Crear FK con nombre e índice (NOM-05, IDX-01), `ON DELETE RESTRICT` |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| INT-05, INT-06 | Texto en lugar de FK: `aseguradora` y similares (catálogos como texto) | Reemplazar por la FK a la tabla correspondiente |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| INT-15 | Entidad de 100 columnas | Revisar separación en tablas 1:1 por grupo de datos |

### `configuracion` (2 columnas, `db.py` línea 324)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| IDX-05, NOM-03 | La PK es un texto (`clave`) | PK `id INT AUTO_INCREMENT` e índice único sobre la llave natural (INT-10) |

### `imagenes` (5 columnas, `db.py` línea 332)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `creado_en` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| NOM-06 | Variante de columna estándar: `creado_en` | Renombrar a `fecha_creacion` (ESTD-01) |
| IDX-05, NOM-03 | La PK es un texto (`nombre`) | PK `id INT AUTO_INCREMENT` e índice único sobre la llave natural (INT-10) |

### `eventos` (18 columnas, `db.py` línea 341)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (5): `fecha_inicio`, `hora_inicio`, `fecha_finalizacion`, `hora_finalizacion`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 17 de 18 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_coordinador_evento`, `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |

### `atencion_vehiculo` (24 columnas, `db.py` línea 363)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (5): `fecha_hora_despacho`, `fecha_hora_salida`, `fecha_hora_llegada`, `fecha_hora_finalizacion`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 21 de 24 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `finalizado` | `TINYINT(1) NOT NULL` con default |
| INT-13 | JSON guardado en texto: `equipos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |

### `atencion_colectiva` (17 columnas, `db.py` línea 389)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (5): `fecha_inicio`, `hora_inicio`, `fecha_finalizacion`, `hora_finalizacion`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 15 de 17 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `finalizado` | `TINYINT(1) NOT NULL` con default |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |

### `preoperacional` (40 columnas, `db.py` línea 409)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (5): `fecha`, `hora`, `soat_vigencia`, `rtm_vigencia`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 38 de 40 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `finalizado` | `TINYINT(1) NOT NULL` con default |
| INT-13 | JSON guardado en texto: `datos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| INT-05, INT-06 | Texto en lugar de FK: `placa_vehiculo`, `movil`, `nombre_conductor` (vehículo y conductor como texto) | Reemplazar por la FK a la tabla correspondiente |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| INT-15 | Entidad de 40 columnas | Revisar separación en tablas 1:1 por grupo de datos |

### `checklist_tam` (33 columnas, `db.py` línea 440)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (3): `fecha`, `hora`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 32 de 33 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| INT-13 | JSON guardado en texto: `datos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| INT-05, INT-06 | Texto en lugar de FK: `placa` (vehículo como texto) | Reemplazar por la FK a la tabla correspondiente |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| INT-15 | Entidad de 33 columnas | Revisar separación en tablas 1:1 por grupo de datos |

### `checklist_tab` (32 columnas, `db.py` línea 462)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (3): `fecha`, `hora`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 31 de 32 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| INT-13 | JSON guardado en texto: `datos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| INT-05, INT-06 | Texto en lugar de FK: `placa` (vehículo como texto) | Reemplazar por la FK a la tabla correspondiente |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| INT-15 | Entidad de 32 columnas | Revisar separación en tablas 1:1 por grupo de datos |

### `checklist_avanzada` (13 columnas, `db.py` línea 484)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (3): `fecha`, `hora`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 11 de 13 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `finalizado` | `TINYINT(1) NOT NULL` con default |
| INT-13 | JSON guardado en texto: `datos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |

### `checklist_pasb` (26 columnas, `db.py` línea 501)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (3): `fecha`, `hora`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 25 de 26 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| INT-13 | JSON guardado en texto: `datos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |

### `checklist_pasm` (31 columnas, `db.py` línea 521)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (3): `fecha`, `hora`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 30 de 31 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| INT-13 | JSON guardado en texto: `datos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| INT-15 | Entidad de 31 columnas | Revisar separación en tablas 1:1 por grupo de datos |

### `checklist_equipos` (11 columnas, `db.py` línea 543)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (3): `fecha`, `hora`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 10 de 11 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| INT-13 | JSON guardado en texto: `datos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |

### `calif_atencion` (19 columnas, `db.py` línea 559)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (3): `fecha`, `hora`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 17 de 19 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `finalizado` | `TINYINT(1) NOT NULL` con default |
| INT-13 | JSON guardado en texto: `datos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador`, `firma_paciente` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |

### `segur_paciente` (16 columnas, `db.py` línea 583)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (3): `fecha`, `hora`, `fecha_registro` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 14 de 16 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `finalizado` | `TINYINT(1) NOT NULL` con default |
| INT-13 | JSON guardado en texto: `datos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |

### `checklist_items` (9 columnas, `db.py` línea 604)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-03, TIP-05 | Columnas `TEXT`: 4 de 9 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo`, `aplica_vencimiento` | `TINYINT(1) NOT NULL` con default |

### `checklist_pasb_traslados` (14 columnas, `db.py` línea 618)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_salida`, `fecha_aceptado` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03 | 3 columnas `VARCHAR(255)` por defecto: `nombre`, `registrado_por`, `aceptado_por` | Ajustar la longitud al dato real |
| INT-02 | Relación sin FK: item_inventario_id → inventarios; checklist_id → checklist_pasb | Crear FK con nombre e índice (NOM-05, IDX-01), `ON DELETE RESTRICT` |
| INT-05, NOM-04 | Usuario guardado como texto: `aceptado_por` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| INT-05, INT-06 | Texto en lugar de FK: `nombre`, `categoria` (copiados del ítem de inventario) | Reemplazar por la FK a la tabla correspondiente |
| NOM-06 | Variante de columna estándar: `fecha_salida` | Renombrar a `fecha_creacion` (ESTD-01) |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `checklist_categorias` (4 columnas, `db.py` línea 643)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-03, TIP-05 | Columnas `TEXT`: 2 de 4 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo` | `TINYINT(1) NOT NULL` con default |

### `checklist_pas_opciones` (4 columnas, `db.py` línea 652)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo` | `TINYINT(1) NOT NULL` con default |

### `reporte_gasto` (13 columnas, `db.py` línea 661)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_registro` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03, TIP-05 | Columnas `TEXT`: 1 de 13 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `finalizado` | `TINYINT(1) NOT NULL` con default |
| INT-13 | JSON guardado en texto: `datos_json` | Tipo `JSON`; si los datos se consultan por campo, pasarlos a columnas o tabla hija |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |

### `vehiculos` (11 columnas, `db.py` línea 679)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-03, TIP-05 | Columnas `TEXT`: 6 de 11 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo` | `TINYINT(1) NOT NULL` con default |
| NOM-05 | Único sin nombre de política: `placa` | Nombrar `ux_{tabla}_{columnas}` |

### `aseguradoras` (3 columnas, `db.py` línea 695)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo` | `TINYINT(1) NOT NULL` con default |
| NOM-05 | Único sin nombre de política: `nombre` | Nombrar `ux_{tabla}_{columnas}` |

### `aseguradoras_soat` (3 columnas, `db.py` línea 703)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo` | `TINYINT(1) NOT NULL` con default |
| NOM-05 | Único sin nombre de política: `nombre` | Nombrar `ux_{tabla}_{columnas}` |

### `ths_licencias_conduccion` (4 columnas, `db.py` línea 770)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| INT-05, INT-06 | Texto en lugar de FK: `identificacion` (persona como texto) | Reemplazar por la FK a la tabla correspondiente |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `ths_vacunas` (5 columnas, `db.py` línea 780)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| INT-05, INT-06 | Texto en lugar de FK: `identificacion` (persona como texto) | Reemplazar por la FK a la tabla correspondiente |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `ths_contratos` (6 columnas, `db.py` línea 791)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| INT-05, INT-06 | Texto en lugar de FK: `identificacion` (persona como texto) | Reemplazar por la FK a la tabla correspondiente |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `ths_certificados_adicionales` (6 columnas, `db.py` línea 803)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| INT-05, INT-06 | Texto en lugar de FK: `identificacion` (persona como texto) | Reemplazar por la FK a la tabla correspondiente |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `inventarios` (14 columnas, `db.py` línea 815)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_registro` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03, TIP-05 | Columnas `TEXT`: 1 de 14 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-03 | 6 columnas `VARCHAR(255)` por defecto: `codigo_barras`, `codigo_secundario`, `nombre`, `invima`, `cum` y 1 más | Ajustar la longitud al dato real |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `inventarios_catalogo` (6 columnas, `db.py` línea 835)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-03 | 3 columnas `VARCHAR(255)` por defecto: `nombre`, `invima`, `cum` | Ajustar la longitud al dato real |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `programacion_operativa` (16 columnas, `db.py` línea 875)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (2): `hora_inicio`, `hora_finalizacion` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_registro` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03, TIP-05 | Columnas `TEXT`: 1 de 16 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-03 | 5 columnas `VARCHAR(255)` por defecto: `tipo_evento`, `nombre_evento`, `lugar`, `contacto`, `coordina` | Ajustar la longitud al dato real |
| TIP-07 | Dinero sin `DECIMAL`: `tarifa_asistencial INT`, `tarifa_conductor INT` | Cambiar a `DECIMAL(19,4)` o la precisión que defina el negocio |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `confirmado` | `TINYINT(1) NOT NULL` con default |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `confirmado` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-02 | Relación sin FK: registrado_por (INT) → usuarios | Crear FK con nombre e índice (NOM-05, IDX-01), `ON DELETE RESTRICT` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `programacion_operativa_integrantes` (7 columnas, `db.py` línea 890)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-03 | 3 columnas `VARCHAR(255)` por defecto: `nombre`, `rol_variable`, `unidad_nombre` | Ajustar la longitud al dato real |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `asistio` | `TINYINT(1) NOT NULL` con default |
| INT-03 | `FOREIGN KEY (programacion_id) REFERENCES programacion_operativa(id) ON DELETE CASCADE` | Quitar `CASCADE` (usar `RESTRICT`) y dar nombre a la FK (NOM-05); excepción solo con aprobación del DBA |
| INT-05, INT-06 | Texto en lugar de FK: `nombre`, `unidad_nombre` (persona y unidad como texto) | Reemplazar por la FK a la tabla correspondiente |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `personal_operativo` (9 columnas, `db.py` línea 901)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_registro` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03 | 5 columnas `VARCHAR(255)` por defecto: `cedula`, `nombres`, `apellidos`, `perfiles`, `registro` | Ajustar la longitud al dato real |
| INT-02 | Relación sin FK: registrado_por (INT) → usuarios | Crear FK con nombre e índice (NOM-05, IDX-01), `ON DELETE RESTRICT` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `registro_voluntariado` (19 columnas, `db.py` línea 913)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (5): `fecha`, `hora_inicio`, `hora_fin`, `fecha_registro`, `fecha_aval` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 17 de 19 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador`, `firma_avalador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion`, `avalado_por`, `avalado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `reporte_actividades` (29 columnas, `db.py` línea 937)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (5): `fecha_evento`, `hora_inicio`, `hora_fin`, `fecha_registro`, `fecha_aval` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 27 de 29 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-09, ALM-01 | Firmas (imagen) dentro de la fila: `firma_registrador`, `firma_avalador` | Mover a la tabla de binarios y relacionar con tabla puente (INT-12) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion`, `avalado_por`, `avalado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `inventarios_historial` (11 columnas, `db.py` línea 995)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_registro` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03 | 4 columnas `VARCHAR(255)` por defecto: `codigo_barras`, `nombre`, `destino`, `registrado_por` | Ajustar la longitud al dato real |
| INT-03 | `FOREIGN KEY (item_id) REFERENCES inventarios(id) ON DELETE CASCADE` | Quitar `CASCADE` (usar `RESTRICT`) y dar nombre a la FK (NOM-05); excepción solo con aprobación del DBA |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| INT-05, INT-06 | Texto en lugar de FK: `nombre`, `codigo_barras`, `lote` (copiados del ítem; ya existe `item_id`) | Reemplazar por la FK a la tabla correspondiente |
| NOM-06 | Variante de columna estándar: `fecha_registro` | Renombrar a `fecha_creacion` (ESTD-01) |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | Quitar la declaración en tablas nuevas; **[DBA]** unificar la collation de las existentes |

### `archivador_categorias` (4 columnas, `db.py` línea 1725)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (1): `created_at` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 1 de 4 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo` | `TINYINT(1) NOT NULL` con default |
| NOM-02 | Nombre en inglés: `created_at` | Renombrar a `fecha_creacion` |
| NOM-05 | Único sin nombre de política: `nombre` | Nombrar `ux_{tabla}_{columnas}` |

### `archivador_formularios` (5 columnas, `db.py` línea 1746)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | Fechas u horas guardadas como texto (1): `created_at` | Cambiar a `DATE`, `TIME`, `DATETIME` o `DATETIME(3)` según el uso, con migración de datos (CAM-04) |
| TIP-03, TIP-05 | Columnas `TEXT`: 1 de 5 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo` | `TINYINT(1) NOT NULL` con default |
| INT-02 | Relación sin FK: categoria_id → archivador_categorias | Crear FK con nombre e índice (NOM-05, IDX-01), `ON DELETE RESTRICT` |
| NOM-02 | Nombre en inglés: `created_at` | Renombrar a `fecha_creacion` |
| NOM-05 | Único sin nombre de política: `nombre` | Nombrar `ux_{tabla}_{columnas}` |

### `nomina_pagos` (9 columnas, `db.py` línea 1884)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_pago`, `fecha_actualizacion` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03 | 5 columnas `VARCHAR(255)` por defecto: `periodo`, `identificacion`, `registrado_por`, `registrado_por_identificacion`, `documento_equivalente` | Ajustar la longitud al dato real |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `pago_realizado` | `TINYINT(1) NOT NULL` con default |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por`, `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |
| INT-05, INT-06 | Texto en lugar de FK: `identificacion` (persona como texto) | Reemplazar por la FK a la tabla correspondiente |
| NOM-05 | Único sin nombre de política: `unq_periodo_identificacion` | Nombrar `ux_{tabla}_{columnas}` |

### `items_nomina_empleados` (6 columnas, `db.py` línea 1927)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_creacion` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo` | `TINYINT(1) NOT NULL` con default |

### `items_pagos_varios` (6 columnas, `db.py` línea 1937)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_creacion` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `activo` | `TINYINT(1) NOT NULL` con default |

### `registro_pagos_nomina_empleados` (13 columnas, `db.py` línea 1947)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_pago`, `fecha_actualizacion` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03, TIP-05 | Columnas `TEXT`: 1 de 13 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-03 | 3 columnas `VARCHAR(255)` por defecto: `nombre_completo`, `documento_soporte`, `registrado_por` | Ajustar la longitud al dato real |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `pago_realizado` | `TINYINT(1) NOT NULL` con default |
| INT-02 | Relación sin FK: item_id → items_nomina_empleados | Crear FK con nombre e índice (NOM-05, IDX-01), `ON DELETE RESTRICT` |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |

### `registro_pagos_varios` (13 columnas, `db.py` línea 1964)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| TIP-01 | `DATETIME` sin milisegundos en columnas de auditoría o control: `fecha_pago`, `fecha_actualizacion` | Usar `DATETIME(3)` en auditoría; default `CURRENT_TIMESTAMP(3)` (TIP-02) |
| TIP-03, TIP-05 | Columnas `TEXT`: 1 de 13 | Pasar a `VARCHAR(n)` con la longitud real; dejar `TEXT` solo en texto libre largo |
| TIP-03 | 3 columnas `VARCHAR(255)` por defecto: `nombre_completo`, `documento_soporte`, `registrado_por` | Ajustar la longitud al dato real |
| TIP-06 | Booleanos que aceptan NULL o son `INTEGER`: `pago_realizado` | `TINYINT(1) NOT NULL` con default |
| INT-02 | Relación sin FK: item_id → items_pagos_varios | Crear FK con nombre e índice (NOM-05, IDX-01), `ON DELETE RESTRICT` |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por_identificacion` | Reemplazar por `usuario_creacion_id` / `usuario_{rol}_id` con FK a `usuarios` |

### `ths_sga_records`, `ths_trip_records`, `ths_soc_records` (33 columnas cada una, `db.py` línea 712)

| Código | Hallazgo | Cambio requerido |
|---|---|---|
| INT-16, NOM-02 | Tres tablas idénticas, con nombre en inglés | Una sola tabla con tipo, nombre en español |
| TIP-03 | 9 columnas `VARCHAR(255)` por defecto (`identificacion`, `nombres`, `apellidos`, `contacto`, `banco_nombre`, etc.) | Ajustar la longitud al dato real |
| TIP-06 | 9 booleanos que aceptan NULL (`hoja_vida`, `rethus`, `acta_grado`, `cert_bancario`, `activo`, etc.) | `TINYINT(1) NOT NULL` con default |
| TIP-08 | `bls_vigencia` + `bls_vigencia_unidad` (y los pares `avvs_`, `avaq_`): la unidad de la duración va en otra columna | Un entero con la unidad en el nombre (`bls_vigencia_meses`) |
| INT-05, NOM-04 | Usuario guardado como texto: `registrado_por` | `usuario_creacion_id` con FK a `usuarios` |
| INT-06 | `banco_nombre`, `pension_nombre`, `eps_nombre` como texto libre | FK a catálogos |
| SEG-05 | `banco_cuenta`: número de cuenta bancaria del personal en texto plano | Identificar como dato sensible; **[DBA]** decide cifrado o enmascaramiento |
| NOM-06, TIP-01 | `fecha_registro DATETIME` | `fecha_creacion DATETIME(3)` |
| TIP-04 | Declara `COLLATE=utf8mb4_general_ci` | No declarar collation |

---

## 4. Hallazgos del código de acceso a datos

### 4.1 Conteo por archivo

| Archivo | Consultas | `SELECT *` | `DELETE FROM` | `REPLACE INTO` | f-string | Función sobre columna en `WHERE` | `LIKE` |
|---|---|---|---|---|---|---|---|
| `routes/routes_admin.py` | 95 | 26 | 9 | 17 | 2 | 2 | 0 |
| `routes/routes_api.py` | 14 | 0 | 0 | 0 | 9 | 10 | 0 |
| `routes/routes_archivador.py` | 28 | 10 | 3 | 0 | 1 | 0 | 3 |
| `routes/routes_atencion_vehiculo.py` | 12 | 5 | 1 | 0 | 0 | 0 | 1 |
| `routes/routes_auth.py` | 25 | 8 | 0 | 0 | 2 | 0 | 0 |
| `routes/routes_checklists.py` | 33 | 10 | 0 | 0 | 18 | 8 | 6 |
| `routes/routes_events.py` | 14 | 6 | 0 | 0 | 1 | 0 | 2 |
| `routes/routes_inventarios.py` | 49 | 15 | 2 | 0 | 3 | 6 | 0 |
| `routes/routes_nomina.py` | 44 | 7 | 1 | 0 | 1 | 0 | 0 |
| `routes/routes_patients.py` | 30 | 14 | 0 | 0 | 0 | 0 | 4 |
| `routes/routes_personal_operativo.py` | 8 | 2 | 1 | 0 | 0 | 0 | 0 |
| `routes/routes_preoperacional.py` | 11 | 8 | 0 | 0 | 0 | 0 | 2 |
| `routes/routes_programacion_operativa.py` | 30 | 9 | 3 | 0 | 2 | 0 | 0 |
| `routes/routes_registros_global.py` | 8 | 7 | 0 | 0 | 4 | 0 | 7 |
| `routes/routes_reporte_actividades.py` | 8 | 5 | 0 | 0 | 0 | 0 | 0 |
| `routes/routes_reporte_gasto.py` | 21 | 6 | 1 | 0 | 2 | 6 | 2 |
| `routes/routes_ths_sga.py` | 8 | 1 | 1 | 0 | 0 | 0 | 0 |
| `routes/routes_ths_soc.py` | 8 | 1 | 1 | 0 | 0 | 0 | 0 |
| `routes/routes_ths_trip.py` | 21 | 5 | 6 | 0 | 0 | 0 | 0 |
| `routes/routes_voluntariado.py` | 15 | 5 | 0 | 0 | 0 | 0 | 0 |
| `db.py` | 331 | 3 | 1 | 1 | 23 | 0 | 0 |
| `app.py`, `utils.py`, `backup_service.py` y otros | 25 | 4 | 0 | 3 | 6 | 0 | 0 |
| **Total** | **838** | **157** | **30** | **21** | **74** | **32** | **27** |

### 4.2 Hallazgos

| Código | Objeto | Hallazgo | Cambio requerido |
|---|---|---|---|
| ELI-01 | 25 tablas. Las de más impacto: `archivador`, `atencion_vehiculo`, `reporte_gasto`, `nomina`, `inventarios`, `vehiculos`, `personal_operativo`, `ths_*_records`, `ths_contratos`, `aseguradoras` | 30 `DELETE FROM` borran registros de forma física | `UPDATE ... SET activo = 0, fecha_eliminacion = NOW(3)`; requiere antes las columnas de ESTD-01 |
| ELI-01, INT-03 | `routes_nomina.py` (`DELETE FROM nomina`) | Borrar una nómina elimina en cascada todos sus registros de `nomina_empleados`, incluidos los pagos marcados | Eliminación lógica y FK con `RESTRICT` |
| ELI-02 | Todas las consultas de listado | Casi ninguna filtra `activo = 1`, porque la mayoría de tablas no tiene la columna | Agregar el filtro al incorporar eliminación lógica |
| SQL-04, ALM-01 | 157 consultas; las más pesadas son las 14 de `routes_patients.py` y las de `routes_admin.py` sobre `pacientes` | `SELECT *` sobre una tabla de 100 columnas que incluye firmas en `LONGTEXT`, incluso para listados | Listar las columnas que se usan; los listados no traen firmas ni `datos_json` |
| SQL-10 | `routes_admin.py` (17, sobre `configuracion`), `db.py` (`guardar_imagen`, sobre `imagenes`) | `REPLACE INTO` borra y vuelve a crear la fila | `INSERT ... ON DUPLICATE KEY UPDATE` |
| SEG-04 | 74 consultas con f-string | Cumple en lo esencial: lo que se inserta en el texto son nombres de tabla o columna de listas fijas (`CHECKLIST_CONFIG`, `FORM_TYPES`, `tablas_map`, lista `('pasb','pasm','avanzada','tam','tab')`) o marcadores `?`; los valores del usuario van como parámetros | Mantener la lista fija. En `routes_inventarios.py` línea 431 el nombre de tabla se arma con un valor del formulario (`checklist_{origen}`) que se valida unas líneas antes: tomar el nombre de un diccionario fijo para que no dependa de esa validación |
| IDX-08 | `routes_api.py` (10), `routes_checklists.py` (8), `routes_inventarios.py` (6), `routes_reporte_gasto.py` (6) | Funciones sobre la columna en el `WHERE`: `substr(fecha_registro, 1, 10) >= ?`, `UPPER(TRIM(placa)) = ...` | Con fechas reales (TIP-01) se filtra por rango; la placa se guarda ya normalizada y se compara directo |
| IDX-08 | 27 consultas | `LIKE '%texto%'` sobre nombres e identificaciones, y `fecha_registro LIKE ?` para buscar por día | Búsqueda por prefijo o por igualdad donde se pueda; fechas por rango |
| TIP-11 | `routes_registros_global.py`, `routes_archivador.py`, `routes_api.py` | Las fechas se comparan como texto (`fecha + " 00:00:00"`) | Pasar `date`/`datetime` de Python contra columnas de fecha |
| SQL-09 | `routes_registros_global.py`, `routes_admin.py`, `routes_archivador.py`, `routes_patients.py` | Listados sin `LIMIT` (ej. `SELECT * FROM archivador WHERE ... ORDER BY id DESC`) | Paginar |
| SQL-08 | Todas las rutas | `registrado_por`, `fecha_registro`, etc. se asignan en cada ruta, con `ahora().strftime(...)` repetido | Una función común que asigne las columnas de auditoría |
| SQL-03 | Todas las rutas | Cumple: las conexiones se cierran de forma explícita y `app.py` tiene un cierre de respaldo al final de cada solicitud (`close_all()`), que revierte lo no confirmado | — |
| SQL-03 | `db.py` (`ConnectionPool`, máximo 10 conexiones) y todas las rutas | Cada petición abre varias conexiones con `get_db()` (la de la ruta, la de la configuración, la del usuario) y las retiene hasta terminar. Con 6 peticiones al mismo tiempo cada una espera una conexión más y el grupo de 10 se agota: todas quedan bloqueadas 15 s y luego fallan. Lo detectó la prueba del navegador al iniciar sesión (el service worker pide unas 30 páginas a la vez). Hoy no ocurre en producción porque gunicorn atiende una petición a la vez por proceso; ocurriría al activar hilos (`--threads`) o con más carga en el servidor de desarrollo | Reutilizar una sola conexión por petición (guardarla en `flask.g` y cerrarla al final de la petición) en lugar de abrir una por cada `get_db()` |

---

## 5. Seguridad (SEG)

| Código | Objeto | Hallazgo | Cambio requerido |
|---|---|---|---|
| SEG-01 | `configuracion` (clave `smtp_password`), `routes_admin.py` línea 748 | La contraseña del correo se guarda en texto plano en la base. Además sale en cada respaldo | Dejarla solo en variables de entorno, o cifrarla desde la aplicación. Cambiar la contraseña actual después de corregirlo |
| SEG-05 | `backup_service.py` | El respaldo completo de la base (historias clínicas, nómina, cuentas bancarias, hashes de contraseñas) se envía sin cifrar como adjunto de correo | **[DBA]** definir el mecanismo de respaldo. Fuera de política: mientras tanto, cifrar el archivo antes de enviarlo |
| SEG-05 | Repositorio git | `static/uploads/archivador/*.pdf` (documentos de atención colectiva) y `ambulancia.db` están versionados aunque `.gitignore` los excluye | Sacarlos del repositorio. Si tienen datos reales también quedan en el historial de git: **[DBA]** / responsable decide si se limpia |
| SEG-05 | `pacientes`, `calif_atencion`, `segur_paciente`, `ths_*_records`, `nomina_*`, `registro_pagos_*`, `usuarios` (GPS) | Datos sensibles sin identificar en el diseño: historia clínica, datos de menores y acompañantes, cuentas bancarias, pagos, ubicación del personal | Marcarlos en el diseño. **[DBA]** decide cifrado o enmascaramiento |
| SEG-02 | `db.py` (`init_db()`), creación de usuarios | Cumple: hash con `werkzeug`. Observación: la contraseña inicial es el número de identificación del usuario | Fuera de política: generar una clave temporal aleatoria, como ya hace la recuperación de contraseña |
| SEG-06 | Todas las tablas de formularios | La trazabilidad depende de un nombre y una cédula en texto. Si el usuario cambia de nombre o se corrige su cédula, los registros quedan sin dueño | FK a `usuarios` (INT-05) |
| SEG-06 | `usuarios` | Cumple: los usuarios se desactivan (`activo`), no hay `DELETE FROM usuarios` | — |
| SEG-03 | Conexión de la aplicación | **[DBA]** No se puede verificar desde el código qué usuario de MySQL usa producción. Hoy la aplicación necesita permisos de `ALTER`/`CREATE` porque cambia el esquema al iniciar | **[DBA]** definir usuario y permisos |

---

## 6. Control de cambios (CAM)

| Código | Objeto | Hallazgo | Cambio requerido |
|---|---|---|---|
| CAM-01 | `routes_auth.py` línea 55 (`_asegurar_columnas_clave_temporal`) | Una ruta ejecuta `ALTER TABLE usuarios ADD COLUMN` por fuera de `init_db()` | Mover a `init_db()` |
| CAM-03 | `init_db()` | La existencia de columnas se revisa con `DESCRIBE` / `SHOW INDEX` y muchos `ALTER` van en `try/except` que oculta el error. Si un cambio falla, la aplicación arranca igual con el esquema a medias | Consultar `information_schema` y dejar que el error se vea |
| CAM-03 | `init_db()` | Ningún cambio tiene script de reversa | Agregar reversa por cambio (SQL-07) |
| CAM-04 | `init_db()` | Hay cambios destructivos sin respaldo previo: `DROP COLUMN fecha` y `hora` en `atencion_colectiva`, `MODIFY COLUMN` de tipos, `DROP INDEX nombre` | Script de migración de datos previo y revisión del DBA |
| CAM-06 | `init_db()` | Mezcla cambios de esquema con cambios de datos (`UPDATE usuarios`, `INSERT` de catálogos, reescritura de `datos_json`) en la misma ejecución; no se puede revertir como un todo | Separar esquema y datos |
| CAM-02 | `init_db()` | Se comporta distinto según el ambiente (`RENDER`, `MYSQL_HOST`): en local crea la base con otra collation | Mismo código en todos los ambientes |
| SQL-07 | `.gitignore` | Ignora `*.sql`: los scripts de reversa y depuración no entrarían al repositorio | Exceptuar la carpeta de scripts versionados |
| CAM-05 | `pacientes` y tablas de formularios | **[DBA]** Los cambios de tipo en estas tablas reescriben toda la tabla | **[DBA]** definir ventana y método |

---

## 7. Pendientes del DBA y del perfil

| Tema | Pendiente |
|---|---|
| Zona horaria (perfil) | La aplicación escribe hora de Colombia (`ahora()`), pero `routes_auth.py` usa `datetime.now()` sin zona y los defaults `CURRENT_TIMESTAMP` usan la hora del servidor. Existe una clave `migracion_nomina_tz_bogota`, señal de que ya hubo una corrección por este motivo. Definir una sola |
| Versión del motor (perfil) | El respaldo de julio reporta MySQL 9.4 en Railway; `README.md` dice "5.7+ o MariaDB". Confirmar la versión mínima |
| Collation (TIP-04) | Unificar las tres collations en uso |
| Respaldos (ALM-04, SEG-05) | Mecanismo, cifrado y retención |
| Usuario y permisos de la aplicación (SEG-03) | Definir |
| Almacenamiento de binarios (ALM-02) | `imagenes` guarda `LONGBLOB`; las firmas van como texto base64 dentro de cada formulario |
| Vía de cambio (CAM-01) | Confirmar si se mantiene `init_db()` o se pasa a scripts versionados |

---

## 8. Hallazgos según el contexto del producto

Reglas R1 a R10 de `contexto.md`.

| Código | Objeto | Hallazgo | Cambio requerido |
|---|---|---|---|
| SEG-01, R10 | Historial de git (commits `af6221e` del 2026-07-10, `f426519` y `ce5599b` del 2026-07-12) | El archivo `.env` con las contraseñas de MySQL y del correo (SMTP) y la `SECRET_KEY` de Flask se subió al repositorio. Se retiró el 2026-08-23 (`fb481e0`), pero sigue en el historial: cualquiera con acceso al repositorio puede leerlas | Rotar las tres ya. Purgar el historial o crear un repositorio nuevo y limpio |
| R3 | Repositorio `correa1982/new_ambulancia_ranway` | El código está en una cuenta personal de GitHub. No se pudo verificar si es público. Si lo es, el código y las contraseñas del historial están expuestos | Verificar visibilidad; pasar el repositorio a una cuenta de Grupo de Apoyo Medellín |
| R1 | Repositorio | No hay archivo LICENSE ni texto que declare que el software es propiedad de Grupo de Apoyo Medellín | Agregar un archivo LICENSE con la propiedad y el uso reservado |
| R5, SEG-05 | `templates/formulario.html` línea 3664, `static/mapa.js` línea 144 | El navegador llama directo a Nominatim (OpenStreetMap) enviando las coordenadas del lugar de la atención, sin pasar por el backend | Hacer la consulta desde el backend, sin datos del paciente y respetando los términos de uso de Nominatim |
| R6, perfil | 25 llamadas en 9 archivos (`routes_voluntariado.py` 5, `routes_ths_trip.py` 5, `routes_nomina.py` 4, `backup_service.py` 3, y otros) | `datetime.now()` / `date.today()` sin zona: toman la hora del servidor de Railway, no la de Colombia. Existe `ahora()` en `utils.py` pero solo 14 archivos lo usan | Usar siempre `ahora()` / `hoy()` |
| R6 | `routes_inventarios.py` líneas 1064 a 1111 | `ZoneInfo("UTC")` y `ZoneInfo("America/Bogota")` repetidos para corregir fechas guardadas en hora del servidor | Una sola zona en la base (SOL-06) y quitar las conversiones |
| R6 | Rutas y plantillas | Formatos de fecha escritos en cada lugar (`strftime('%Y-%m-%d')` 32 veces, `'%d/%m/%Y'` 7 veces); en el navegador `toLocaleString()` sin cultura y `toLocaleTimeString('es-CO')` | Un helper de formato en Python (filtro Jinja) y uno en JS |

