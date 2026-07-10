import os

file_path = r'd:\GITHUB\render_ambulancia1.1\ambulacia\templates\formulario.html'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'volver' in line.lower() or 'registros' in line.lower():
        if i > 2500:
            print(f'{i+1}: {line.encode("ascii", "ignore").decode("ascii").strip()}')
