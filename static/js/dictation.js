let recognition = null;
let targetTextarea = null;
let dictationBtn = null;
let isRecording = false;
let lastActivity = 0;
let initialText = "";

const INACTIVITY_TIMEOUT_MS = 4000;

function initSpeechRecognition() {
    if (recognition) return true;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
        if (window.isSecureContext) {
            alert("El dictado de voz no es soportado por este navegador. Intenta usar Google Chrome.");
        } else {
            alert("El dictado de voz requiere una conexión segura (HTTPS o localhost). Esta aplicación se está viendo a través de una conexión no segura.");
        }
        return false;
    }

    recognition = new SpeechRecognition();
    recognition.lang = 'es-ES';
    // Desactivamos continuous para evitar el bug de duplicación en Android Offline
    recognition.continuous = false; 
    recognition.interimResults = true;

    recognition.onstart = function() {
        if (targetTextarea && initialText === "") {
            initialText = targetTextarea.value.trim();
        }
        actualizarEstadoBoton();
    };

    recognition.onresult = function(event) {
        lastActivity = Date.now();
        let interimTranscript = "";
        let finalTranscript = "";

        for (let i = 0; i < event.results.length; i++) {
            let resultText = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += resultText;
            } else {
                interimTranscript += resultText;
            }
        }

        if (targetTextarea) {
            let newText = initialText;
            if (newText.length > 0 && (finalTranscript.length > 0 || interimTranscript.length > 0)) {
                newText += " ";
            }
            newText += finalTranscript + interimTranscript;
            targetTextarea.value = newText;

            if (finalTranscript.length > 0) {
                initialText = newText;
            }

            targetTextarea.dispatchEvent(new Event('input', { bubbles: true }));
        }
    };

    recognition.onerror = function(event) {
        console.error("Speech Recognition Error:", event.error);
        if (event.error === 'network') {
            alert("Error de red: El motor de voz de tu dispositivo no tiene descargado el paquete offline de idioma español.");
            stopDictation();
        } else if (event.error === 'not-allowed') {
            alert("Permiso denegado para usar el micrófono.");
            stopDictation();
        }
        // Si hay otro error leve (como 'no-speech'), onend se encargará de reiniciar si isRecording es true
    };

    recognition.onend = function() {
        if (isRecording) {
            // Solo reiniciamos si hubo actividad de voz reciente; si no, detenemos
            if (Date.now() - lastActivity <= INACTIVITY_TIMEOUT_MS) {
                try {
                    recognition.start();
                } catch (e) {
                    stopDictation();
                }
            } else {
                stopDictation();
            }
        } else {
            actualizarEstadoBoton();
        }
    };

    return true;
}

function actualizarEstadoBoton() {
    if (!dictationBtn) return;
    if (isRecording) {
        dictationBtn.classList.add('recording');
        dictationBtn.title = "Escuchando... clic para detener";
    } else {
        dictationBtn.classList.remove('recording');
        dictationBtn.title = "Dictado de voz";
    }
}

function startDictation(btn, targetEl) {
    if (isRecording && targetTextarea === targetEl) {
        stopDictation();
        return;
    }

    const yaGrabando = isRecording;

    if (yaGrabando && dictationBtn && dictationBtn !== btn) {
        dictationBtn.classList.remove('recording');
        dictationBtn.title = "Dictado de voz";
    }

    targetTextarea = targetEl;
    dictationBtn = btn;
    initialText = "";

    if (initSpeechRecognition()) {
        if (!yaGrabando) {
            isRecording = true;
            try {
                recognition.start();
            } catch (err) {
                console.warn("Recognition ya estaba corriendo", err);
            }
        } else {
            // Cambiar de campo: reiniciamos apuntando al nuevo campo
            lastActivity = Date.now();
            try {
                recognition.stop();
            } catch (e) {}
        }
        actualizarEstadoBoton();
    }
}

function stopDictation() {
    isRecording = false;
    if (recognition) {
        try {
            recognition.stop();
        } catch (e) {}
    }
    actualizarEstadoBoton();
}

document.addEventListener('submit', function() {
    stopDictation();
}, true);

document.addEventListener('visibilitychange', function() {
    if (document.hidden) stopDictation();
});
