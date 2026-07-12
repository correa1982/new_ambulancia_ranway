let recognition = null;
let targetTextarea = null;
let dictationBtn = null;
let isRecording = false;
let initialText = ""; // Guardar el texto que tenía el área antes de empezar

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
    // Activamos resultados interinos para una experiencia más fluida, y evitamos la duplicación reconstruyendo todo
    recognition.interimResults = true; 

    recognition.onstart = function() {
        isRecording = true;
        if (dictationBtn) {
            dictationBtn.classList.add('recording');
            dictationBtn.title = "Escuchando... clic para detener";
        }
        // Guardamos el texto actual que tiene el textarea al momento de empezar a grabar
        if (targetTextarea) {
            initialText = targetTextarea.value.trim();
        }
    };

    recognition.onresult = function(event) {
        let finalTranscript = "";
        let interimTranscript = "";

        // Recorremos todos los resultados desde el inicio de esta sesión de dictado
        for (let i = 0; i < event.results.length; i++) {
            let resultText = event.results[i][0].transcript;
            if (event.results[i].isFinal) {
                finalTranscript += resultText;
            } else {
                interimTranscript += resultText;
            }
        }

        if (targetTextarea) {
            // El nuevo valor será el texto original + lo ya finalizado + lo que está entendiendo en este momento
            let newText = initialText;
            if (newText.length > 0 && (finalTranscript.length > 0 || interimTranscript.length > 0)) {
                newText += " ";
            }
            newText += finalTranscript + interimTranscript;
            
            targetTextarea.value = newText;
            
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
