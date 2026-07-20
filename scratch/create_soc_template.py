with open('templates/ths_sga.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('ths_sga', 'ths_soc')
content = content.replace('Documentación Personal de Apoyo Externo', 'Documentación Salud Socorristas')
content = content.replace('THS SGA', 'Salud Socorristas')

with open('templates/ths_soc.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Successfully created ths_soc.html")
