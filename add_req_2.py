import os

file_path = r'd:\GITHUB\render_ambulancia1.1\ambulacia\templates\formulario_mci.html'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

replacements = {
    'name="tipo_documento" id="tipo_documento"': 'name="tipo_documento" id="tipo_documento" required',
    'name="tipo_afiliacion"': 'name="tipo_afiliacion" required',
    'name="aseguradora"': 'name="aseguradora" required',
    'name="motivo_consulta"': 'name="motivo_consulta" required',
    'name="enfermedad_actual"': 'name="enfermedad_actual" required'
}

for old, new in replacements.items():
    text = text.replace(old, new)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated successfully. Added required to remaining fields.')
