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
    recognition.lang = 'es-ES';
    // Desactivamos continuous para evitar el bug de duplicación en Android Offline
    recognition.continuous = false; 
    recognition.interimResults = true; 

    recognition.onstart = function() {
        if (dictationBtn) {
            dictationBtn.classList.add('recording');
            dictationBtn.title = "Escuchando... clic para detener";
        }
        if (targetTextarea && initialText === "") {
            initialText = targetTextarea.value.trim();
        }
    };

    recognition.onresult = function(event) {
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
            
            // Si hay un resultado final, lo volvemos el nuevo texto inicial para el siguiente ciclo
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
        // Si el usuario no ha detenido la grabación, la reiniciamos automáticamente
        if (isRecording) {
            try {
                recognition.start();
            } catch (e) {
                // Ignore
            }
        } else {
            // Se detuvo manualmente
            if (dictationBtn) {
                dictationBtn.classList.remove('recording');
                dictationBtn.title = "Dictado de voz";
            }
        }
    };

    return true;
}

function startDictation(btn, targetEl) {
    targetTextarea = targetEl;
    dictationBtn = btn;
    initialText = ""; // Reseteamos el texto inicial al presionar el botón

    if (isRecording) {
        stopDictation();
        return;
    }

    if (initSpeechRecognition()) {
        isRecording = true;
        try {
            recognition.start();
        } catch (err) {
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
