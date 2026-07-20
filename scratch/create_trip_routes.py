import os
import re

with open('routes/routes_ths_sga.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace variables, function names, strings
content = content.replace('ths_sga', 'ths_trip')
content = content.replace('THS SGA', 'THS Tripulantes')

# Replace the auth decorator specifically to enforce admin only
auth_decorator_pattern = re.compile(r'def ths_trip_required\(f\):.*?return decorated_function', re.DOTALL)
new_auth_decorator = '''def ths_trip_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))
            
        if session["usuario"].get("rol_real") != "admin" and session["usuario"].get("rol") != "admin":
            flash("No tienes permisos para acceder a la Documentación THS Tripulantes. Solo administradores pueden acceder.", "error")
            return redirect(url_for("dashboard"))
            
        return f(*args, **kwargs)
    return decorated_function'''

content = auth_decorator_pattern.sub(new_auth_decorator, content)

with open('routes/routes_ths_trip.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Successfully created routes_ths_trip.py")
