# Pruebas automáticas – aplicación de ambulancias de Grupo de Apoyo Medellín

Las pruebas recorren toda la aplicación como lo haría una persona: inician sesión con distintos usuarios, abren todas las páginas, envían los formularios y revisan que nada falle. Se corren en tu computador con un solo comando.

## Qué revisan

| Archivo | Qué prueba |
|---|---|
| `test_01_base_datos.py` | `init_db()` crea todas las tablas, se puede ejecutar dos veces sin fallar y algunas reglas de la política de base de datos |
| `test_02_inicio_sesion.py` | Login correcto e incorrecto, usuario inactivo, cambio de clave obligatorio, usuario con dos perfiles, cierre de sesión |
| `test_03_formularios.py` | Historia clínica, eventos, atención colectiva, atención vehículo, los 8 checklists y reporte de gasto: envío normal y sincronización offline (sin duplicados) |
| `test_04_recorrido.py` | **Todas las páginas** de la aplicación (la lista sale de la aplicación misma) con administrador, usuario operativo y sin sesión: que no haya errores, que el operativo no vea páginas de administrador y que sin sesión no se vea nada privado |
| `test_05_seguridad.py` | Todos los envíos sin sesión son rechazados, token CSRF, enlaces desde otros sitios, descarga de archivos del servidor, contraseñas con hash |
| `test_06_offline.py` | Modo sin conexión: service worker simulado, versiones de archivos y token para sincronizar |
| `test_07_navegador.py` | **Recorrido en un navegador real (Chromium):** inicia sesión en la pantalla de login, abre todas las páginas revisando que no tengan errores de JavaScript y, para cada formulario que funciona sin conexión, corta el internet, lo guarda en el dispositivo, devuelve el internet y comprueba que llegue a la base una sola vez. También prueba la "señal falsa" y el aviso del preoperacional |

## Antes de la primera vez

1. **MySQL encendido** en tu computador (el mismo que usas para trabajar en local).
2. **Instalar las dependencias**, desde la carpeta del proyecto:

   ```
   python -m pip install -r requirements.txt -r requirements-dev.txt
   python -m playwright install chromium
   ```

   La segunda línea descarga el navegador de pruebas (unos 150 MB, una sola vez).

3. **Configurar la base de pruebas:** copia `tests/bd_pruebas.ejemplo` como `tests/bd_pruebas.local` y escribe el usuario y la contraseña de tu MySQL local. `bd_pruebas.local` no se sube a git.

   - La base `ambulancia_test` la crean las pruebas solas. **Se borra y se vuelve a crear en cada corrida.**
   - Por seguridad, las pruebas no arrancan si el nombre de la base no termina en `_test` o si el servidor no es tu computador.
   - Las pruebas no leen tu archivo `.env` para conectarse, así que no tocan la base de producción aunque el `.env` apunte a ella.
   - No se envían correos: el envío se simula.

4. Opcional: tener **Node.js** instalado para la prueba del modo sin conexión. Si no está, esa prueba se omite.

## Cómo correrlas: ProbarTodo

Doble clic en `tests\ProbarTodo.bat`. Hace todo en orden:

1. **Entorno:** versión de Python, librerías instaladas, Node.js y el archivo `tests/bd_pruebas.local`.
2. **Sintaxis:** revisa que ningún archivo Python o JavaScript tenga errores de escritura.
3. **Pruebas:** corre todas las pruebas.
4. **Resultado:** muestra `N de N, 0 omitidos` y lo guarda con la fecha y el commit en `tests/resultados/ultimo_resultado.md` (no se sube a git). Ese archivo sirve como evidencia.

La corrida está bien **solo** si termina en verde con `N de N, 0 omitidos`: todas pasaron y ninguna se saltó. Para que no quede ninguna omitida hay que tener Node.js instalado.

Para una corrida parcial: `tests\ProbarTodo.bat -k formularios`. Sirve mientras se corrige algo, pero la evidencia final siempre es la corrida completa.

Sin ProbarTodo también se puede usar pytest directamente, desde la carpeta del proyecto:

```
python -m pytest
```

Algunas variantes útiles:

| Comando | Para qué |
|---|---|
| `python -m pytest -x` | Se detiene en el primer error |
| `python -m pytest -k formularios` | Solo las pruebas cuyo nombre contiene "formularios" |
| `python -m pytest tests/test_04_recorrido.py` | Solo el recorrido de páginas |
| `python -m pytest -v` | Muestra cada prueba con su resultado |

## Cómo leer el resultado

ProbarTodo muestra `N de N, 0 omitidos` y aparte los pendientes conocidos. Con pytest directo el resumen se ve como `350 passed, 2 xfailed, 1 skipped`:

- **passed:** la prueba funcionó.
- **failed:** algo no funciona. El detalle dice qué página o formulario y qué respondió.
- **xfailed:** incumplimiento ya conocido y registrado en `docs/auditoria/solicitud-cambios.md` (por ejemplo SOL-04). No es un error nuevo.
- **xpassed:** un incumplimiento conocido ya se corrigió; hay que quitarle la marca `xfail` a esa prueba.
- **skipped:** la prueba se omitió (por ejemplo, porque falta Node.js).

## Cuándo correrlas

Antes de cada commit que cambie el código, y siempre antes de publicar en Railway.

Si agregas una página nueva que recibe un número (por ejemplo `/algo/ver/<int:id>`), el recorrido falla con el mensaje "Ruta nueva: indicar en TABLA_POR_RUTA..." hasta que la agregues a esa lista en `test_04_recorrido.py`, indicando de qué tabla tomar el registro.
