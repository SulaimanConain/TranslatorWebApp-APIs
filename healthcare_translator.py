import flet as ft
import requests
import os
import re
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import json

# Try importing pymysql, use SQLite as fallback
try:
    import pymysql
    USE_MYSQL = True
except ImportError:
    import sqlite3
    USE_MYSQL = False
    logging.warning("PyMySQL not available, using SQLite instead")

from flet import Colors

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Update the Flask API URL to use local Flask server
FLASK_API_URL = "http://localhost:8800"  # Make sure this matches your Flask server

# Add headers for API authentication if needed
API_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Language code mapping
LANGUAGE_CODES = {
    'ar': 'Arabic',
    'bn': 'Bengali',
    'zh': 'Chinese',
    'en': 'English',
    'fr': 'French',
    'de': 'German',
    'gu': 'Gujarati',
    'hi': 'Hindi',
    'mr': 'Marathi',
    'mn': 'Mongolian',
    'fa': 'Persian',
    'pt': 'Portuguese',
    'pa': 'Punjabi',
    'ru': 'Russian',
    'es': 'Spanish',
    'sv': 'Swedish',
    'ta': 'Tamil',
    'te': 'Telugu',
    'ur': 'Urdu'
}

def detect_language(text):
    """
    Simple language detection based on character sets and common words.
    Returns ISO 639-1 language code.
    """
    # Common words in different languages
    language_markers = {
        'en': ['the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i'],
        'es': ['el', 'la', 'de', 'que', 'y', 'en', 'un', 'ser', 'se', 'no'],
        'fr': ['le', 'la', 'de', 'et', 'un', 'être', 'avoir', 'je', 'pour', 'ne'],
        'de': ['der', 'die', 'das', 'und', 'in', 'zu', 'den', 'ist', 'sie', 'nicht'],
        'ar': ['في', 'من', 'على', 'إلى', 'عن', 'مع', 'هذا', 'كان', 'لكن', 'هل'],
        'hi': ['में', 'की', 'है', 'का', 'यह', 'और', 'को', 'एक', 'से', 'हैं'],
        'zh': ['的', '是', '不', '了', '在', '人', '有', '我', '他', '这'],
    }
    
    # Convert text to lowercase and split into words
    words = text.lower().split()
    
    # Count matches for each language
    matches = {lang: sum(1 for word in words if word in markers) 
              for lang, markers in language_markers.items()}
    
    # If no matches found, default to English
    if not any(matches.values()):
        return 'en'
    
    # Return the language with most matches
    return max(matches.items(), key=lambda x: x[1])[0]

class HealthcareTranslator:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Healthcare Translator"
        
        # Set theme colors
        self.colors = {
            "light": {
                "bg_color": ft.Colors.WHITE,
                "card_bg": ft.Colors.WHITE,
                "text_color": ft.Colors.BLACK,
                "border_color": ft.Colors.BLACK12,
            },
            "dark": {
                "bg_color": "#1a1f2e",
                "card_bg": "#1e293b",
                "text_color": ft.Colors.WHITE,
                "border_color": ft.Colors.WHITE24,
            }
        }
        
        # Initialize theme state
        self.current_theme = "light"
        
        # Set initial theme
        self.apply_theme()
        
        # Initialize login fields with proper references
        self.email_field = ft.Ref[ft.TextField]()
        self.unique_user_id_field = ft.Ref[ft.TextField]()
        self.password_field = ft.Ref[ft.TextField]()
        self.reg_email_field = ft.Ref[ft.TextField]()
        self.reg_password_field = ft.Ref[ft.TextField]()
        
        # Initialize states
        self.current_user = None
        self.current_session = None
        self.translations_enabled = True
        self.is_recording = False
        
        # Initialize UI components
        self.init_ui_components()
        
        # Add JavaScript code for speech recognition
        page.on_web_event = self.handle_web_event
        
        # Add the speech recognition JavaScript
        self.add_speech_recognition_js()
        
        # Apply theme
        self.apply_theme()
        
        # Show login view initially
        self.show_login_view()
        
        # Initialize UI components with improved styling
        self.translations_list = ft.ListView(
            expand=True,
            spacing=10,
            padding=20,
            auto_scroll=True
        )
        
        self.chat_input = ft.TextField(
            label="Ask a question",
            multiline=True,
            min_lines=3,
            max_lines=5,
            expand=True
        )
        
        self.input_language = ft.Dropdown(
            value="en",
            options=[
                ft.dropdown.Option(key=k, text=v)
                for k, v in LANGUAGE_CODES.items()
            ],
            expand=True
        )
        
        self.target_language = ft.Dropdown(
            value="en",
            options=[
                ft.dropdown.Option(key=k, text=v)
                for k, v in LANGUAGE_CODES.items()
            ],
            expand=True
        )
        
        self.record_button = ft.ElevatedButton(
            text="Start Recording",
            icon=ft.Icons.MIC,
            style=self.get_button_style(),
            on_click=self.toggle_recording
        )
        
        # Initialize UI references
        self.translations_counter = ft.Ref[ft.Text]()

    def apply_theme(self):
        """Apply the current theme to all components"""
        theme_colors = self.colors[self.current_theme]
        
        # Set page background and theme
        self.page.bgcolor = theme_colors["bg_color"]
        self.page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=ft.Colors.BLUE_400,
                secondary=ft.Colors.BLUE_200,
                background=theme_colors["bg_color"],
            )
        )
        
        # Update UI if it exists
        if hasattr(self, 'main_content'):
            self.main_content = self.build_ui()
            self.page.clean()
            self.page.add(self.main_content)
        
        self.page.update()

    def toggle_theme(self, e):
        """Toggle between light and dark theme"""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        self.apply_theme()

    def handle_translation_toggle(self, e):
        self.translations_enabled = e.control.value
        self.target_language.disabled = not self.translations_enabled
        if not self.translations_enabled:
            self.target_language.value = self.input_language.value
        self.page.update()

    def toggle_recording(self, e):
        """Toggle recording state and update button appearance"""
        try:
            # Start/stop recording
            self.is_recording = not self.is_recording
            
            if self.is_recording:
                # Request microphone access before starting
                js_code = """
                async function startRecordingWithPermission() {
                    try {
                        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                        stream.getTracks().forEach(track => track.stop());
                        window.startRecording();
                    } catch (err) {
                        window.pageProvider.sendMessage(JSON.stringify({
                            type: 'microphone_permission',
                            status: 'denied',
                            error: err.message
                        }));
                    }
                }
                startRecordingWithPermission();
                """
                self.page.launch_url(f"javascript:{js_code}")
                
                self.record_button.text = "Stop Recording"
                self.record_button.icon = ft.Icons.STOP
                self.record_button.style.bgcolor = ft.Colors.RED_400
                self.show_snackbar("Started listening...")
            else:
                self.page.launch_url("javascript:window.stopRecording()")
                self.record_button.text = "Start Recording"
                self.record_button.icon = ft.Icons.MIC
                self.record_button.style.bgcolor = ft.Colors.BLUE_400
            
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error toggling recording: {str(e)}")
            self.show_error_dialog("Error toggling recording")

    def handle_web_event(self, e):
        """Handle events from JavaScript"""
        try:
            if isinstance(e.data, str):
                try:
                    data = json.loads(e.data)
                    logger.info(f"Received web event data: {data}")
                except:
                    logger.error(f"Invalid event data: {e.data}")
                    return
            else:
                data = e.data
            
            event_type = data.get("type")
            logger.info(f"Received web event: {event_type}")
            
            if event_type == "speech_interim":
                # Show interim transcript immediately without translation
                transcript = data.get("transcript", "").strip()
                if transcript:
                    self.update_interim_transcript(transcript)
                
            elif event_type == "speech_final":
                # Process final transcript and request translation
                transcript = data.get("transcript", "").strip()
                if transcript:
                    # Add original text immediately
                    self.add_translation_to_list(
                        transcript,
                        "Translating...",  # Placeholder while translation is in progress
                        self.input_language.value,
                        datetime.now()
                    )
                    # Request translation
                    if self.translations_enabled:
                        self.request_translation(transcript)
                
            elif event_type == "speech_start":
                # Clear interim display or prepare for new transcription
                self.clear_interim_display()
            
            elif event_type == "speech_end":
                # Clear interim display
                self.clear_interim_display()
            
            elif event_type == "microphone_permission":
                status = data.get("status")
                error = data.get("error", "")
                
                if status == "requesting":
                    self.show_snackbar("Please allow microphone access when prompted")
                elif status == "denied":
                    self.show_error_dialog(
                        "Microphone access denied. Please allow microphone access in your browser settings and refresh the page."
                    )
                elif status == "no_devices":
                    self.show_error_dialog(
                        "No microphones found. Please connect a microphone and click the refresh button."
                    )
                elif status == "error":
                    self.show_error_dialog(f"Microphone error: {error}")
            
            elif event_type == "microphones_list":
                devices = data.get("devices", [])
                logger.info(f"Received microphones: {devices}")
                
                if not devices:
                    self.show_error_dialog(
                        "No microphones detected. Please check your microphone connection and browser permissions."
                    )
                    return
                
                # Update dropdown options
                options = [
                    ft.dropdown.Option(key=device["id"], text=device["label"])
                    for device in devices
                ]
                
                self.microphone_dropdown.options = options
                if options:
                    self.microphone_dropdown.value = options[0].key
                    self.show_snackbar(f"Found {len(options)} microphone(s)")
                
                # Update UI
                self.page.update()
                
        except Exception as e:
            logger.error(f"Error handling web event: {str(e)}")
            self.show_error_dialog(f"Error: {str(e)}")

    def init_ui_components(self):
        """Initialize all UI components"""
        try:
            # Initialize translations list
            self.translations_list = ft.ListView(
                expand=True,
                spacing=10,
                padding=20,
                auto_scroll=True
            )
            
            # Initialize chat history
            self.chat_history = ft.ListView(
                expand=True,
                spacing=10,
                padding=10,
                auto_scroll=True,
                height=300
            )
            
            # Initialize chat input
            self.chat_input = ft.TextField(
                label="Ask a question",
                hint_text="Type your message here...",
                multiline=True,
                min_lines=3,
                max_lines=5,
                expand=True,
                border_color=ft.Colors.BLUE_400,
                text_style=ft.TextStyle(
                    color=ft.Colors.WHITE if self.current_theme == "dark" else ft.Colors.BLACK
                )
            )
            
            # Initialize language dropdowns
            self.input_language = ft.Dropdown(
                value="en",
                options=[
                    ft.dropdown.Option(key=k, text=v)
                    for k, v in LANGUAGE_CODES.items()
                ],
                width=200
            )
            
            self.target_language = ft.Dropdown(
                value="ar",
                options=[
                    ft.dropdown.Option(key=k, text=v)
                    for k, v in LANGUAGE_CODES.items()
                ],
                width=200
            )
            
            # Initialize summary text
            self.summary_text = ft.Text(
                "No conversation summary available yet.",
                size=14,
                color=ft.Colors.WHITE if self.current_theme == "dark" else ft.Colors.BLACK,
                text_align=ft.TextAlign.LEFT,
                selectable=True
            )
            
            # Initialize states
            self.translations_enabled = True
            self.is_recording = False
            
            logger.info("UI components initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing UI components: {str(e)}")
            raise

    def init_microphone(self):
        """Initialize microphone with proper permission handling"""
        try:
            # Use JavaScript to request microphone permissions
            js_code = """
            async function requestMicrophonePermission() {
                try {
                    console.log('Requesting microphone permission...');
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    stream.getTracks().forEach(track => track.stop());
                    
                    window.pageProvider.sendMessage(JSON.stringify({
                        type: 'microphone_permission',
                        status: 'granted'
                    }));
                    
                    // After permission granted, get device list
                    const devices = await navigator.mediaDevices.enumerateDevices();
                    const microphones = devices.filter(device => device.kind === 'audioinput');
                    
                    window.pageProvider.sendMessage(JSON.stringify({
                        type: 'microphones_list',
                        devices: microphones.map(mic => ({
                            id: mic.deviceId,
                            label: mic.label || `Microphone ${microphones.indexOf(mic) + 1}`
                        }))
                    }));
                    
                } catch (err) {
                    console.error('Microphone permission error:', err);
                    window.pageProvider.sendMessage(JSON.stringify({
                        type: 'microphone_permission',
                        status: 'denied',
                        error: err.message
                    }));
                }
            }
            requestMicrophonePermission();
            """
            self.page.launch_url(f"javascript:{js_code}")
            
        except Exception as e:
            logger.error(f"Error initializing microphone: {str(e)}")
            self.show_error_dialog("Failed to initialize microphone")

    def on_microphone_permission_result(self, permission_status):
        """Handle microphone permission result"""
        try:
            if permission_status == ft.PermissionStatus.GRANTED:
                logger.info("Microphone permission granted")
                self.show_snackbar("Microphone access granted")
                # Initialize speech recognition after permission granted
                self.init_speech_recognition()
            else:
                logger.warning("Microphone permission denied")
                self.show_error_dialog(
                    "Microphone access denied. Please allow microphone access in your browser settings."
                )
        except Exception as e:
            logger.error(f"Error handling microphone permission: {str(e)}")

    def init_speech_recognition(self):
        """Initialize speech recognition after permission granted"""
        js_code = """
        if (typeof window.recognition === 'undefined') {
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                window.pageProvider.sendMessage(JSON.stringify({
                    type: 'speech_error',
                    error: 'Speech recognition not supported in this browser. Please use Chrome.'
                }));
                return;
            }

            const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition;
            window.recognition = new SpeechRecognition();
            window.recognition.continuous = true;
            window.recognition.interimResults = true;
            
            window.recognition.onstart = () => {
                console.log('Speech recognition started');
                window.pageProvider.sendMessage(JSON.stringify({
                    type: 'speech_start'
                }));
            };
            
            window.recognition.onend = () => {
                console.log('Speech recognition ended');
                window.pageProvider.sendMessage(JSON.stringify({
                    type: 'speech_end'
                }));
            };
            
            window.recognition.onresult = (event) => {
                let interim_transcript = '';
                let final_transcript = '';
                
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        final_transcript += transcript;
                        window.pageProvider.sendMessage(JSON.stringify({
                            type: 'speech_final',
                            transcript: final_transcript
                        }));
                    } else {
                        interim_transcript += transcript;
                        window.pageProvider.sendMessage(JSON.stringify({
                            type: 'speech_interim',
                            transcript: interim_transcript
                        }));
                    }
                }
            };
            
            window.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                window.pageProvider.sendMessage(JSON.stringify({
                    type: 'speech_error',
                    error: event.error
                }));
            };

            // Functions for controlling recording
            window.startRecording = function() {
                if (!window.recognition) return;
                try {
                    window.recognition.start();
                    console.log('Started recording');
                } catch (e) {
                    console.error('Error starting recording:', e);
                }
            };

            window.stopRecording = function() {
                if (!window.recognition) return;
                try {
                    window.recognition.stop();
                    console.log('Stopped recording');
                } catch (e) {
                    console.error('Error stopping recording:', e);
                }
            };
        }
        """
        self.page.launch_url(f"javascript:{js_code}")

    def update_translations_counter(self):
        """Update the translations remaining counter"""
        try:
            if self.current_user:
                translations_remaining = self.current_user.get('translations_remaining', 0)
                self.translations_counter.value = f"Translations remaining: {translations_remaining}"
                self.page.update()
        except Exception as e:
            logger.error(f"Error updating translations counter: {str(e)}")

    def load_previous_translations(self):
        try:
            if not self.current_user:
                logger.warning("No user logged in")
                return

            logger.info(f"Loading translations for user {self.current_user['id']}")
            
            # Get previous translations
            response = requests.get(
                f"{FLASK_API_URL}/api/translations",
                headers=API_HEADERS,
                params={"user_id": self.current_user['id']}
            )
            
            logger.info(f"Translation response status: {response.status_code}")
            logger.info(f"Translation response content: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    translations = data.get('translations', [])
                    logger.info(f"Loaded {len(translations)} translations")
                    
                    # Clear existing translations
                    self.translations_list.controls.clear()
                    
                    # Add translations to the list
                    for t in translations:
                        self.add_translation_to_list(
                            t['original_text'],
                            t['translated_text'],
                            t['detected_language'],
                            t['timestamp']
                        )
                    
                    # Update the UI
                    self.page.update()
                else:
                    logger.error(f"Failed to load translations: {data.get('error')}")
            else:
                logger.error(f"Failed to load translations: {response.status_code}")
            
        except Exception as e:
            logger.error(f"Failed to load translations: {str(e)}")

    def add_translation_to_list(self, original_text, translated_text, detected_language, timestamp):
        """Add a translation to the translations list"""
        try:
            # Create translation card
            translation_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(
                            f"{timestamp}",
                            size=12,
                            color=ft.Colors.GREY_600
                        ),
                        ft.Text(
                            f"{LANGUAGE_CODES.get(detected_language, detected_language)}",
                            size=12,
                            color=ft.Colors.BLUE_400
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(original_text, selectable=True),
                    ft.Text(translated_text, 
                           selectable=True,
                           color=ft.Colors.BLUE_400)
                ]),
                padding=10,
                bgcolor=ft.Colors.WHITE,
                border=ft.border.all(1, ft.Colors.BLACK12),
                border_radius=8,
                margin=ft.margin.only(bottom=10)
            )
            
            # Add to list
            self.translations_list.controls.insert(0, translation_card)
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error adding translation to list: {str(e)}")

    def copy_to_clipboard(self, text):
        self.page.set_clipboard(text)
        self.show_snackbar("Text copied to clipboard")

    def show_snackbar(self, message):
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()

    def handle_logout(self, e):
        self.current_user = None
        self.current_session = None
        self.translations_list.controls.clear()
        self.show_login_view()

    def show_error_dialog(self, message):
        self.page.dialog = ft.AlertDialog(
            title=ft.Text("Error"),
            content=ft.Text(message),
            actions=[
                ft.TextButton("OK", on_click=lambda _: setattr(self.page.dialog, 'is_open', False))
            ]
        )
        self.page.dialog.is_open = True
        self.page.update()

    def show_success_dialog(self, message):
        self.page.dialog = ft.AlertDialog(
            title=ft.Text("Success"),
            content=ft.Text(message),
            actions=[
                ft.TextButton("OK", on_click=lambda _: setattr(self.page.dialog, 'is_open', False))
            ]
        )
        self.page.dialog.is_open = True
        self.page.update()

    def show_login_view(self):
        """Show the login view"""
        try:
            # Clear the page
            self.page.clean()
            
            # Create login form
            login_form = ft.Container(
                content=ft.Column([
                    ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text("Healthcare Translator", size=24, weight=ft.FontWeight.BOLD),
                                ft.TextField(
                                    ref=self.email_field,
                                    label="Email",
                                    border_color=ft.Colors.BLUE_400,
                                    width=300,
                                    autofocus=True
                                ),
                                ft.TextField(
                                    ref=self.unique_user_id_field,
                                    label="Unique User ID",
                                    border_color=ft.Colors.BLUE_400,
                                    width=300
                                ),
                                ft.TextField(
                                    ref=self.password_field,
                                    label="Password",
                                    password=True,
                                    can_reveal_password=True,
                                    border_color=ft.Colors.BLUE_400,
                                    width=300
                                ),
                                ft.ElevatedButton(
                                    text="Login",
                                    style=ft.ButtonStyle(
                                        color=ft.Colors.WHITE,
                                        bgcolor=ft.Colors.BLUE_400,
                                    ),
                                    width=300,
                                    on_click=self.handle_login
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=20),
                            padding=30,
                        ),
                        elevation=4,
                    )
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER),
                expand=True,
                bgcolor=self.colors[self.current_theme]["bg_color"]
            )
            
            # Add the login form to the page
            self.page.add(login_form)
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error showing login view: {str(e)}")
            self.show_error_dialog(f"Error showing login view: {str(e)}")

    def show_loading(self, show: bool, text: str = "Loading..."):
        """Show or hide loading indicator"""
        try:
            if show:
                self.page.splash = ft.ProgressBar()
                self.page.splash_text = text
            else:
                self.page.splash = None
                self.page.splash_text = None
            self.page.update()
        except Exception as e:
            logger.error(f"Error updating loading state: {str(e)}")

    def generate_summary(self, e=None):
        try:
            if not self.current_session:
                self.show_error_dialog("No active session")
                return

            if not self.translations_list.controls:
                self.show_error_dialog("No conversations to summarize")
                return

            # Show loading screen
            self.show_loading(True, "Generating summary... Please wait...")

            logger.info(f"Making request to exposed API for summary... Session ID: {self.current_session}")
            response = requests.post(
                f"{FLASK_API_URL}/api/generate_summary",
                headers=API_HEADERS,
                json={
                    "session_id": self.current_session,
                    "user_id": self.current_user['id']  # Added user_id
                }
            )
            
            logger.info(f"Summary response status: {response.status_code}")
            logger.info(f"Summary response content: {response.text}")

            # Hide loading screen
            self.show_loading(False)

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    summary = data.get('summary', '')
                    if summary:
                        # Update the summary text in the UI
                        self.summary_text.value = summary
                        self.summary_text.color = "white"
                        self.page.update()
                    else:
                        self.show_error_dialog("Generated summary is empty")
                else:
                    self.show_error_dialog(data.get('error', 'Failed to generate summary'))
            else:
                error_msg = response.json().get('error', 'Unknown error')
                self.show_error_dialog(f"Failed to generate summary: {error_msg}")

        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            self.show_error_dialog(f"Error generating summary: {str(e)}")
            self.show_loading(False)

    def add_chat_message(self, message, is_user=True):
        """Add a message to the chat history"""
        self.chat_history.controls.append(
            ft.Container(
                content=ft.Text(
                    message,
                    color=ft.Colors.WHITE if self.current_theme == "dark" else ft.Colors.BLACK,
                    selectable=True
                ),
                bgcolor=ft.Colors.BLUE_400 if is_user else (
                    "#2d3748" if self.current_theme == "dark" else ft.Colors.GREY_100
                ),
                border_radius=10,
                padding=10,
                margin=ft.margin.only(
                    left=40 if is_user else 10,
                    right=10 if is_user else 40
                )
            )
        )
        self.page.update()

    def handle_chat(self, e):
        """Handle chat message submission"""
        try:
            message = self.chat_input.value
            if not message:
                return

            # Add user message to chat
            self.add_chat_message(message, is_user=True)
            
            # Clear input
            self.chat_input.value = ""
            self.page.update()

            # Make API request
            try:
                response = requests.post(
                    f"{FLASK_API_URL}/api/chat",
                    headers=API_HEADERS,
                    json={
                        "message": message,
                        "session_id": self.current_session,
                        "user_id": self.current_user['id']
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('response'):
                        # Add AI response to chat
                        self.add_chat_message(data['response'], is_user=False)
                    else:
                        self.show_error_dialog("No response from AI")
                else:
                    self.show_error_dialog("Failed to get AI response")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Chat request error: {str(e)}")
                self.show_error_dialog(f"Network error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error handling chat: {str(e)}")
            self.show_error_dialog(f"Error: {str(e)}")

    def show_main_view(self):
        """Show main application view"""
        try:
            logger.info("Showing main view...")
            
            # Clear the page first
            self.page.clean()
            
            # Build and add main UI
            self.main_content = self.build_ui()
            if self.main_content:
                self.page.add(self.main_content)
                self.page.update()
                logger.info("Main view loaded successfully")
            else:
                raise Exception("Failed to build main UI")
            
        except Exception as e:
            logger.error(f"Error showing main view: {str(e)}")
            self.show_error_dialog(f"Error loading main view: {str(e)}")

    def build_login_view(self):
        """Build and return the login view"""
        return ft.Container(
            content=ft.Column([
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("Healthcare Translator", size=24, weight=ft.FontWeight.BOLD),
                            ft.TextField(
                                ref=self.email_field,
                                label="Email",
                                border_color=ft.Colors.BLUE_400,
                                width=300,
                                autofocus=True
                            ),
                            ft.TextField(
                                ref=self.unique_user_id_field,
                                label="Unique User ID",
                                border_color=ft.Colors.BLUE_400,
                                width=300
                            ),
                            ft.TextField(
                                ref=self.password_field,
                                label="Password",
                                password=True,
                                can_reveal_password=True,
                                border_color=ft.Colors.BLUE_400,
                                width=300
                            ),
                            ft.ElevatedButton(
                                text="Login",
                                style=ft.ButtonStyle(
                                    color=ft.Colors.WHITE,
                                    bgcolor=ft.Colors.BLUE_400,
                                ),
                                width=300,
                                on_click=self.handle_login
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=20),
                        padding=30,
                    ),
                    elevation=4,
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER),
            expand=True,
            bgcolor=self.colors[self.current_theme]["bg_color"]
        )

    def build_register_view(self):
        """Build and return the registration view"""
        return ft.Container(
            content=ft.Column([
                ft.Card(
                    content=ft.Container(
                        content=ft.Column([
                            ft.Text("Create Account", size=24, weight=ft.FontWeight.BOLD),
                            ft.TextField(
                                ref=self.reg_email_field,
                                label="Email",
                                border_color=ft.Colors.BLUE_400,
                                width=300
                            ),
                            ft.TextField(
                                ref=self.reg_password_field,
                                label="Password",
                                password=True,
                                can_reveal_password=True,
                                border_color=ft.Colors.BLUE_400,
                                width=300
                            ),
                            ft.ElevatedButton(
                                text="Register",
                                style=ft.ButtonStyle(
                                    color=ft.Colors.WHITE,
                                    bgcolor=ft.Colors.BLUE_400,
                                ),
                                width=300,
                                on_click=self.handle_register
                            ),
                            ft.TextButton(
                                text="Already have an account? Login",
                                on_click=self.show_login_view
                            )
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=20),
                        padding=30,
                    ),
                    elevation=4,
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER),
            expand=True,
            bgcolor=self.colors[self.current_theme]["bg_color"]
        )

    def show_register_view(self, e=None):
        """Show registration view"""
        self.page.clean()
        self.page.add(self.build_register_view())

    def handle_register(self, e):
        try:
            first_name = self.first_name_field.value
            last_name = self.last_name_field.value
            email = self.reg_email_field.value
            password = self.reg_password_field.value

            if not all([first_name, last_name, email, password]):
                self.show_error_dialog("Please fill in all fields")
                return

            # Call register API
            try:
                response = requests.post(
                    f"{FLASK_API_URL}/api/register",
                    headers=API_HEADERS,
                    json={
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "password": password
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        unique_id = data.get('unique_user_id')
                        self.show_success_dialog(f"Registration successful! Your Unique User ID is: {unique_id}")
                        self.show_login_view()
                    else:
                        self.show_error_dialog(data.get('error', 'Registration failed'))
                else:
                    self.show_error_dialog("Registration failed")
                    
            except requests.exceptions.RequestException as e:
                self.show_error_dialog(f"Network error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            self.show_error_dialog("Registration failed. Please try again.")

    def handle_login(self, e):
        """Handle login button click"""
        try:
            # Get values from text fields
            email = self.email_field.current.value
            unique_user_id = self.unique_user_id_field.current.value
            password = self.password_field.current.value
            
            # Validate input
            if not all([email, unique_user_id, password]):
                self.show_error_dialog("Please fill in all fields")
                return
            
            # Show loading indicator
            self.show_loading(True, "Logging in...")
            
            try:
                logger.info(f"Attempting login for email: {email}")
                
                response = requests.post(
                    f"{FLASK_API_URL}/api/login",
                    headers=API_HEADERS,
                    json={
                        "email": email,
                        "unique_user_id": unique_user_id,
                        "password": password
                    }
                )
                
                logger.info(f"Login response status: {response.status_code}")
                logger.info(f"Login response content: {response.text}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success'):
                        # Store user data
                        self.current_user = data['user']
                        self.current_session = data['session_id']
                        
                        # Initialize UI components
                        self.init_ui_components()
                        
                        # Set theme
                        theme_colors = self.colors[self.current_theme]
                        self.page.bgcolor = theme_colors["bg_color"]
                        
                        # Clear the page
                        self.page.clean()
                        
                        # Build and show main UI
                        main_content = self.build_ui()
                        if main_content:
                            self.page.add(main_content)
                            self.page.update()
                            
                            # Load previous translations
                            self.load_previous_translations()
                        else:
                            raise Exception("Failed to build main UI")
                    else:
                        error_msg = data.get('error', 'Login failed')
                        logger.error(f"Login failed: {error_msg}")
                        self.show_error_dialog(error_msg)
                else:
                    logger.error(f"Login failed with status code: {response.status_code}")
                    self.show_error_dialog("Invalid credentials")
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error during login: {str(e)}")
                self.show_error_dialog(f"Network error: {str(e)}")
            finally:
                self.show_loading(False)
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            self.show_error_dialog(f"Login error: {str(e)}")
            self.show_loading(False)

    def build_ui(self):
        """Build the main UI components"""
        try:
            logger.info("Building UI components...")
            theme_colors = self.colors[self.current_theme]
            
            # Create main layout
            main_layout = ft.Column([
                # Top navigation bar
                ft.Container(
                    content=ft.Row([
                        ft.Text(
                            "Welcome, te", 
                            color=theme_colors["text_color"]
                        ),
                        ft.Row([
                            ft.IconButton(
                                icon=ft.Icons.DARK_MODE,
                                icon_color=theme_colors["text_color"],
                                tooltip="Toggle theme",
                                on_click=self.toggle_theme
                            ),
                            ft.TextButton(
                                text="Sign Out",
                                style=ft.ButtonStyle(
                                    color=theme_colors["text_color"]
                                ),
                                on_click=self.handle_logout
                            )
                        ])
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=10,
                    bgcolor=theme_colors["card_bg"]
                ),
                
                # Main content area
                ft.Container(
                    content=ft.ResponsiveRow([
                        # Left panel - Translations
                        ft.Column(
                            col={"sm": 12, "md": 12, "lg": 8},
                            controls=[
                                # Translator header
                                ft.Container(
                                    content=ft.Row([
                                        ft.Row([
                                            ft.Icon(ft.Icons.TRANSLATE, color=ft.Colors.BLUE_400, size=24),
                                            ft.Text(
                                                "Universal Translator & Assistant", 
                                                size=16, 
                                                weight=ft.FontWeight.BOLD,
                                                color=theme_colors["text_color"]
                                            )
                                        ]),
                                        ft.Row([
                                            ft.Container(
                                                content=ft.Text(
                                                    f"Translations left: {self.current_user.get('translations_remaining', 0)}",
                                                    color=theme_colors["text_color"]
                                                ),
                                                bgcolor=ft.Colors.BLUE_400,
                                                border_radius=15,
                                                padding=ft.padding.only(left=10, right=10, top=5, bottom=5)
                                            ),
                                            ft.Switch(
                                                label="Translations",
                                                value=True,
                                                label_style=ft.TextStyle(
                                                    color=theme_colors["text_color"]
                                                ),
                                                on_change=self.handle_translation_toggle
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.CLEAR,
                                                icon_color=ft.Colors.BLUE_400,
                                                tooltip="Clear",
                                                on_click=self.handle_clear
                                            )
                                        ])
                                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                    padding=10,
                                    bgcolor=theme_colors["card_bg"]
                                ),

                                # Translations list
                                ft.Container(
                                    content=self.translations_list,
                                    expand=True,
                                    height=500,
                                    padding=10,
                                    bgcolor=theme_colors["card_bg"],
                                    border_radius=8
                                ),

                                # Bottom controls
                                ft.Container(
                                    content=ft.Column([
                                        ft.ResponsiveRow([
                                            ft.Column(
                                                col={"sm": 12, "md": 6},
                                                controls=[
                                                    ft.Dropdown(
                                                        label="Select Transcription Language",
                                                        value="en",
                                                        options=[
                                                            ft.dropdown.Option(key=k, text=v)
                                                            for k, v in LANGUAGE_CODES.items()
                                                        ],
                                                        width=200,
                                                        bgcolor=theme_colors["card_bg"],
                                                        label_style=ft.TextStyle(
                                                            color=theme_colors["text_color"]
                                                        ),
                                                        text_style=ft.TextStyle(
                                                            color=theme_colors["text_color"]
                                                        )
                                                    ),
                                                ]
                                            ),
                                            ft.Column(
                                                col={"sm": 12, "md": 6},
                                                controls=[
                                                    ft.Dropdown(
                                                        label="Target Language(Translation)",
                                                        value="ar",
                                                        options=[
                                                            ft.dropdown.Option(key=k, text=v)
                                                            for k, v in LANGUAGE_CODES.items()
                                                        ],
                                                        width=200,
                                                        bgcolor=theme_colors["card_bg"],
                                                        label_style=ft.TextStyle(
                                                            color=theme_colors["text_color"]
                                                        ),
                                                        text_style=ft.TextStyle(
                                                            color=theme_colors["text_color"]
                                                        )
                                                    ),
                                                ]
                                            ),
                                        ]),
                                        ft.ElevatedButton(
                                            "Start Recording",
                                            icon=ft.Icons.MIC,
                                            style=self.get_button_style(),
                                            width=float("inf"),
                                            on_click=self.toggle_recording
                                        )
                                    ]),
                                    padding=10,
                                    bgcolor=theme_colors["card_bg"],
                                    border_radius=8
                                )
                            ],
                            spacing=10
                        ),

                        # Right panel - Summary and Chat
                        ft.Column(
                            col={"sm": 12, "md": 12, "lg": 4},
                            controls=[
                                # Conversation Summary
                                ft.Container(
                                    content=ft.Column([
                                        ft.Text(
                                            "Conversation Summary", 
                                            size=16, 
                                            weight=ft.FontWeight.BOLD,
                                            color=theme_colors["text_color"]
                                        ),
                                        ft.Container(
                                            content=self.summary_text,
                                            height=200,
                                            bgcolor=theme_colors["card_bg"],
                                            border_radius=5,
                                            padding=10,
                                            margin=ft.margin.only(top=10, bottom=10)
                                        ),
                                        ft.ElevatedButton(
                                            "Generate Summary",
                                            style=self.get_button_style(False),
                                            width=float("inf"),
                                            on_click=self.generate_summary
                                        )
                                    ]),
                                    padding=20,
                                    bgcolor=theme_colors["card_bg"],
                                    border_radius=8
                                ),

                                # AI Assistant
                                ft.Container(
                                    content=ft.Column([
                                        ft.Text(
                                            "AI Assistant", 
                                            size=16, 
                                            weight=ft.FontWeight.BOLD,
                                            color=theme_colors["text_color"]
                                        ),
                                        # Chat history
                                        ft.Container(
                                            content=self.chat_history,
                                            bgcolor=theme_colors["card_bg"],
                                            border_radius=5,
                                            padding=10,
                                            margin=ft.margin.only(top=10, bottom=10)
                                        ),
                                        # Input area
                                        ft.Container(
                                            content=self.chat_input,
                                            bgcolor=theme_colors["card_bg"],
                                            border_radius=5,
                                            padding=10
                                        ),
                                        ft.ElevatedButton(
                                            "Send",
                                            style=self.get_button_style(False),
                                            width=float("inf"),
                                            on_click=self.handle_chat
                                        )
                                    ]),
                                    padding=20,
                                    bgcolor=theme_colors["card_bg"],
                                    border_radius=8
                                )
                            ],
                            spacing=10
                        )
                    ]),
                    padding=20,
                    bgcolor=theme_colors["bg_color"]
                )
            ], expand=True, scroll=True)

            return main_layout

        except Exception as e:
            logger.error(f"Error building UI: {str(e)}")
            raise

    def get_button_style(self, is_primary=True):
        """Get button style with glow effect"""
        return ft.ButtonStyle(
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.BLUE_400,
            shadow_color=ft.Colors.BLUE_400,
            elevation=5 if is_primary else 2,
            animation_duration=300,
            side={
                'width': 1,
                'color': ft.Colors.BLUE_400,
            }
        )

    def add_speech_recognition_js(self):
        """Add speech recognition JavaScript code to the page"""
        js_code = """
        async function initializeSpeechRecognition() {
            if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
                window.pageProvider.sendMessage(JSON.stringify({
                    type: 'speech_error',
                    error: 'Speech recognition is not supported in this browser. Please use Chrome.'
                }));
                return false;
            }

            const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition;
            window.recognition = new SpeechRecognition();
            window.recognition.continuous = true;
            window.recognition.interimResults = true;
            
            // Set language based on input language selection
            window.recognition.lang = 'en-US';  // Default to English
            
            window.recognition.onstart = () => {
                console.log('Speech recognition started');
                // Clear any previous interim results
                window.pageProvider.sendMessage(JSON.stringify({
                    type: 'speech_start'
                }));
            };
            
            window.recognition.onend = () => {
                console.log('Speech recognition ended');
                window.pageProvider.sendMessage(JSON.stringify({
                    type: 'speech_end'
                }));
            };
            
            window.recognition.onresult = (event) => {
                let interim_transcript = '';
                let final_transcript = '';
                
                // Process results
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        final_transcript += transcript;
                        // Send final transcript for translation
                        window.pageProvider.sendMessage(JSON.stringify({
                            type: 'speech_final',
                            transcript: final_transcript
                        }));
                    } else {
                        interim_transcript += transcript;
                        // Send interim transcript for display
                        window.pageProvider.sendMessage(JSON.stringify({
                            type: 'speech_interim',
                            transcript: interim_transcript
                        }));
                    }
                }
            };
            
            window.recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                window.pageProvider.sendMessage(JSON.stringify({
                    type: 'speech_error',
                    error: event.error
                }));
            };
            
            return true;
        }

        async function checkMicrophonePermission() {
            try {
                console.log('Checking microphone permission...');
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                stream.getTracks().forEach(track => track.stop());
                return true;
            } catch (err) {
                console.error('Microphone permission denied:', err);
                window.pageProvider.sendMessage(JSON.stringify({
                    type: 'microphone_permission',
                    status: 'denied',
                    error: err.message
                }));
                return false;
            }
        }

        async function initializeMicrophones() {
            try {
                const hasPermission = await checkMicrophonePermission();
                if (!hasPermission) return [];
                
                const devices = await navigator.mediaDevices.enumerateDevices();
                const microphones = devices.filter(device => device.kind === 'audioinput');
                console.log('Available microphones:', microphones);
                
                window.pageProvider.sendMessage(JSON.stringify({
                    type: 'microphones_list',
                    devices: microphones.map(mic => ({
                        id: mic.deviceId,
                        label: mic.label || `Microphone ${microphones.indexOf(mic) + 1}`
                    }))
                }));
                
                return microphones;
            } catch (err) {
                console.error('Error listing microphones:', err);
                return [];
            }
        }

        // Initialize everything
        if (typeof window.speechInitialized === 'undefined') {
            window.speechInitialized = true;
            
            // Initialize speech recognition
            const speechInitialized = await initializeSpeechRecognition();
            if (!speechInitialized) return;
            
            // Functions for controlling recording
            window.startRecording = async function() {
                if (!window.recognition) {
                    console.error('Speech recognition not initialized');
                    return;
                }
                
                try {
                    const hasPermission = await checkMicrophonePermission();
                    if (!hasPermission) return;
                    
                    window.recognition.start();
                    console.log('Started recording');
                } catch (e) {
                    console.error('Error starting recording:', e);
                    if (e.name === 'NotAllowedError') {
                        window.pageProvider.sendMessage(JSON.stringify({
                            type: 'microphone_permission',
                            status: 'denied',
                            error: 'Microphone access denied'
                        }));
                    }
                }
            };

            window.stopRecording = function() {
                if (window.recognition) {
                    try {
                        window.recognition.stop();
                        console.log('Stopped recording');
                    } catch (e) {
                        console.error('Error stopping recording:', e);
                    }
                }
            };

            window.requestMicrophones = initializeMicrophones;
            
            // Initial microphone detection
            setTimeout(initializeMicrophones, 1000);
        }
        """
        
        self.page.launch_url(f"javascript:{js_code}")

    def refresh_microphones(self, e=None):
        """Refresh the list of available microphones"""
        logger.info("Refreshing microphones...")
        self.page.launch_url("javascript:window.requestMicrophones()")
        self.show_snackbar("Detecting microphones...")

    def update_interim_transcript(self, transcript):
        """Update the interim transcript display"""
        try:
            # Create or update interim transcript display
            if not hasattr(self, 'interim_text'):
                self.interim_text = ft.Text(
                    transcript,
                    color=ft.colors.GREY_400,
                    italic=True,
                    size=14
                )
                self.translations_list.controls.insert(0, self.interim_text)
            else:
                self.interim_text.value = transcript
            self.page.update()
        except Exception as e:
            logger.error(f"Error updating interim transcript: {str(e)}")

    def clear_interim_display(self):
        """Clear the interim transcript display"""
        try:
            if hasattr(self, 'interim_text'):
                if self.interim_text in self.translations_list.controls:
                    self.translations_list.controls.remove(self.interim_text)
                delattr(self, 'interim_text')
                self.page.update()
        except Exception as e:
            logger.error(f"Error clearing interim transcript: {str(e)}")

    def request_translation(self, text):
        """Request translation from the server"""
        try:
            response = requests.post(
                f"{FLASK_API_URL}/api/translate",
                headers=API_HEADERS,
                json={
                    "text": text,
                    "source_lang": self.input_language.value,
                    "target_lang": self.target_language.value,
                    "session_id": self.current_session,
                    "user_id": self.current_user['id']
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    # Update the translation in the list
                    self.update_translation(text, data['translated_text'])
                else:
                    self.show_error_dialog(data.get('error', 'Translation failed'))
            else:
                self.show_error_dialog("Translation request failed")
            
        except Exception as e:
            logger.error(f"Translation request error: {str(e)}")
            self.show_error_dialog(f"Translation error: {str(e)}")

    def update_translation(self, original_text, translated_text):
        """Update the translation in the list"""
        try:
            # Find and update the translation entry
            for control in self.translations_list.controls:
                if isinstance(control, ft.Card):
                    original = control.content.controls[0].value
                    if original == original_text:
                        control.content.controls[1].value = translated_text
                        self.page.update()
                        break
        except Exception as e:
            logger.error(f"Error updating translation: {str(e)}")

    def handle_clear(self, e):
        """Handle clear button click"""
        try:
            def clear_confirmed(e):
                try:
                    # Clear translations list
                    self.translations_list.controls.clear()
                    # Clear chat history
                    self.chat_history.controls.clear()
                    # Clear summary text
                    self.summary_text.value = "No conversation summary available yet."
                    # Update UI
                    self.page.update()
                    # Close dialog
                    dialog.open = False
                except Exception as e:
                    logger.error(f"Error clearing content: {str(e)}")
                    self.show_error_dialog(f"Error clearing content: {str(e)}")

            # Create confirmation dialog
            dialog = ft.AlertDialog(
                modal=True,
                title=ft.Text("Clear All"),
                content=ft.Text("Are you sure you want to clear all conversations and translations?"),
                actions=[
                    ft.TextButton("Cancel", on_click=lambda e: setattr(dialog, 'open', False)),
                    ft.TextButton("Clear", on_click=clear_confirmed)
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            
            # Show dialog
            self.page.dialog = dialog
            dialog.open = True
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error handling clear: {str(e)}")
            self.show_error_dialog(f"Error: {str(e)}")

def main(page: ft.Page):
    app = HealthcareTranslator(page)

if __name__ == '__main__':
    ft.app(target=main) 