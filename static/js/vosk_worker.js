importScripts('/static/vosk/vosk.js');

let model;
let recognizer;

onmessage = async function(e) {
    const data = e.data;
    
    if (data.action === 'init') {
        try {
            // Initialize Vosk
            if (typeof Vosk === 'undefined') {
                throw new Error("Vosk.js no se cargó correctamente.");
            }
            
            // In vosk-browser 0.0.8, the API is different.
            // Cargar el modelo en español (ruta al archivo tar.gz)
            model = await Vosk.createModel('/static/vosk/model.tar.gz');
            
            // Inicializar reconocedor a 16kHz
            recognizer = new model.KaldiRecognizer(16000);
            
            recognizer.on("result", (message) => {
                postMessage({ action: 'result', text: message.result.text });
            });
            
            recognizer.on("partialresult", (message) => {
                postMessage({ action: 'partial', text: message.result.partial });
            });
            
            postMessage({ action: 'ready' });
        } catch (err) {
            postMessage({ action: 'error', error: err.toString() });
        }
    } else if (data.action === 'audio') {
        if (recognizer) {
            // Process incoming AudioBuffer chunks (Float32Array)
            try {
                recognizer.acceptWaveform(data.buffer);
            } catch (err) {
                console.error("Vosk audio process error:", err);
            }
        }
    } else if (data.action === 'reset') {
        // recognizer.reset() might not exist in 0.0.8, but we can recreate the recognizer or try removing it
        if (recognizer && typeof recognizer.reset === 'function') {
            recognizer.reset();
        }
    }
};
