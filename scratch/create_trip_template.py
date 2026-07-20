with open('templates/ths_sga.html', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('ths_sga', 'ths_trip')
content = content.replace('THS SGA', 'THS Tripulantes')

with open('templates/ths_trip.html', 'w', encoding='utf-8') as f:
    f.write(content)
print("Successfully created ths_trip.html")
