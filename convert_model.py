import zipfile, tarfile, os
z = zipfile.ZipFile('d:/GitHub/new_ambulancia_ranway/static/vosk/model.zip')
z.extractall('d:/GitHub/new_ambulancia_ranway/static/vosk/temp_model')
with tarfile.open('d:/GitHub/new_ambulancia_ranway/static/vosk/model.tar.gz', 'w:gz') as tar:
    tar.add('d:/GitHub/new_ambulancia_ranway/static/vosk/temp_model/vosk-model-small-es-0.42', arcname='model')
