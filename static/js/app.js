// Global variables
let websocket;
let recognizer;
let isRecording = false;
let sessionId = generateSessionId();
let selectedLanguage = 'en';
let canRecord = true;  // New flag to control recording
let isFirstRecording = true;  // Track first recording

// DOM Elements
const micButton = document.getElementById('micButton');
const micStatus = document.getElementById('micStatus');
const connectionStatus = document.getElementById('connectionStatus');
const transcriptContainer = document.getElementById('transcriptContainer');
const guidanceContainer = document.getElementById('guidanceContainer');
const languageSelect = document.getElementById('languageSelect');
const errorModal = document.getElementById('errorModal');
const errorMessage = document.getElementById('errorMessage');
const closeErrorModal = document.getElementById('closeErrorModal');
const acknowledgeError = document.getElementById('acknowledgeError');

// Templates
const transcriptTemplate = document.getElementById('transcript-template');
const guidanceTemplate = document.getElementById('guidance-template');

// Azure Speech SDK configuration
const speechConfig = {
    subscriptionKey: 'your-key-here',  // Replace with your Azure subscription key
    region: 'centralindia'
};

document.addEventListener('DOMContentLoaded', initialize);

function initialize() {
    console.log('Initializing application...');
    connectWebSocket();
    
    micButton.addEventListener('click', toggleRecording);
    languageSelect.addEventListener('change', handleLanguageChange);
    closeErrorModal.addEventListener('click', hideErrorModal);
    acknowledgeError.addEventListener('click', hideErrorModal);

    // Add event listener for space bar
    document.addEventListener('keydown', handleSpaceBarRecording);
}

// New function to handle space bar recording
function handleSpaceBarRecording(event) {
    // Check if space bar is pressed and no input fields are focused
    if (event.code === 'Space' && 
        document.activeElement.tagName !== 'INPUT' && 
        document.activeElement.tagName !== 'TEXTAREA' &&
        document.activeElement.tagName !== 'SELECT') {
        
        // Prevent default space bar behavior (scrolling)
        event.preventDefault();
        
        // Trigger recording without changing UI
        toggleRecording(true);
    }
}

function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 15);
}

function connectWebSocket() {
    console.log('Connecting to WebSocket...');
    const wsUrl = `ws://localhost:8000/ws/${sessionId}`;  // Direct backend connection
    
    websocket = new WebSocket(wsUrl);
    
    websocket.onopen = () => {
        console.log('WebSocket connected');
        updateConnectionStatus('connected');
        initializeSpeechSDK();
    };
    
    websocket.onmessage = (event) => {
        console.log('Received:', event.data);
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (error) {
            console.error('Error parsing message:', error);
        }
    };
    
    websocket.onclose = () => {
        console.log('WebSocket closed');
        updateConnectionStatus('disconnected');
        setTimeout(connectWebSocket, 3000);
    };
    
    websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        showError('Connection error. Please refresh.');
        updateConnectionStatus('disconnected');
    };
}

function updateConnectionStatus(status) {
    const statusDot = connectionStatus.querySelector('.status-dot');
    const statusText = connectionStatus.querySelector('.status-text');
    
    statusDot.className = 'status-dot ' + status;
    statusText.textContent = status.charAt(0).toUpperCase() + status.slice(1);
}

async function initializeSpeechSDK() {
    try {
        // Wait until SpeechSDK is available
        await waitForSpeechSDK();

        const speechConfigInstance = SpeechSDK.SpeechConfig.fromSubscription(
            speechConfig.subscriptionKey, 
            speechConfig.region
        );

        speechConfigInstance.speechRecognitionLanguage = getLanguageCode(selectedLanguage);
        const audioConfig = SpeechSDK.AudioConfig.fromDefaultMicrophoneInput();

        recognizer = new SpeechSDK.SpeechRecognizer(speechConfigInstance, audioConfig);

        recognizer.recognizing = (s, e) => {
            if (e.result.reason === SpeechSDK.ResultReason.RecognizingSpeech) {
                console.log('Partial:', e.result.text);
            }
        };

        recognizer.recognized = (s, e) => {
            if (e.result.reason === SpeechSDK.ResultReason.RecognizedSpeech) {
                const transcript = e.result.text;
                if (transcript.trim()) {
                    addTranscriptItem('Customer', transcript);
                    websocket.send(JSON.stringify({
                        type: 'audio',
                        transcript: transcript,
                        language: selectedLanguage
                    }));
                }
            }
        };

        recognizer.canceled = (s, e) => {
            console.error('Recognition error:', e.errorDetails);
            showError(`Speech error: ${e.errorDetails}`);
            isRecording = false;
            updateMicUI();
        };

    } catch (error) {
        console.error('Speech init error:', error);
        showError(`Speech setup failed: ${error.message}`);
    }
}

// Wait for Speech SDK to be available
function waitForSpeechSDK() {
    return new Promise((resolve, reject) => {
        let attempts = 0;
        const interval = setInterval(() => {
            if (window.SpeechSDK) {
                clearInterval(interval);
                resolve();
            } else if (++attempts > 20) { // Timeout after ~2 seconds
                clearInterval(interval);
                reject(new Error("Speech SDK failed to load"));
            }
        }, 100);
    });
}

function toggleRecording(isSpaceBar = false) {
    if (!recognizer) {
        showError('Speech not initialized');
        return;
    }
    
    if (!canRecord) {
        showError('Please wait a moment before recording again');
        return;
    }
    
    isRecording = !isRecording;
    spaceBarTriggered = isSpaceBar;

    if (isRecording) {
        // Only clear transcripts and guidance on first recording
        if (isFirstRecording) {
            transcriptContainer.innerHTML = '';
            guidanceContainer.innerHTML = '';
            isFirstRecording = false;
        }
        
        // Start continuous recognition 
        recognizer.startContinuousRecognitionAsync();
    } else {
        recognizer.stopContinuousRecognitionAsync();
    }

    // Only update UI if triggered by mic button click
    if (!isSpaceBar) {
        updateMicUI();
    }
}

function updateMicUI() {
    // Only update UI if not triggered by space bar
    if (!spaceBarTriggered) {
        micButton.classList.toggle('recording', isRecording);
        micStatus.textContent = isRecording ? 'Recording...' : 'Click to start';
    }
    
    // Reset space bar trigger flag
    spaceBarTriggered = false;
}

function handleLanguageChange() {
    selectedLanguage = languageSelect.value;
    if (recognizer) {
        recognizer.stopContinuousRecognitionAsync(() => {
            recognizer.close();
            initializeSpeechSDK();
        });
    }
}

function getLanguageCode(language) {
    const codes = {
        'en': 'en-US', 'es': 'es-ES', 'fr': 'fr-FR',
        'de': 'de-DE','hi': 'hi-IN', 'zh': 'zh-CN', 'ja': 'ja-JP'
    };
    return codes[language] || 'en-US';
}

function addTranscriptItem(role, text) {
    const placeholder = transcriptContainer.querySelector('.transcript-placeholder');
    if (placeholder) placeholder.remove();
    
    const clone = document.importNode(transcriptTemplate.content, true);
    clone.querySelector('.transcript-role').textContent = `${role}:`;
    clone.querySelector('.transcript-text').textContent = text;
    transcriptContainer.appendChild(clone);
    transcriptContainer.scrollTop = transcriptContainer.scrollHeight;
}

function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'guidance':
            addGuidanceItem(data.response_id, data.text);
            break;
        case 'confirmation':
            console.log('Server confirmed:', data.message);
            break;
    }
}

function addGuidanceItem(responseId, text) {
    const placeholder = guidanceContainer.querySelector('.guidance-placeholder');
    if (placeholder) placeholder.remove();
    
    const clone = document.importNode(guidanceTemplate.content, true);
    const guidanceTextElement = clone.querySelector('.guidance-text');
    
    // Store original text and set initial text
    guidanceTextElement.textContent = text;
    guidanceTextElement.setAttribute('data-original-text', text);
    
    clone.querySelectorAll('.feedback-button').forEach(button => {
        button.addEventListener('click', () => {
            // Reset all buttons and text
            button.parentElement.querySelectorAll('.feedback-button').forEach(btn => {
                btn.classList.remove(
                    'selected', 
                    'text-green-500', 
                    'text-red-500', 
                    'scale-125'
                );
            });
            
            // Reset guidance text
            const originalText = guidanceTextElement.getAttribute('data-original-text');
            guidanceTextElement.classList.remove('text-xl', 'font-bold', 'line-through');
            guidanceTextElement.textContent = originalText;
            
            // Apply new styling based on feedback
            if (button.dataset.feedback === 'helpful') {
                button.classList.add('selected', 'text-green-500', 'scale-125');
                guidanceTextElement.classList.add('text-xl', 'font-bold');
            } else {
                button.classList.add('selected', 'text-red-500', 'scale-125');
                guidanceTextElement.classList.add('line-through');
            }
            
            // Send feedback to server
            websocket.send(JSON.stringify({
                type: 'feedback',
                response_id: responseId,
                is_helpful: button.dataset.feedback === 'helpful'
            }));
        });
    });
    
    guidanceContainer.appendChild(clone);
    guidanceContainer.scrollTop = guidanceContainer.scrollHeight;
}

function showError(message) {
    errorMessage.textContent = message;
    errorModal.classList.add('show');
}

function hideErrorModal() {
    errorModal.classList.remove('show');
}

window.addEventListener('beforeunload', () => {
    if (recognizer) recognizer.close();
    if (websocket) websocket.close();
});