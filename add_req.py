import os

file_path = r'd:\GITHUB\render_ambulancia1.1\ambulacia\templates\formulario_mci.html'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

replacements = {
    'name="identificacion_paciente"': 'name="identificacion_paciente" required',
    'name="primer_apellido"': 'name="primer_apellido" required',
    'name="primer_nombre"': 'name="primer_nombre" required',
    'name="fecha_nacimiento"': 'name="fecha_nacimiento" required',
    'name="sexo_biologico"': 'name="sexo_biologico" required',
    'name="triage"': 'name="triage" required'
}

for old, new in replacements.items():
    text = text.replace(old, new)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Updated successfully. Required count:', text.count('required'))
