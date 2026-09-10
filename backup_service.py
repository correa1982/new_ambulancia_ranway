import gzip
import os
import smtplib
import threading
import traceback
from datetime import datetime
from email.message import EmailMessage

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE_DIR, '.env'))

# Evita que dos ejecuciones (manual y programada) corran al mismo tiempo
_backup_lock = threading.Lock()


def _get_cfg(key, default=None, conn=None):
    """Lee un valor de la tabla `configuracion`; si no existe, usa el default (.env)."""
    try:
        from db import get_db
        if conn is not None:
            row = conn.execute("SELECT valor FROM configuracion WHERE clave = ?", (key,)).fetchone()
        else:
            c = get_db()
            try:
                row = c.execute("SELECT valor FROM configuracion WHERE clave = ?", (key,)).fetchone()
            finally:
                c.close()
        if row and row["valor"]:
            return row["valor"]
        return default
    except Exception:
        return default


def _store_status(status, error=""):
    """Guarda el resultado del último backup en `configuracion` para mostrarlo en el admin."""
    try:
        from db import get_db
        conn = get_db()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('backup_last_status', ?)", (status,))
        conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('backup_last_run', ?)", (ts,))
        conn.execute("REPLACE INTO configuracion (clave, valor) VALUES ('backup_last_error', ?)", (error,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def _dump_database_sql(conn):
    """Genera un dump SQL completo de la base de datos en Python puro (sin mysqldump)."""
    cur = conn.execute("SELECT DATABASE()")
    row = cur.fetchone()
    db_name = list(row.values())[0] if row else "ambulancia_db"

    lines = []
    lines.append("-- Backup generado por Python")
    lines.append(f"-- Base de datos: {db_name}")
    lines.append(f"-- Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("SET NAMES utf8mb4;")
    lines.append("SET FOREIGN_KEY_CHECKS = 0;")
    lines.append("")

    cur = conn.execute("SHOW TABLES")
    tables = [list(t.values())[0] for t in cur.fetchall()]

    for table in tables:
        cur = conn.execute(f"SHOW CREATE TABLE `{table}`")
        create_stmt = cur.fetchone()
        cols = list(create_stmt.values())
        create_sql = cols[1] if len(cols) > 1 else cols[0]
        lines.append(f"DROP TABLE IF EXISTS `{table}`;")
        lines.append(create_sql + ";")
        lines.append("")

        cur = conn.execute(f"SELECT * FROM `{table}`")
        rows = cur.fetchall()
        for row in rows:
            col_names = ', '.join([f"`{k}`" for k in row.keys()])
            vals = []
            for v in row.values():
                if v is None:
                    vals.append('NULL')
                elif isinstance(v, (int, float)):
                    vals.append(str(v))
                else:
                    v_str = str(v).replace("'", "''").replace('\\', '\\\\')
                    vals.append(f"'{v_str}'")
            lines.append(f"INSERT INTO `{table}` ({col_names}) VALUES ({', '.join(vals)});")
        lines.append("")

    lines.append("SET FOREIGN_KEY_CHECKS = 1;")
    return db_name, "\n".join(lines)


def send_backup_email():
    """Genera el dump, lo envía por correo y deja el resultado en `configuracion`.

    Retorna (ok: bool, mensaje: str).
    """
    if not _backup_lock.acquire(blocking=False):
        print("[BACKUP] Ejecución omitida: ya hay un backup en curso.")
        return False, "Ya hay un backup en curso. Intenta de nuevo en unos segundos."

    started = datetime.now()
    try:
        from db import get_db
        conn = get_db()
        try:
            # Configuración SMTP: BD con respaldo en .env
            smtp_host = _get_cfg("smtp_host", os.getenv("SMTP_HOST"), conn)
            smtp_port = _get_cfg("smtp_port", os.getenv("SMTP_PORT", "587"), conn)
            smtp_user = _get_cfg("smtp_user", os.getenv("SMTP_USER"), conn)
            smtp_password = _get_cfg("smtp_password", os.getenv("SMTP_PASSWORD"), conn)
            dest_str = _get_cfg("backup_email_dest", os.getenv("BACKUP_EMAIL_DEST", ""), conn)

            dest_emails = [e.strip() for e in dest_str.split(",") if e.strip()]
            if not dest_emails and smtp_user:
                dest_emails = [smtp_user]

            if not all([smtp_host, smtp_port, smtp_user, smtp_password]):
                raise ValueError("Faltan credenciales SMTP. Configúralas en Configuración o en el .env (SMTP_HOST/SMTP_USER/SMTP_PASSWORD).")

            if not dest_emails:
                raise ValueError("No hay correo destino configurado para el backup.")

            print("[BACKUP] Generando dump de la base de datos...")
            db_name, dump_data = _dump_database_sql(conn)

            print("[BACKUP] Comprimiendo dump...")
            gz_data = gzip.compress(dump_data.encode("utf-8"))

            msg = EmailMessage()
            msg["Subject"] = f"Backup Base de Datos ({db_name}) - {started.strftime('%Y-%m-%d %H:%M:%S')}"
            msg["From"] = smtp_user
            msg["To"] = ", ".join(dest_emails)
            msg.set_content("Adjunto encontrarás la copia de seguridad de la base de datos.")

            filename = f"backup_{db_name}_{started.strftime('%Y%m%d_%H%M%S')}.sql.gz"
            msg.add_attachment(gz_data, maintype="application", subtype="gzip", filename=filename)

            print(f"[BACKUP] Enviando a {len(dest_emails)} correo(s)...")
            with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        finally:
            try:
                conn.close()
            except Exception:
                pass

        ok_msg = f"Backup enviado correctamente a: {', '.join(dest_emails)}"
        print("[BACKUP]", ok_msg)
        _store_status("OK", "")
        return True, ok_msg

    except Exception as e:
        traceback.print_exc()
        _store_status("ERROR", str(e))
        return False, f"Error durante el backup: {e}"

    finally:
        _backup_lock.release()


if __name__ == "__main__":
    ok, msg = send_backup_email()
    print(msg)