import sys
import os

sys.path.append(os.path.abspath('ambulacia'))

from ambulacia.app import app
app.config['TESTING'] = True
app.config['DEBUG'] = True

client = app.test_client()

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
    # Simular POST request de guardar borrador
    data = {
        "accion": "borrador",
        "identificacion_paciente": "999888777",
        "tipo_documento": "CC",
        "primer_nombre": "Test",
        "primer_apellido": "Paciente"
    }
    res = client.post('/formulario', data=data, follow_redirects=False)
    print("STATUS:", res.status_code)
    if res.status_code == 500:
        print(res.data.decode('utf-8')[:1000])
except Exception as e:
    import traceback
    traceback.print_exc()
