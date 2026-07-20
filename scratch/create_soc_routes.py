import os
import re

with open('routes/routes_ths_sga.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace variables, function names, strings
content = content.replace('ths_sga', 'ths_soc')
content = content.replace('Documentación Personal de Apoyo Externo', 'Documentación Salud Socorristas')
content = content.replace('THS SGA', 'Salud Socorristas')

with open('routes/routes_ths_soc.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("Successfully created routes_ths_soc.py")
