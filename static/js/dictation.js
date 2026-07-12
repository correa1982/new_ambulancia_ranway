let recognition = null;
let targetTextarea = null;
let dictationBtn = null;
let isRecording = false;

function initSpeechRecognition() {
    // Si ya existe, no la recreamos
    if (recognition) return true;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
        alert("El dictado de voz nativo no es soportado por este navegador. Intenta usar Google Chrome.");
        return false;
    }

    recognition = new SpeechRecognition();
    recognition.lang = 'es-ES'; // Idioma español
    recognition.continuous = true; // Sigue escuchando aunque haya pausas
    recognition.interimResults = false; // Solo resultados finales consolidados

    recognition.onstart = function() {
        isRecording = true;
        if (dictationBtn) {
            dictationBtn.classList.add('recording');
            dictationBtn.title = "Escuchando... clic para detener";
        }
    };

    recognition.onresult = function(event) {
        let transcript = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                transcript += event.results[i][0].transcript;
            }
        }

        if (transcript.trim().length > 0 && targetTextarea) {
            let currentVal = targetTextarea.value.trim();
            if (currentVal) {
                targetTextarea.value = currentVal + " " + transcript.trim();
            } else {
                targetTextarea.value = transcript.trim();
            }
            // Disparar evento input para que otros scripts (como autoguardado) lo detecten
            targetTextarea.dispatchEvent(new Event('input', { bubbles: true }));
        }
    };

    recognition.onerror = function(event) {
        console.error("Speech Recognition Error:", event.error);
        if (event.error === 'network') {
            alert("Error de red: El motor de voz de tu dispositivo no tiene descargado el paquete offline de idioma español.");
        } else if (event.error === 'not-allowed') {
            alert("Permiso denegado para usar el micrófono.");
        }
        stopDictation();
    };

    recognition.onend = function() {
        // Si se detiene automáticamente por silencio largo, reseteamos el botón
        stopDictation();
    };

    return true;
}

function startDictation(btn, targetEl) {
    targetTextarea = targetEl;
    dictationBtn = btn;

    if (isRecording) {
        stopDictation();
        return;
    }

    if (initSpeechRecognition()) {
        try {
            recognition.start();
        } catch (err) {
            // Manejar caso donde ya está iniciado
            console.warn("Recognition ya estaba corriendo", err);
        }
    }
}

function stopDictation() {
    isRecording = false;
    if (recognition) {
        try {
            recognition.stop();
        } catch(e) {}
    }
    
    if (dictationBtn) {
        dictationBtn.classList.remove('recording');
        dictationBtn.title = "Dictado de voz";
    }
}
