import os
import urllib.request
import zipfile
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static', 'vosk')

def download_file(url, dest):
    print(f'Downloading {url} to {dest}...')
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response, open(dest, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        print('Done.')
    except Exception as e:
        print(f"Error downloading {url}: {e}")

def setup():
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)
        
    js_url = "https://cdn.jsdelivr.net/npm/vosk-browser@0.0.8/dist/vosk.js"
    wasm_url = "https://cdn.jsdelivr.net/npm/vosk-browser@0.0.8/dist/vosk.wasm"
    
    js_dest = os.path.join(STATIC_DIR, 'vosk.js')
    wasm_dest = os.path.join(STATIC_DIR, 'vosk.wasm')
    
    if not os.path.exists(js_dest): download_file(js_url, js_dest)
    if not os.path.exists(wasm_dest): download_file(wasm_url, wasm_dest)
    
    model_url = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
    model_zip = os.path.join(STATIC_DIR, 'model.zip')
    model_dir = os.path.join(STATIC_DIR, 'model')
    
    if not os.path.exists(model_dir):
        if not os.path.exists(model_zip):
            download_file(model_url, model_zip)
        print('Extracting model...')
        with zipfile.ZipFile(model_zip, 'r') as zip_ref:
            zip_ref.extractall(STATIC_DIR)
        extracted_folder = os.path.join(STATIC_DIR, 'vosk-model-small-es-0.42')
        if os.path.exists(extracted_folder):
            os.rename(extracted_folder, model_dir)
        os.remove(model_zip)
        print('Model extracted to static/vosk/model')
    else:
        print('Model already exists.')

if __name__ == '__main__':
    setup()
