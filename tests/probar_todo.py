"""ProbarTodo: revisa el entorno, la sintaxis y corre TODAS las pruebas.

Uso (desde la carpeta del proyecto):
    python tests/probar_todo.py            -> corrida completa
    python tests/probar_todo.py -k gasto   -> corrida parcial (argumentos de pytest)

En Windows basta con doble clic en tests\\ProbarTodo.bat.

La corrida está bien solo si termina en "N de N, 0 omitidos": todas pasaron y
ninguna se saltó. Las pruebas marcadas como pendientes conocidas (xfail, ligadas
a la solicitud de cambios) se informan aparte y no cuentan como fallo.

Deja el resultado en tests/resultados/ultimo_resultado.md (con fecha y commit),
para usarlo como evidencia.
"""
import importlib
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_RESULTADOS = RAIZ / "tests" / "resultados"
CONFIG_BD = RAIZ / "tests" / "bd_pruebas.local"
CARPETAS_EXCLUIDAS = {".git", "venv", ".venv", "env", "__pycache__", "node_modules", "package",
                      "scratch", ".pytest_cache", "resultados"}
LIBRERIAS = {
    "flask": "Flask", "pymysql": "PyMySQL", "dotenv": "python-dotenv", "werkzeug": "Werkzeug",
    "itsdangerous": "itsdangerous", "openpyxl": "openpyxl", "pandas": "pandas",
    "dateutil": "python-dateutil", "flask_apscheduler": "Flask-APScheduler",
    "flask_compress": "Flask-Compress", "pytest": "pytest", "playwright": "playwright",
}

VERDE, ROJO, AMARILLO, NEGRITA, FIN = "\033[92m", "\033[91m", "\033[93m", "\033[1m", "\033[0m"
if os.name == "nt":
    os.system("")  # activa los colores en la consola de Windows


def titulo(texto):
    print(f"\n{NEGRITA}== {texto} =={FIN}")


def bien(texto):
    print(f"  {VERDE}OK{FIN}    {texto}")


def mal(texto):
    print(f"  {ROJO}FALLA{FIN} {texto}")


def aviso(texto):
    print(f"  {AMARILLO}AVISO{FIN} {texto}")


def ahora_colombia():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Bogota"))
    except Exception:
        return datetime.now()


def git(*argumentos):
    try:
        return subprocess.run(["git", *argumentos], cwd=RAIZ, capture_output=True, text=True,
                              timeout=20).stdout.strip()
    except Exception:
        return ""


# ── 1. Entorno ─────────────────────────────────────────────────────────────
def revisar_entorno():
    titulo("1. Entorno")
    problemas = []
    version = sys.version_info
    if version < (3, 10):
        problemas.append(f"Python {version.major}.{version.minor}: se necesita 3.10 o superior")
        mal(problemas[-1])
    else:
        bien(f"Python {version.major}.{version.minor}.{version.micro}")

    faltantes = []
    for modulo, paquete in LIBRERIAS.items():
        try:
            importlib.import_module(modulo)
        except Exception:
            faltantes.append(paquete)
    if faltantes:
        problemas.append("Faltan librerías: " + ", ".join(faltantes))
        mal(problemas[-1])
        print("        Instálalas con: python -m pip install -r requirements.txt -r requirements-dev.txt")
        if "playwright" in faltantes:
            print("        y después, una sola vez: python -m playwright install chromium")
    else:
        bien("Librerías de requirements.txt y pytest instaladas")

    if "playwright" not in faltantes:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                ruta = Path(p.chromium.executable_path)
            if ruta.exists():
                bien("Navegador de pruebas (Chromium) instalado")
            else:
                problemas.append("Falta el navegador de pruebas")
                mal(problemas[-1])
                print("        Instálalo una sola vez con: python -m playwright install chromium")
        except Exception as error:
            problemas.append(f"No se pudo revisar el navegador de pruebas: {error}")
            mal(problemas[-1])

    if shutil.which("node"):
        bien("Node.js instalado (prueba del modo sin conexión)")
    else:
        aviso("Node.js no está instalado: la prueba del modo sin conexión se omitirá "
              "y la corrida no podrá quedar en '0 omitidos'")

    if CONFIG_BD.exists():
        bien(f"Configuración de la base de pruebas: {CONFIG_BD.relative_to(RAIZ)}")
    else:
        problemas.append("Falta tests/bd_pruebas.local")
        mal(problemas[-1])
        print("        Copia tests/bd_pruebas.ejemplo como tests/bd_pruebas.local y escribe "
              "el usuario y la contraseña de tu MySQL local.")
    return problemas


# ── 2. Sintaxis ────────────────────────────────────────────────────────────
def _archivos(extension):
    for ruta in RAIZ.rglob(f"*{extension}"):
        if not any(parte in CARPETAS_EXCLUIDAS for parte in ruta.relative_to(RAIZ).parts):
            yield ruta


def revisar_sintaxis():
    titulo("2. Sintaxis del código")
    errores = []

    archivos_py = sorted(_archivos(".py"))
    for ruta in archivos_py:
        try:
            compile(ruta.read_text(encoding="utf-8"), str(ruta), "exec")
        except SyntaxError as error:
            errores.append(f"{ruta.relative_to(RAIZ)}, línea {error.lineno}: {error.msg}")
        except UnicodeDecodeError:
            errores.append(f"{ruta.relative_to(RAIZ)}: no está guardado en UTF-8")
    if errores:
        for e in errores:
            mal(e)
    else:
        bien(f"{len(archivos_py)} archivos Python sin errores de sintaxis")

    if shutil.which("node"):
        archivos_js = sorted(list((RAIZ / "static").glob("*.js")) + list((RAIZ / "static" / "js").glob("*.js")))
        errores_js = []
        for ruta in archivos_js:
            resultado = subprocess.run(["node", "--check", str(ruta)], capture_output=True, text=True)
            if resultado.returncode != 0:
                errores_js.append(f"{ruta.relative_to(RAIZ)}: {resultado.stderr.strip().splitlines()[-1] if resultado.stderr.strip() else 'error'}")
        if errores_js:
            for e in errores_js:
                mal(e)
        else:
            bien(f"{len(archivos_js)} archivos JavaScript sin errores de sintaxis")
        errores += errores_js
    return errores


# ── 3. Pruebas ─────────────────────────────────────────────────────────────
def correr_pruebas(argumentos_extra):
    titulo("3. Pruebas automáticas")
    CARPETA_RESULTADOS.mkdir(exist_ok=True)
    xml = CARPETA_RESULTADOS / "pytest.xml"
    if xml.exists():
        xml.unlink()
    comando = [sys.executable, "-m", "pytest", "-q", "-rfEsxX", f"--junitxml={xml}", *argumentos_extra]
    print("  " + " ".join(comando[2:]) + "\n")
    codigo = subprocess.call(comando, cwd=RAIZ)
    return codigo, xml


def leer_resultado(xml):
    """Cuenta los resultados del reporte de pytest. Los xfail (pendientes conocidos) van aparte."""
    r = {"pasaron": 0, "fallaron": [], "omitidos": [], "pendientes": []}
    if not xml.exists():
        return None
    for caso in ET.parse(xml).getroot().iter("testcase"):
        nombre = f"{caso.get('classname', '')}::{caso.get('name', '')}".replace("tests.", "")
        falla = caso.find("failure")
        if falla is None:
            falla = caso.find("error")
        omitido = caso.find("skipped")
        if falla is not None:
            r["fallaron"].append((nombre, " ".join((falla.get("message") or "").split())[:300]))
        elif omitido is not None:
            mensaje = " ".join((omitido.get("message") or "").split())
            if (omitido.get("type") or "") == "pytest.xfail":
                r["pendientes"].append((nombre, mensaje.replace("xfail: ", "", 1)[:200]))
            else:
                r["omitidos"].append((nombre, mensaje[:200]))
        else:
            r["pasaron"] += 1
    return r


# ── 4. Reporte ─────────────────────────────────────────────────────────────
def escribir_reporte(resultado, problemas_entorno, errores_sintaxis, parcial, argumentos_extra):
    fecha = ahora_colombia().strftime("%Y-%m-%d %H:%M")
    commit = git("rev-parse", "--short", "HEAD") or "desconocido"
    rama = git("rev-parse", "--abbrev-ref", "HEAD") or "desconocida"
    sin_commit = bool(git("status", "--porcelain"))

    lineas = ["# Resultado de ProbarTodo", "",
              f"- Fecha: {fecha} (hora de Colombia)",
              f"- Rama y commit: `{rama}` `{commit}`" + (" (con cambios sin commit)" if sin_commit else ""),
              f"- Tipo de corrida: {'parcial (' + ' '.join(argumentos_extra) + ')' if parcial else 'completa'}",
              ""]
    if problemas_entorno or errores_sintaxis:
        lineas.append("## Problemas antes de las pruebas")
        lineas += [f"- {p}" for p in problemas_entorno + errores_sintaxis]
        lineas.append("")

    if resultado is None:
        lineas.append("**Las pruebas no llegaron a ejecutarse.** Revisa el mensaje en la consola.")
    else:
        total = resultado["pasaron"] + len(resultado["fallaron"]) + len(resultado["omitidos"])
        lineas += [f"**{resultado['pasaron']} de {total}, {len(resultado['omitidos'])} omitidos**", "",
                   "| Resultado | Cantidad |", "|---|---|",
                   f"| Pasaron | {resultado['pasaron']} |",
                   f"| Fallaron | {len(resultado['fallaron'])} |",
                   f"| Omitidos | {len(resultado['omitidos'])} |",
                   f"| Pendientes conocidos (xfail) | {len(resultado['pendientes'])} |", ""]
        for titulo_seccion, lista in (("Fallaron", resultado["fallaron"]),
                                      ("Omitidos", resultado["omitidos"]),
                                      ("Pendientes conocidos de la solicitud de cambios", resultado["pendientes"])):
            if lista:
                lineas.append(f"## {titulo_seccion}")
                lineas += [f"- `{nombre}`" + (f": {mensaje}" if mensaje else "") for nombre, mensaje in lista]
                lineas.append("")
    archivo = CARPETA_RESULTADOS / "ultimo_resultado.md"
    CARPETA_RESULTADOS.mkdir(exist_ok=True)
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return archivo, fecha, commit


def main():
    argumentos_extra = sys.argv[1:]
    parcial = bool(argumentos_extra)
    print(f"{NEGRITA}ProbarTodo – aplicación de ambulancias de Grupo de Apoyo Medellín{FIN}")

    problemas = revisar_entorno()
    errores_sintaxis = revisar_sintaxis()

    resultado = None
    if problemas:
        titulo("3. Pruebas automáticas")
        mal("No se corren las pruebas hasta resolver los problemas del entorno.")
    else:
        _, xml = correr_pruebas(argumentos_extra)
        resultado = leer_resultado(xml)
        if resultado and not (resultado["pasaron"] or resultado["fallaron"] or resultado["omitidos"]
                              or resultado["pendientes"]):
            resultado = None  # pytest se detuvo antes de correr pruebas (por ejemplo, sin MySQL)

    archivo, fecha, commit = escribir_reporte(resultado, problemas, errores_sintaxis, parcial, argumentos_extra)

    titulo("Resultado")
    if resultado is None:
        mal("Las pruebas no se ejecutaron.")
        exito = False
    else:
        total = resultado["pasaron"] + len(resultado["fallaron"]) + len(resultado["omitidos"])
        exito = not resultado["fallaron"] and not resultado["omitidos"] and not errores_sintaxis and total > 0
        color = VERDE if exito else ROJO
        print(f"  {color}{NEGRITA}{resultado['pasaron']} de {total}, {len(resultado['omitidos'])} omitidos{FIN}"
              + (f"  ({len(resultado['pendientes'])} pendientes conocidos de la solicitud)" if resultado["pendientes"] else ""))
        if resultado["fallaron"]:
            mal(f"{len(resultado['fallaron'])} prueba(s) fallaron. El detalle está arriba y en el reporte.")
        if resultado["omitidos"]:
            aviso(f"{len(resultado['omitidos'])} prueba(s) se omitieron: " + "; ".join(m for _, m in resultado["omitidos"][:3]))
        if errores_sintaxis:
            mal(f"{len(errores_sintaxis)} archivo(s) con errores de sintaxis.")
        if parcial:
            aviso("Corrida parcial: para la evidencia final corre ProbarTodo sin argumentos.")
    print(f"  Verificado el {fecha} en el commit {commit}")
    print(f"  Reporte: {archivo.relative_to(RAIZ)}")
    return 0 if exito else 1


if __name__ == "__main__":
    sys.exit(main())
