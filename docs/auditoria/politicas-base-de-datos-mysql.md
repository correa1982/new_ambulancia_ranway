# Políticas de base de datos – MySQL

Versión 1.0-MySQL – 2026-11-11
Responsable: DBA del equipo de desarrollo
Producto: aplicación de ambulancias de Grupo de Apoyo Medellín (Flask + PyMySQL, sin ORM)

Cada regla tiene un código (NOM, ESTD, TIP, INT, ELI, IDX, ALM, SEG, CAM, SQL) que se cita en los hallazgos y en la solicitud de cambios.

---

## 0. Instrucciones para el agente

Estas reglas son obligatorias. Aplícalas en todo diseño, revisión, script o código de acceso a datos que generes.

1. Aplica solo las reglas de este documento y el perfil del proyecto (sección 1). No propongas alternativas por fuera de ellas.
2. Cita el código de la regla (ej. `TIP-02`) cada vez que señales un hallazgo o justifiques un cambio.
3. Si una solicitud contradice una regla, no generes el cambio. Indica la regla afectada y pide confirmación al responsable.
4. Si un caso no está cubierto, dilo en una línea con la etiqueta **"Fuera de política"** y propone una opción. No la presentes como regla.
5. Las acciones marcadas **[DBA]** no las implementes. Solo señálalas como pendiente del DBA.
6. No propongas cambios de charset ni de collation, ni configuraciones de servidor (`my.cnf`, variables globales, `sql_mode`, `time_zone`). Las tablas nuevas no declaran `CHARSET` ni `COLLATE`: heredan los de la base (ver TIP-04).
7. Respuestas breves: qué cambiar, en qué objeto y la regla que aplica.
8. Las reglas aplican a objetos nuevos y a los que se modifiquen. No corrijas la deuda existente si no se pide; solo repórtala. Los hallazgos de las revisiones se registran en un archivo aparte (`hallazgos.md`), no en este documento.

---

## 1. Perfil del proyecto (parametrizable por equipo)

| Parámetro | Valor para Ambulancia |
|---|---|
| Motor | MySQL 8.0.16 o superior, InnoDB. No MariaDB (el `CHECK`, los defaults y la sintaxis difieren) |
| Ambientes | Nube (Railway) y ambiente local / de pruebas |
| Acceso a datos | Sin ORM: SQL manual con PyMySQL a través de `get_db()` (`db.py`) |
| Vía de cambio de esquema | Función `init_db()` de `db.py`, que se ejecuta al iniciar la aplicación |
| Base / esquema | Una sola base por ambiente. Los objetos se referencian sin nombre de base (cambia entre ambientes) |
| Charset / collation | `utf8mb4`, collation de la base. No se declara por tabla |
| Idioma de nombres | Español, `snake_case` en minúscula, sin tildes ni ñ (`tamano`, `extension`) |
| Convención de llave foránea | Sufijo: `{entidad}_id` (ej. `sede_id`, `nomina_id`) |
| Tipo de llave primaria | `INT NOT NULL AUTO_INCREMENT`; `BIGINT` en tablas de alto volumen (historial, auditoría, GPS) |
| Zona horaria de fechas | Pendiente de definir. Hoy la aplicación usa hora de Colombia (`ahora()` en `utils.py`) y los defaults de la base usan la hora del servidor. Una sola para todo el producto |
| Texto | `VARCHAR(n)` con longitud definida. `TEXT` solo por regla TIP-05 |

Los nombres van en minúscula porque en Linux (Railway) MySQL distingue mayúsculas en los nombres de tabla y en Windows (ambiente local) no: `Usuarios` y `usuarios` serían la misma tabla en un ambiente y dos distintas en el otro.

---

## 2. Nomenclatura (NOM)

- **NOM-01** Las tablas van en plural y `snake_case` (`casos`, `sedes`). Las tablas puente combinan ambas entidades (`articulo_adjuntos`). Se usa la misma forma en todo el producto.
- **NOM-02** Las columnas van en `snake_case` y en español. No se mezcla inglés y español (no `created_at` junto a `fecha_registro`; no `ip_address`, usar `direccion_ip`).
- **NOM-03** La PK es `id`. La FK sigue la convención del perfil (`{entidad}_id`).
- **NOM-04** Cuando una tabla tiene varias FK a la misma entidad, el nombre indica el rol más la convención: `tecnico_asignado_id`, `usuario_creador_id`. No se usan nombres sin sufijo (no `registrado_por`, `avalado_por`).
- **NOM-05** Todo constraint e índice lleva nombre explícito. No se permiten nombres generados por MySQL (`nomina_empleados_ibfk_1`, o un índice llamado igual que la columna), porque cambian entre ambientes. Máximo 64 caracteres. El nombre de una FK debe ser único en toda la base.

  | Objeto | Formato |
  |---|---|
  | Llave primaria | Sin nombre: MySQL siempre la llama `PRIMARY` |
  | Llave foránea | `fk_{tabla_hija}_{tabla_padre}_{columna}` |
  | Índice | `ix_{tabla}_{columna1}_{columna2}` |
  | Índice único | `ux_{tabla}_{columnas}` |
  | Default | Sin nombre: en MySQL el default es parte de la columna |
  | Check | `ck_{tabla}_{regla}` |

- **NOM-06** Las columnas estándar se llaman igual en todas las tablas (ver ESTD-01). No se usan variantes (`fecha_registro`, `creado_en`, `created_at`, `fecha_subida` en lugar de `fecha_creacion`).
- **NOM-07** No hay tablas de framework en este proyecto. Si se agrega una librería que cree las suyas, conservan sus nombres originales.
- **NOM-08** Antes de entregar un script, revisar la ortografía de los nombres (ej. `extencion` debe ser `extension`).

---

## 3. Columnas estándar (ESTD)

- **ESTD-01** Toda tabla transaccional y de catálogo tiene estas columnas:

  | Columna | Tipo | Nulo | Default |
  |---|---|---|---|
  | `id` | `INT AUTO_INCREMENT` (PK) | NOT NULL | — |
  | `activo` | `TINYINT(1)` | NOT NULL | `1` |
  | `fecha_creacion` | `DATETIME(3)` | NOT NULL | `CURRENT_TIMESTAMP(3)` |
  | `usuario_creacion_id` | `INT` (FK a `usuarios`) | NOT NULL | — |
  | `fecha_actualizacion` | `DATETIME(3)` | NULL | — |
  | `usuario_actualizacion_id` | `INT` (FK a `usuarios`) | NULL | — |
  | `fecha_eliminacion` | `DATETIME(3)` | NULL | — |

- **ESTD-02** Las tablas de catálogo además tienen `nombre VARCHAR(n) NOT NULL` con índice único (`ux_{tabla}_nombre`) y `orden INT NOT NULL`.
- **ESTD-03** Las tablas puente N:M y las tablas de log o auditoría solo llevan `fecha_creacion` (y `usuario_creacion_id` si aplica).

---

## 4. Tipos de datos (TIP)

- **TIP-01** No se usa `TIMESTAMP` (solo llega al año 2038 y MySQL lo convierte según la zona horaria de la conexión) ni se guardan fechas u horas en columnas de texto. Las fechas se definen según su uso:

  | Tipo | Uso |
  |---|---|
  | `DATETIME(3)` | Auditoría, trazabilidad, control de procesos, logs (fecha y hora con milisegundos) |
  | `DATETIME` | Fechas de negocio con hora que no requieren milisegundos |
  | `DATE` | Fechas sin hora (fecha de pago, fecha de nacimiento, vencimiento de SOAT) |
  | `TIME` | Horas de atención u horarios (horas y minutos) |

  No se usan otras precisiones (`DATETIME(1)`, `(2)`, `(6)`).

- **TIP-02** Los defaults de fecha usan `CURRENT_TIMESTAMP` con la misma precisión de la columna (`DATETIME(3)` → `CURRENT_TIMESTAMP(3)`); si la precisión no coincide, MySQL rechaza la tabla. En consultas se usa `NOW(3)`. No se usa `SYSDATE()`.
- **TIP-03** El texto es `VARCHAR` con longitud definida según el dato real (en MySQL la longitud son caracteres). No se usa `VARCHAR(255)` por costumbre. Referencias:

  | Dato | Tipo |
  |---|---|
  | Nombre de catálogo | `VARCHAR(100)` |
  | Nombre completo de persona | `VARCHAR(200)` |
  | Correo | `VARCHAR(256)` |
  | Dirección IP | `VARCHAR(45)` |
  | Teléfono / extensión | `VARCHAR(20)` |
  | Identificación, iniciales, códigos cortos | `VARCHAR(10)` a `VARCHAR(50)` |
  | URL | `VARCHAR(500)` |
  | Observaciones | `VARCHAR(2000)` |

- **TIP-04** Todo el texto es `utf8mb4`, que ya guarda tildes, ñ, emojis y otros alfabetos. No se usa `NCHAR`/`NVARCHAR` ni el charset `utf8` (`utf8mb3`). Las tablas y columnas nuevas no declaran `CHARSET` ni `COLLATE`: dos tablas con collation distinta fallan o pierden el índice al unirse por texto.
- **TIP-05** `TEXT` / `MEDIUMTEXT` / `LONGTEXT` solo para texto libre que puede superar los 2000 caracteres (notas clínicas largas, firmas en base64, contenido de documentos). Nunca para nombres, códigos, identificaciones, IP, correos, fechas o campos que se filtran, indexan o deben ser únicos.
- **TIP-06** Booleanos: `TINYINT(1) NOT NULL` con default. No se usa `BIT`.
- **TIP-07** Dinero y cantidades exactas: `DECIMAL(19,4)` (o la precisión que defina el negocio). Nunca `FLOAT`, `DOUBLE` ni texto (`VARCHAR`).
- **TIP-08** Duraciones: un entero con la unidad en el nombre (`duracion_meses`, `tiempo_maximo_atencion_minutos`).
- **TIP-09** Binarios (archivos, imágenes): `LONGBLOB` en tabla separada 1:1 de la tabla de metadatos (ver ALM-01).
- **TIP-10** Los UUID se guardan en `CHAR(36)`, solo como identificador público o externo (con índice único). Nunca como llave primaria: en InnoDB la PK ordena físicamente la tabla.
- **TIP-11** El tipo del valor en Python debe coincidir con el de la columna: `int` para enteros, `str` para texto, `date`/`datetime` para fechas, `Decimal` para dinero. Comparar una columna de texto contra un número (o al revés) obliga a MySQL a convertir cada fila y deja de usar el índice.

---

## 5. Integridad y normalización (INT)

- **INT-01** Las columnas son NOT NULL por defecto. Una columna nullable debe justificarse por regla de negocio.
- **INT-02** Toda columna que referencia otra tabla tiene FK. No se permiten relaciones "lógicas" sin constraint. La columna hija tiene exactamente el mismo tipo que la PK del padre (`INT` con `INT`); si no, MySQL no crea la FK.
- **INT-03** Toda FK usa `ON DELETE RESTRICT` y `ON UPDATE RESTRICT`. No se permite `CASCADE` ni `SET NULL`, porque un DELETE hecho desde la base se propagaría a los hijos sin control. Una excepción requiere aprobación del DBA y queda documentada.
- **INT-04** Si un hijo debe pertenecer al mismo padre que otra columna de la fila, se garantiza con una FK compuesta: el padre tiene un índice único `ux_{tabla}_id_{padre}_id (id, {padre}_id)` y el hijo una FK de dos columnas hacia él.
- **INT-05** No se guarda texto en lugar de una FK. Ejemplos: `registrado_por` (nombre) y `registrado_por_identificacion` en lugar de `usuario_creacion_id`.
- **INT-06** No se guardan columnas derivables de otra. Si existe `usuario_creacion_id`, no se repiten en la fila el nombre, el perfil ni el registro médico del usuario, salvo que el negocio exija conservar el valor del momento (se documenta en la tabla).
- **INT-07** No se guardan listas en una columna (valores separados por coma, o un arreglo JSON de perfiles). Van en tabla hija, un registro por valor.
- **INT-08** Los valores enumerados (estado, prioridad, tipo) se modelan con tabla catálogo y FK. Si no hay catálogo, llevan `CHECK` con los valores válidos y su significado documentado. No se usa el tipo `ENUM`.
- **INT-09** Los rangos y reglas simples se validan con `CHECK` con nombre. Ejemplos: calificación entre 1 y 5, porcentaje entre 0 y 100, cantidad >= 0, hora fin > hora inicio.
- **INT-10** Toda llave natural de negocio tiene índice único. Ejemplos: `identificacion` de usuario, placa de vehículo, `nombre` de catálogo, consecutivo por formulario.
- **INT-11** Los contadores y existencias no se almacenan si se pueden calcular de su tabla de detalle. Si se almacenan por rendimiento, se documenta cómo se mantienen sincronizados.
- **INT-12** Los adjuntos se relacionan siempre con una tabla puente (`{entidad}_adjuntos`). No se usa una columna `archivo_url` o `archivo_id` en la entidad, porque limita a un solo adjunto.
- **INT-13** Se usa JSON solo para estructuras de configuración que no se consultan por columna. La columna es de tipo `JSON` (MySQL valida el contenido), no `TEXT`.
- **INT-14** La configuración extensible (plantillas, parámetros) se modela en filas, no en columnas fijas. Una tabla de configuración de una sola fila lleva un `CHECK (id = 1)`.
- **INT-15** Una entidad grande (más de ~30 columnas) se revisa para separar grupos de datos con ciclo de vida propio en tablas 1:1.
- **INT-16** No se dejan modelos paralelos para el mismo concepto (ej. una tabla por cada tipo de checklist con la misma estructura). Se deja uno.

---

## 6. Eliminación y concurrencia (ELI)

- **ELI-01** No hay eliminación física en tablas transaccionales ni catálogos. Se usa eliminación lógica: `activo = 0` y `fecha_eliminacion = NOW(3)`.
- **ELI-02** Las consultas de la aplicación filtran `activo = 1` por defecto. Como no hay ORM, el filtro va escrito en cada consulta o en una vista.
- **ELI-03** La eliminación física solo se hace en depuraciones autorizadas, con script revisado por el DBA y respaldo previo.
- **ELI-04** Las tablas que se actualizan de forma concurrente tienen una columna `version_fila INT NOT NULL DEFAULT 0`. La aplicación actualiza con `SET version_fila = version_fila + 1 ... WHERE id = ? AND version_fila = ?` y, si no se afectó ninguna fila, rechaza el cambio.

---

## 7. Índices (IDX)

- **IDX-01** Toda FK tiene índice con nombre explícito (`ix_...`), creado antes de la FK, salvo que la columna ya sea la primera de otro índice. Si no se crea, MySQL genera uno automático con el nombre de la FK (incumple NOM-05).
- **IDX-02** No se crean índices redundantes. Si `ix_a_x_y (x, y)` existe, sobra `ix_a_x (x)`.
- **IDX-03** Límite de llave: 3072 bytes por índice en InnoDB; con `utf8mb4` cada carácter cuenta 4 bytes, es decir 768 caracteres sumando todas las columnas de texto del índice. No se crean índices únicos sobre textos largos. Si se necesita unicidad sobre un texto extenso, primero se revisa si es necesaria y se normaliza.
- **IDX-04** No se indexan columnas `TEXT` ni `BLOB` (MySQL solo permite indexar un prefijo y eso no garantiza unicidad).
- **IDX-05** Toda tabla tiene PK, y es angosta, creciente y estable (`id INT AUTO_INCREMENT`). En InnoDB la PK ordena la tabla y se copia dentro de cada índice secundario.
- **IDX-06** Los índices adicionales (compuestos o de cobertura) se crean solo con evidencia: `EXPLAIN` / `EXPLAIN ANALYZE`, consultas frecuentes, slow query log o las vistas `sys.schema_unused_indexes` y `sys.schema_redundant_indexes`. Se documenta la consulta que lo justifica. MySQL no tiene `INCLUDE` ni índices filtrados.
- **IDX-07** Las tablas de log, historial y auditoría tienen índice por `fecha_creacion`.
- **IDX-08** Las consultas deben poder usar el índice: sin funciones sobre columnas indexadas en el `WHERE` (`DATE(col)`, `STR_TO_DATE(col)`, `LOWER(col)`), sin `LIKE '%texto'`, sin conversiones implícitas (TIP-11) y sin comparar columnas de collation distinta (TIP-04).

---

## 8. Almacenamiento (ALM)

- **ALM-01** El contenido binario de archivos va en una tabla separada (ej. `archivos_adjuntos_contenido`), relacionada 1:1 con la tabla de metadatos (nombre, mime, tamaño). Las consultas de listado nunca leen la tabla del binario ni usan `SELECT *` sobre ella.
- **ALM-02** **[DBA]** Ubicación física de las tablas de binarios (tablespaces) y límite de tamaño por archivo (`max_allowed_packet`). El agente solo indica que la tabla nueva guarda binarios.
- **ALM-03** El texto extraído de archivos (OCR, contenido para búsqueda) va en una tabla propia ligada al archivo (`archivos_adjuntos_texto`: `archivo_adjunto_id` PK y FK, `texto_extraido`, `fecha_extraccion`). No va en la tabla del binario ni en la tabla de la entidad.
- **ALM-04** **[DBA]** Particionamiento, compresión (`ROW_FORMAT`), y estrategia de retención de logs y respaldos los define el DBA.

---

## 9. Seguridad (SEG)

- **SEG-01** No se guardan contraseñas, llaves privadas, tokens ni secretos en texto plano, ni en la base ni en el repositorio. Van en variables de entorno (`.env` fuera de git, variables de Railway) o cifrados desde la aplicación.
- **SEG-02** Las contraseñas de usuarios se guardan solo como hash (`werkzeug.security.generate_password_hash`).
- **SEG-03** **[DBA]** La aplicación usa un usuario de MySQL propio con permisos mínimos sobre su base. Nunca `root` en producción.
- **SEG-04** Todo acceso a datos usa consultas parametrizadas (marcador `?` de `get_db()`). No se arma SQL con valores de usuario mediante f-strings, `+` ni `.format()`. Los nombres de tabla o columna no se pueden parametrizar: si deben ser dinámicos, salen de una lista fija en el código, nunca de la solicitud.
- **SEG-05** Los datos sensibles (historia clínica y datos personales de pacientes, datos bancarios y de nómina del personal) se identifican en el diseño. **[DBA]** decide si se aplica cifrado o enmascaramiento. Los respaldos, volcados (`.sql`) y archivos con datos reales no se suben al repositorio.
- **SEG-06** La trazabilidad no se pierde: las FK hacia `usuarios` no usan `SET NULL`, y los usuarios se desactivan, no se eliminan.

---

## 10. Control de cambios (CAM)

- **CAM-01** Hay una sola vía para cambiar el esquema según el perfil: `init_db()` en `db.py`. No se hacen cambios manuales en la base (Workbench, consola) ni desde scripts sueltos.
- **CAM-02** El mismo código de `init_db()` se aplica en pruebas y luego en producción. No se ajusta a mano por ambiente.
- **CAM-03** Los cambios son idempotentes: `CREATE TABLE IF NOT EXISTS`, y para columnas, índices y FK (MySQL no tiene `ADD ... IF NOT EXISTS`) se consulta antes `information_schema` (`columns`, `statistics`, `table_constraints`, con `table_schema = DATABASE()`). No se usa `try/except` vacío para ocultar el error de un `ALTER`. Cada cambio incluye su script de reversa.
- **CAM-04** Los cambios que afectan datos existentes (NOT NULL nuevo, eliminación de columnas, cambio de tipo, de texto a fecha) incluyen el script de depuración o migración de datos previo.
- **CAM-05** **[DBA]** Los cambios en tablas grandes (más de 1 millón de filas) se revisan con el DBA para definir ventana y método (`ALGORITHM=INSTANT`/`INPLACE`, `LOCK=NONE`, lotes).
- **CAM-06** En MySQL cada sentencia de esquema (`CREATE`, `ALTER`, `DROP`) confirma la transacción en curso y no se puede deshacer con `ROLLBACK`. No se mezclan cambios de esquema y cambios de datos en la misma transacción.

---

## 11. Reglas por tecnología: sin ORM (Python + PyMySQL)

- **SQL-01** Los `CREATE TABLE` cumplen todas las reglas de las secciones 2 a 10. El equipo crea manualmente índices de FK (IDX-01), nombres de constraints (NOM-05), defaults y `CHECK`. Toda tabla es `ENGINE=InnoDB`.
- **SQL-02** Los objetos se referencian sin nombre de base (`usuarios`, no `railway.usuarios`), porque la base se llama distinto en cada ambiente.
- **SQL-03** Toda operación que modifica datos usa una sola conexión de `get_db()`, hace `commit()` explícito al final y cierra la conexión en `finally` o con `with` (el cierre revierte lo no confirmado). Varias escrituras relacionadas van en la misma transacción.
- **SQL-04** No se usa `SELECT *`. Se listan las columnas.
- **SQL-05** No se baja el nivel de aislamiento (`READ UNCOMMITTED`) para evitar bloqueos. **[DBA]** evalúa el aislamiento a nivel de base.
- **SQL-06** Los parámetros tienen el mismo tipo que la columna que filtran (TIP-11, IDX-08).
- **SQL-07** Los scripts de reversa y de depuración de datos se versionan en el repositorio del proyecto, con el nombre `AAAAMMDD_NN_Descripcion.sql`.
- **SQL-08** Las columnas de auditoría (`fecha_creacion`, `usuario_creacion_id`, `fecha_actualizacion`...) se asignan en una función común, no en cada ruta.
- **SQL-09** Las consultas de listado traen solo las columnas que se muestran y van paginadas (`LIMIT`). No se consulta dentro de un ciclo por cada fila (N+1): se usa `JOIN` o `IN`.
- **SQL-10** No se usa `REPLACE INTO` (borra la fila y la vuelve a crear, lo que cambia el `id` y choca con ELI-01). Se usa `INSERT ... ON DUPLICATE KEY UPDATE`.

---

## 12. Lista de revisión para el agente

Al revisar un modelo, script o cambio de `init_db()`, verificar en este orden y reportar cada incumplimiento con su código de regla:

1. Nombres de tablas, columnas y constraints (NOM).
2. Columnas estándar presentes y con tipo correcto (ESTD).
3. Tipos de datos, longitudes, fechas y defaults (TIP).
4. NOT NULL, FK, cascadas, CHECK, únicos y redundancias (INT).
5. Eliminación lógica y concurrencia (ELI).
6. Índices de FK, redundantes y límites de llave (IDX).
7. Binarios, texto extraído y pendientes de DBA (ALM).
8. Secretos y datos sensibles (SEG).
9. Vía de cambio, idempotencia y depuración de datos (CAM).
10. Reglas de acceso a datos (SQL).

Formato de respuesta de una revisión: `Código | Objeto | Hallazgo | Cambio requerido`.

---

## 13. Referencias oficiales

- Tipos de fecha y hora: https://dev.mysql.com/doc/refman/8.4/en/datetime.html
- Límites de InnoDB (tamaño de llave de índice): https://dev.mysql.com/doc/refman/8.4/en/innodb-limits.html
- Llaves foráneas: https://dev.mysql.com/doc/refman/8.4/en/create-table-foreign-keys.html
- Restricciones CHECK: https://dev.mysql.com/doc/refman/8.4/en/create-table-check-constraints.html
- utf8mb4: https://dev.mysql.com/doc/refman/8.4/en/charset-unicode-utf8mb4.html
- Mayúsculas y minúsculas en nombres: https://dev.mysql.com/doc/refman/8.4/en/identifier-case-sensitivity.html
- Optimización e índices: https://dev.mysql.com/doc/refman/8.4/en/optimization-indexes.html
- PyMySQL: https://pymysql.readthedocs.io/
