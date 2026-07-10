import sys
import os

# Agregamos 'ambulacia' al path
sys.path.append(os.path.abspath('ambulacia'))

from ambulacia.app import app
app.config['TESTING'] = True
app.config['DEBUG'] = True

client = app.test_client()

# Hacemos login en el contexto de prueba
with client.session_transaction() as sess:
    sess['usuario'] = {
        'id': 1,
        'identificacion': '123456',
        'nombre': 'Admin',
        'rol': 'admin',
        'perfil': 'Medico',
        'firma': 'base64...'
    }

try:
    res = client.get('/formulario', follow_redirects=False)
    print("STATUS:", res.status_code)
    if res.status_code == 500:
        print(res.data.decode('utf-8'))
except Exception as e:
    import traceback
    traceback.print_exc()
