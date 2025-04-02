let recognition = null;
let isRecording = false;
let currentTranscriptionTimeout = null;
let currentSessionId = null;
let translationsEnabled = true;
let translationsRemaining = 200;

function scrollToBottom() {
    const translationsDiv = document.getElementById('translations');
    if (translationsDiv && !window.preventScroll) {
        const scrollOptions = {
            top: translationsDiv.scrollHeight,
            behavior: 'smooth'
        };
        
        try {
            translationsDiv.scrollTo(scrollOptions);
        } catch (error) {
            translationsDiv.scrollTop = translationsDiv.scrollHeight;
        }
        
        setTimeout(() => {
            if (translationsDiv.scrollTop + translationsDiv.clientHeight < translationsDiv.scrollHeight) {
                translationsDiv.scrollTop = translationsDiv.scrollHeight;
            }
        }, 100);
    }
}

function loadPreviousConversations() {
    fetch('/get_previous_conversations')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.conversations && data.conversations.length > 0) {
                // Hide empty state and show translations
                const emptyState = document.getElementById('empty-state');
                if (emptyState) emptyState.style.display = 'none';
                
                const translationsDiv = document.getElementById('translations');
                if (translationsDiv) {
                    translationsDiv.style.display = 'block';
                    translationsDiv.innerHTML = ''; // Clear existing translations

                    // Add all conversations
                    data.conversations.forEach(conv => {
                        const translationItem = document.createElement('div');
                        translationItem.className = 'translation-item';
                        translationItem.id = `translation-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                        translationItem.innerHTML = `
                            <div class="translation-meta">
                                <span>${conv.timestamp}</span>
                                <span>${conv.language}</span>
                            </div>
                            <div class="text-container">
                                <div class="text-wrapper">
                                    <p class="translation-text">${conv.transcript}</p>
                                    <button class="copy-button" aria-label="Copy original text">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                                        </svg>
                                    </button>
                                </div>
                                <div class="text-wrapper">
                                    <p class="translated-text">${conv.translated_text}</p>
                                    <button class="copy-button" aria-label="Copy translated text">
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        `;
                        translationsDiv.appendChild(translationItem);
                    });

                    // Set the session ID and language selections
                    if (data.session_id) {
                        currentSessionId = data.session_id;
                    }

                    const inputLangSelect = document.getElementById('input-language-select');
                    if (inputLangSelect) {
                        inputLangSelect.value = data.input_language || 'en';
                    }

                    const targetLangSelect = document.getElementById('target-language-select');
                    if (targetLangSelect) {
                        targetLangSelect.value = data.target_language || 'en';
                    }

                    // Initialize copy buttons and scroll to bottom
                    addCopyButtonFunctionality();
                    scrollToBottom();
                }
            } else {
                console.log('No previous conversations found');
                // Show empty state
                const emptyState = document.getElementById('empty-state');
                if (emptyState) emptyState.style.display = 'block';
                
                const translationsDiv = document.getElementById('translations');
                if (translationsDiv) translationsDiv.style.display = 'none';
            }
        })
        .catch(error => {
            console.error('Error loading previous conversations:', error);
            // Set default languages even if loading fails
            const inputLangSelect = document.getElementById('input-language-select');
            if (inputLangSelect) inputLangSelect.value = 'en';
            
            const targetLangSelect = document.getElementById('target-language-select');
            if (targetLangSelect) targetLangSelect.value = 'en';
        });
}

function initializeSpeechRecognition() {
    window.SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || window.mozSpeechRecognition || window.msSpeechRecognition;
    
    if (window.SpeechRecognition) {
        recognition = new window.SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;

        const languageSelect = document.getElementById('input-language-select');
        recognition.lang = languageSelect.value || 'en';

        recognition.onstart = () => {
            createRealtimeContainer();
        };

        recognition.onresult = (event) => {
            let interimTranscript = '';
            let finalTranscript = '';

            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                } else {
                    interimTranscript += transcript;
                }
            }

            updateRealtimeTranscription(finalTranscript, interimTranscript);

            if (finalTranscript) {
                clearTimeout(currentTranscriptionTimeout);
                currentTranscriptionTimeout = setTimeout(() => {
                    if (finalTranscript.trim()) {
                        addTranscriptionItem(finalTranscript.trim());
                        createRealtimeContainer();
                    }
                }, 1500);
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            if (event.error === 'not-allowed') {
                alert('Please allow microphone access to use the speech recognition feature.');
            }
            stopRecording();
        };

        recognition.onend = () => {
            if (isRecording) {
                try {
                    recognition.start();
                } catch (e) {
                    console.error('Failed to restart recognition:', e);
                    stopRecording();
                }
            }
        };

        document.addEventListener('visibilitychange', () => {
            if (document.hidden && isRecording) {
                stopRecording();
            }
        });
    } else {
        alert('Speech recognition is not supported in this browser. Please use Chrome, Edge, Safari, or Firefox.');
        const recordButton = document.getElementById('record-button');
        if (recordButton) {
            recordButton.disabled = true;
        }
    }
}

function createRealtimeContainer() {
    const translationsDiv = document.getElementById('translations');
    const existingContainer = document.getElementById('realtime-transcription');
    if (existingContainer) {
        existingContainer.remove();
    }

    const realtimeContainer = document.createElement('div');
    realtimeContainer.id = 'realtime-transcription';
    realtimeContainer.className = 'translation-item current';
    realtimeContainer.innerHTML = `
        <div class="translation-meta">
            <span>${new Date().toLocaleTimeString()}</span>
            <span>${document.getElementById('input-language-select').options[document.getElementById('input-language-select').selectedIndex].text}</span>
        </div>
        <p class="translation-text"></p>
    `;
    translationsDiv.appendChild(realtimeContainer);
    scrollToBottom();
}

function updateRealtimeTranscription(finalTranscript, interimTranscript) {
    const realtimeContainer = document.getElementById('realtime-transcription');
    if (realtimeContainer) {
        const transcriptElement = realtimeContainer.querySelector('.translation-text');
        if (transcriptElement) {
            transcriptElement.textContent = (finalTranscript + ' ' + interimTranscript).trim();
            scrollToBottom();
        }
    }
}

function updateRecognitionLanguage() {
    const languageSelect = document.getElementById('input-language-select');
    if (recognition) {
        recognition.lang = languageSelect.value || 'en';
        if (isRecording) {
            stopRecording();
            startRecording();
        }
    }
}

function addTranscriptionItem(transcript) {
    if (!transcript || transcript.trim().length === 0) return;
    
    const translationsDiv = document.getElementById('translations');
    const timestamp = new Date().toLocaleTimeString();
    const itemId = 'translation-' + Date.now();
    
    const translationItem = document.createElement('div');
    translationItem.className = 'translation-item';
    translationItem.id = itemId;
    translationItem.innerHTML = `
        <div class="translation-meta">
            <span>${timestamp}</span>
            <span>${document.getElementById('input-language-select').options[document.getElementById('input-language-select').selectedIndex].text}</span>
        </div>
        <div class="text-wrapper">
            <div class="text-line">
                <p class="translation-text">${transcript}</p>
                <button class="copy-button" aria-label="Copy original text">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                </button>
            </div>
            <div class="text-line">
                <p class="translated-text loading">
                    <span class="loading-text">Translating</span>
                    <span class="loading-dots"></span>
                </p>
                <button class="copy-button" aria-label="Copy translated text">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                        <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
                    </svg>
                </button>
            </div>
        </div>
    `;
    
    translationsDiv.appendChild(translationItem);
    scrollToBottom();
    
    // Initialize copy buttons for the new item
    addCopyButtonFunctionality();
    
    translateText(transcript, itemId);
    
    // Reinitialize AI features after adding new content
    initializeAIFeatures();
}

function updateTranslation(itemId, translatedText, sessionId) {
    const item = document.getElementById(itemId);
    if (item) {
        const translatedElement = item.querySelector('.translated-text');
        if (translatedElement) {
            if (translatedText.startsWith('Error:')) {
                translatedElement.classList.add('error');
                translatedElement.textContent = translatedText.substring(7); // Remove 'Error: ' prefix
            } else {
                translatedElement.classList.remove('error');
                translatedElement.textContent = translatedText;
            }
            translatedElement.classList.remove('loading');
            
            // Update currentSessionId when receiving a translation
            if (sessionId) {
                currentSessionId = sessionId;
            }
        }
    }
}

function translateText(transcript, itemId) {
    if (translationsRemaining <= 0) {
        translationsEnabled = false;
        const translationToggle = document.getElementById('translation-toggle');
        if (translationToggle) {
            translationToggle.checked = false;
            translationToggle.disabled = true;
        }
        alert('You have used all your available translations. Please contact support for more.');
        return;
    }

    fetch('/process_patient', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            transcript: transcript,
            target_language: document.getElementById('target-language-select').value || 'en',
            input_language: document.getElementById('input-language-select').value || 'en',
            translations_enabled: translationsEnabled
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(err => {
                throw new Error(err.error || 'Translation failed');
            });
        }
        return response.json();
    })
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        updateTranslation(itemId, data.translated_text, data.session_id);
        if (translationsEnabled && data.translated_text !== "Translations were disabled") {
            translationsRemaining = data.translations_remaining;
            updateCounters();
        }
        // Reinitialize AI features after translation is complete
        initializeAIFeatures();
    })
    .catch(error => {
        console.error('Translation error:', error);
        const errorMessage = error.message || 'Translation failed. Please try again.';
        updateTranslation(itemId, `Error: ${errorMessage}`);
        // Reinitialize AI features even if there's an error
        initializeAIFeatures();
    });
}

function toggleRecording() {
    if (!recognition) {
        initializeSpeechRecognition();
    }

    const button = document.getElementById('record-button');
    const buttonText = button.querySelector('span:last-child');
    
    if (!isRecording) {
        startRecording();
        button.classList.add('recording');
        button.innerHTML = `
            <span class="button-content">
                <svg class="mic-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" y1="19" x2="12" y2="23"/>
                    <line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
                <span>Stop Recording</span>
            </span>`;
    } else {
        stopRecording();
        button.classList.remove('recording');
        button.innerHTML = `
            <span class="button-content">
                <svg class="mic-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
                    <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
                    <line x1="12" y1="19" x2="12" y2="23"/>
                    <line x1="8" y1="23" x2="16" y2="23"/>
                </svg>
                <span>Start Recording</span>
            </span>`;
    }
}

function startRecording() {
    if (recognition) {
        clearTimeout(currentTranscriptionTimeout);
        try {
            recognition.start();
            isRecording = true;
            document.getElementById('empty-state').style.display = 'none';
            document.getElementById('translations').style.display = 'block';
        } catch (e) {
            console.error('Failed to start recording:', e);
            stopRecording();
        }
    }
}

function stopRecording() {
    if (recognition) {
        clearTimeout(currentTranscriptionTimeout);
        recognition.stop();
        isRecording = false;
        const realtimeContainer = document.getElementById('realtime-transcription');
        if (realtimeContainer) {
            realtimeContainer.remove();
        }
    }
}

function toggleTheme() {
    const body = document.body;
    const isDark = body.getAttribute('data-theme') === 'dark';
    body.setAttribute('data-theme', isDark ? 'light' : 'dark');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
}

function initializeAIFeatures() {
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    const generateSummaryButton = document.getElementById('generate-summary-button');
    
    if (chatInput && sendButton) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
        
        sendButton.addEventListener('click', sendChatMessage);
    }
    
    // Add generate summary button initialization here
    if (generateSummaryButton) {
        // Remove any existing event listeners
        generateSummaryButton.removeEventListener('click', generateSummary);
        // Add new event listener
        generateSummaryButton.addEventListener('click', generateSummary);
    }
}

function sendChatMessage() {
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');
    
    if (!chatInput || !chatMessages) return;
    
    const message = chatInput.value.trim();
    if (!message) return;
    
    // Add user message
    const userMessage = document.createElement('div');
    userMessage.className = 'chat-message user';
    userMessage.textContent = message;
    chatMessages.appendChild(userMessage);

    // Add loading message
    const loadingMessage = document.createElement('div');
    loadingMessage.className = 'chat-message loading';
    loadingMessage.innerHTML = `
        <div class="loading-spinner"></div>
        AI is thinking
        <div class="typing-dots">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    chatMessages.appendChild(loadingMessage);
    
    chatInput.value = '';
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // Send request to backend
    fetch('/chat_with_ai', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message: message,
            session_id: currentSessionId
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        loadingMessage.remove();
        if (data.response) {
            const aiMessage = document.createElement('div');
            aiMessage.className = 'chat-message ai';
            aiMessage.textContent = data.response;
            chatMessages.appendChild(aiMessage);
        } else {
            throw new Error('No response from AI');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        loadingMessage.remove();
        
        const errorMessage = document.createElement('div');
        errorMessage.className = 'chat-message error';
        errorMessage.textContent = 'Sorry, there was an error processing your request.';
        chatMessages.appendChild(errorMessage);
    })
    .finally(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    });
}

function generateSummary(event) {
    // Prevent default if it's an event
    if (event) {
        event.preventDefault();
    }

    const summaryContent = document.getElementById('summary-content');
    const summaryButton = document.getElementById('generate-summary-button');
    const summaryCopyButton = document.querySelector('.summary-copy-button');
    
    if (!summaryContent || !currentSessionId) {
        console.error('Missing required elements or session ID');
        return;
    }
    
    // Get the current session ID from translations
    const translations = document.querySelectorAll('.translation-item');
    if (translations.length === 0) {
        summaryContent.textContent = 'No conversation available to summarize.';
        summaryCopyButton.style.display = 'none';
        return;
    }
    
    // Disable button and show loading state
    if (summaryButton) {
        summaryButton.disabled = true;
    }
    
    summaryContent.innerHTML = `
        <div class="loading-message">
            <div class="loading-spinner"></div>
            <span>Generating summary...</span>
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    summaryCopyButton.style.display = 'none';
    
    console.log('Generating summary for session:', currentSessionId); // Debug log

    fetch('/generate_summary', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            session_id: currentSessionId
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        if (data.summary) {
            summaryContent.textContent = data.summary;
            summaryCopyButton.style.display = 'flex';
            // Initialize copy functionality for the summary
            initializeSummaryCopyButton();
        } else {
            throw new Error('No summary generated');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        summaryContent.textContent = 'An error occurred while generating the summary. Please try again.';
        summaryCopyButton.style.display = 'none';
    })
    .finally(() => {
        if (summaryButton) {
            summaryButton.disabled = false;
        }
    });
}

// Add this new function to initialize the summary copy button
function initializeSummaryCopyButton() {
    const summaryCopyButton = document.querySelector('.summary-copy-button');
    if (summaryCopyButton) {
        summaryCopyButton.addEventListener('click', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const summaryContent = document.getElementById('summary-content');
            const text = summaryContent.textContent;

            try {
                await navigator.clipboard.writeText(text);
                
                // Change icon to checkmark temporarily
                const icon = this.querySelector('svg');
                icon.innerHTML = document.querySelector('#check-icon-template').innerHTML;
                this.classList.add('copied');

                // Reset after 2 seconds
                setTimeout(() => {
                    icon.innerHTML = document.querySelector('#copy-icon-template').innerHTML;
                    this.classList.remove('copied');
                }, 2000);
            } catch (err) {
                console.error('Failed to copy summary:', err);
            }
        });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.body.setAttribute('data-theme', savedTheme);
    
    // Set default languages before initializing speech recognition
    document.getElementById('input-language-select').value = 'en';
    document.getElementById('target-language-select').value = 'en';
    
    initializeSpeechRecognition();
    initializeAIFeatures();
    loadPreviousConversations();
    
    const themeToggleButton = document.getElementById('theme-toggle');
    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', toggleTheme);
    }
    
    const inputLanguageSelect = document.getElementById('input-language-select');
    if (inputLanguageSelect) {
        inputLanguageSelect.addEventListener('change', updateRecognitionLanguage);
    }

    const translationsDiv = document.getElementById('translations');
    if (translationsDiv) {
        const observer = new MutationObserver((mutations) => {
            // Only scroll if the mutation is not from a copy button action
            if (!mutations.some(mutation => 
                mutation.target.classList.contains('copy-button') || 
                mutation.target.closest('.copy-button')
            )) {
                scrollToBottom();
            }
        });
        observer.observe(translationsDiv, { childList: true, subtree: true });
    }
    
    // Initialize translation toggle with disabled state check
    const translationToggle = document.getElementById('translation-toggle');
    if (translationToggle) {
        // Check if translations are available
        if (translationsRemaining <= 0) {
            translationsEnabled = false;
            translationToggle.checked = false;
            translationToggle.disabled = true;
        } else {
            translationToggle.checked = translationsEnabled;
            translationToggle.disabled = false;
        }

        translationToggle.addEventListener('change', (e) => {
            translationsEnabled = e.target.checked;
        });
    }
    
    // Initialize both counters
    updateCounters();
    
    // Fetch initial translations remaining count
    fetchTranslationsRemaining();

    const targetLanguageSelect = document.getElementById('target-language-select');

    if (translationToggle && targetLanguageSelect) {
        // Set initial state
        targetLanguageSelect.disabled = !translationsEnabled;
        
        translationToggle.addEventListener('change', (e) => {
            translationsEnabled = e.target.checked;
            targetLanguageSelect.disabled = !translationsEnabled;
            
            // Optional: Reset to default value when disabled
            if (!translationsEnabled) {
                targetLanguageSelect.value = 'en';
            }
        });
    }

    // Initialize summary copy button if summary exists
    const summaryContent = document.getElementById('summary-content');
    const summaryCopyButton = document.querySelector('.summary-copy-button');
    if (summaryContent && summaryCopyButton && summaryContent.textContent.trim() !== 'No conversation summary available yet. Start a conversation and click "Generate Summary" to create one.') {
        summaryCopyButton.style.display = 'flex';
        initializeSummaryCopyButton();
    }
});

function showClearConfirmation() {
    const modal = document.getElementById('clearConfirmationModal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function hideClearConfirmation() {
    const modal = document.getElementById('clearConfirmationModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function clearConversation() {
    fetch('/clear_conversation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Clear the translations div
            const translationsDiv = document.getElementById('translations');
            if (translationsDiv) {
                translationsDiv.innerHTML = '';
                translationsDiv.style.display = 'none';
            }
            
            // Show the empty state
            const emptyState = document.getElementById('empty-state');
            if (emptyState) {
                emptyState.style.display = 'flex';
            }
            
            // Reset the summary content
            const summaryContent = document.getElementById('summary-content');
            if (summaryContent) {
                summaryContent.textContent = 'No conversation summary available yet. Start a conversation and click "Generate Summary" to create one.';
            }
            
            // Reset the chat messages
            const chatMessages = document.getElementById('chat-messages');
            if (chatMessages) {
                chatMessages.innerHTML = `
                    <div class="chat-message ai">
                        Hello! I'm your AI medical assistant. I can help answer questions about the conversation or provide additional medical information. How can I help you today?
                    </div>
                `;
            }
            
            // Reset the current session ID
            currentSessionId = null;
        } else {
            console.error('Failed to clear conversation:', data.message);
        }
        
        // Hide the confirmation modal
        hideClearConfirmation();
    })
    .catch(error => {
        console.error('Error clearing conversation:', error);
        hideClearConfirmation();
    });
}

document.addEventListener('DOMContentLoaded', () => {
    // ... (keep existing initialization code)
    
    // Initialize clear conversation button
    const clearButton = document.getElementById('clear-button');
    if (clearButton) {
        clearButton.addEventListener('click', showClearConfirmation);
    }
    
    // Initialize modal buttons
    const cancelClearButton = document.getElementById('cancel-clear');
    const confirmClearButton = document.getElementById('confirm-clear');
    
    if (cancelClearButton) {
        cancelClearButton.addEventListener('click', hideClearConfirmation);
    }
    
    if (confirmClearButton) {
        confirmClearButton.addEventListener('click', clearConversation);
    }
});

function updateCounters() {
    const remainingCounter = document.getElementById('translations-remaining');
    const translationToggle = document.getElementById('translation-toggle');
    
    if (remainingCounter) {
        remainingCounter.textContent = translationsRemaining;
    }
    
    // Update toggle button state
    if (translationToggle && translationsRemaining <= 0) {
        translationsEnabled = false;
        translationToggle.checked = false;
        translationToggle.disabled = true;
    }
}

// Add this function to fetch initial translations remaining
function fetchTranslationsRemaining() {
    fetch('/get_translations_remaining')
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch translations remaining');
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                console.error('Error:', data.error);
                return;
            }
            translationsRemaining = data.translations_remaining;
            updateCounters();
            
            // Disable toggle if no translations remaining
            const translationToggle = document.getElementById('translation-toggle');
            if (translationToggle && translationsRemaining <= 0) {
                translationsEnabled = false;
                translationToggle.checked = false;
                translationToggle.disabled = true;
            }
        })
        .catch(error => {
            console.error('Error fetching translations remaining:', error);
            translationsRemaining = 0;
            updateCounters();
        });
}

// Update the addCopyButtonFunctionality function
function addCopyButtonFunctionality() {
    document.querySelectorAll('.copy-button').forEach(button => {
        button.addEventListener('click', async function(e) {
            // Prevent any default behavior
            e.preventDefault();
            e.stopPropagation();
            
            const textElement = this.parentElement.querySelector('.translation-text, .translated-text');
            const text = textElement.textContent;

            try {
                await navigator.clipboard.writeText(text);
                
                // Change icon to checkmark temporarily
                const icon = this.querySelector('svg');
                icon.innerHTML = document.querySelector('#check-icon-template').innerHTML;
                this.classList.add('copied');

                // Reset after 2 seconds
                setTimeout(() => {
                    icon.innerHTML = document.querySelector('#copy-icon-template').innerHTML;
                    this.classList.remove('copied');
                }, 2000);
            } catch (err) {
                console.error('Failed to copy text:', err);
            }
        });
    });
}

// Make sure to call addCopyButtonFunctionality() after adding new translations
function updateTranslations(translations) {
    // ... your existing code ...
    
    // Add this line after creating new translation items
    addCopyButtonFunctionality();
}