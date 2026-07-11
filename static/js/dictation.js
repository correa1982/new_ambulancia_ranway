let recognitionActive = false;
let voskWorker = null;
let audioContext = null;
let mediaStream = null;
let scriptProcessor = null;
let targetTextarea = null;
let dictationBtn = null;

// Ensure Vosk Worker is initialized early
function initVosk() {
    if (!voskWorker) {
        voskWorker = new Worker('/static/js/vosk_worker.js');
        voskWorker.onmessage = function(e) {
            const data = e.data;
            if (data.action === 'ready') {
                console.log("Vosk model is ready!");
                if (dictationBtn) {
                    dictationBtn.classList.remove('loading');
                    dictationBtn.title = "Dictado de voz listo";
                }
            } else if (data.action === 'partial') {
                // We could show partial text, but for now we append on result
            } else if (data.action === 'result') {
                if (data.text && data.text.trim().length > 0 && targetTextarea) {
                    let currentVal = targetTextarea.value.trim();
                    if (currentVal) {
                        targetTextarea.value = currentVal + " " + data.text;
                    } else {
                        targetTextarea.value = data.text;
                    }
                    targetTextarea.dispatchEvent(new Event('input', { bubbles: true }));
                }
            } else if (data.action === 'error') {
                console.error("Vosk Error:", data.error);
                alert("Error inicializando modelo de voz offline: " + data.error);
                stopVoskDictation();
            }
        };
        voskWorker.postMessage({ action: 'init' });
    }
}

async function startDictation(btn, targetEl) {
    targetTextarea = targetEl;
    dictationBtn = btn;

    if (recognitionActive) {
        stopVoskDictation();
        return;
    }

    if (!voskWorker) {
        btn.classList.add('loading');
        btn.title = "Cargando modelo offline por primera vez (puede demorar un poco)...";
        initVosk();
    }

    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({
            video: false,
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                channelCount: 1,
                sampleRate: 16000
            }
        });

        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        const source = audioContext.createMediaStreamSource(mediaStream);
        
        // Use ScriptProcessorNode for wide compatibility 
        // (AudioWorklet is better but requires serving another file)
        scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
        
        scriptProcessor.onaudioprocess = function(event) {
            if (!recognitionActive) return;
            const channelData = event.inputBuffer.getChannelData(0);
            if (voskWorker) {
                voskWorker.postMessage({ action: 'audio', buffer: channelData }, [channelData.buffer]);
            }
        };

        source.connect(scriptProcessor);
        scriptProcessor.connect(audioContext.destination);

        recognitionActive = true;
        btn.classList.add('recording');
        btn.title = "Escuchando... clic para detener";
        
        if (voskWorker) {
            voskWorker.postMessage({ action: 'reset' });
        }

    } catch (err) {
        console.error("Error accessing microphone:", err);
        alert("No se pudo acceder al micrófono. Verifique permisos y si la página usa HTTPS/Localhost.");
    }
}

function stopVoskDictation() {
    recognitionActive = false;
    
    if (dictationBtn) {
        dictationBtn.classList.remove('recording');
        dictationBtn.title = "Dictado de voz";
    }

    if (scriptProcessor) {
        scriptProcessor.disconnect();
        scriptProcessor = null;
    }
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
}

// Pre-load the model when the page starts (optional but recommended for speed)
window.addEventListener('DOMContentLoaded', () => {
    initVosk();
});
