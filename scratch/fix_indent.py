import re

with open('routes/routes_ths_trip.py', 'r', encoding='utf-8') as f:
    content = f.read()

# The block from line 30 to 86 is indented by 12 spaces instead of 8 spaces.
lines = content.split('\n')
new_lines = []
in_admin_ths_trip = False
for line in lines:
    if "def admin_ths_trip():" in line:
        in_admin_ths_trip = True
        new_lines.append(line)
    elif "def admin_ths_trip_agregar(" in line:
        in_admin_ths_trip = False
        new_lines.append(line)
    else:
        if in_admin_ths_trip and line.startswith("            "):
            new_lines.append(line[4:])
        else:
            new_lines.append(line)

with open('routes/routes_ths_trip.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))
