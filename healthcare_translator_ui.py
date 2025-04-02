import flet as ft
import logging
from healthcare_translator_backend import HealthcareTranslatorBackend
import os
from datetime import datetime

# Update these paths according to your actual installation paths
if os.name == 'nt':  # Windows
    os.environ["JAVA_HOME"] = "C:\\Program Files\\Microsoft\\jdk-17.0.14"  # Update to match your OpenJDK path
    os.environ["ANDROID_HOME"] = "C:\\Users\\moham\\AppData\\Local\\Android\\Sdk"
else:  # Linux/Mac
    os.environ["JAVA_HOME"] = "/path/to/your/java/home"
    os.environ["ANDROID_HOME"] = "/path/to/your/android/sdk"

logger = logging.getLogger(__name__)

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

class HealthcareTranslatorUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "Universal Translator"
        
        # Mobile configuration
        self.page.window_width = 400
        self.page.window_height = 800
        self.page.window_resizable = True
        self.page.window_maximizable = True
        self.page.theme_mode = ft.ThemeMode.DARK
        
        # Enhanced mobile responsiveness
        self.page.responsive = True
        self.page.scroll = ft.ScrollMode.AUTO
        self.page.padding = 0
        self.page.spacing = 0
        self.page.fonts = {
            "Roboto": "https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap"
        }
        
        # Mobile viewport settings
        self.page.viewport = {
            "width": None,  # Use device width
            "initial_scale": 1.0,
            "minimum_scale": 1.0,
            "maximum_scale": 1.0,
            "user_scalable": False
        }
        
        # Initialize backend
        self.backend = HealthcareTranslatorBackend()
        
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
        self.current_theme = "dark"
        
        # Initialize login fields
        self.email_field = ft.Ref[ft.TextField]()
        self.unique_user_id_field = ft.Ref[ft.TextField]()
        self.password_field = ft.Ref[ft.TextField]()
        
        # Initialize chat input reference
        self.chat_input = ft.Ref[ft.TextField]()
        
        # Initialize chat history
        self.chat_history = ft.ListView(
            expand=True,
            spacing=10,
            padding=10,
            auto_scroll=True,
            height=200  # Fixed height for chat history
        )
        
        # Initialize summary text
        self.summary_text = ft.Text(
            "No conversation summary available yet.",
            size=14,
            color=ft.Colors.WHITE if self.current_theme == "dark" else ft.Colors.BLACK,
            text_align=ft.TextAlign.LEFT,
            selectable=True
        )
        
        # Initialize recording state
        self.is_recording = False
        
        # Initialize translations state
        self.translations_enabled = True
        
        logger.info("UI components initialized successfully")
        
        # Initialize UI components
        self.init_ui_components()
        
        # Show login view initially
        self.show_login_view()

        # Register assets directory
        self.page.assets_dir = "assets"

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
            
            # Initialize language dropdowns
            self.input_language = ft.Dropdown(
                value="en",
                options=[
                    ft.dropdown.Option(key=k, text=v)
                    for k, v in LANGUAGE_CODES.items()
                ],
                width=200,
                expand=True
            )
            
            self.target_language = ft.Dropdown(
                value="ar",
                options=[
                    ft.dropdown.Option(key=k, text=v)
                    for k, v in LANGUAGE_CODES.items()
                ],
                width=200,
                expand=True
            )
            
            # Initialize chat components
            self.chat_input = ft.Ref[ft.TextField]()
            self.chat_history = ft.ListView(
                expand=True,
                spacing=10,
                padding=10,
                auto_scroll=True,
                height=200
            )
            
            # Initialize summary text
            self.summary_text = ft.Text(
                "No conversation summary available yet.",
                size=14,
                color=ft.Colors.WHITE if self.current_theme == "dark" else ft.Colors.BLACK,
                text_align=ft.TextAlign.LEFT,
                selectable=True
            )
            
            logger.info("UI components initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing UI components: {str(e)}")
            raise

    def build_ui(self):
        """Build the main UI components"""
        try:
            theme_colors = self.colors[self.current_theme]
            
            # Create main layout
            main_layout = ft.Column([
                # Top navigation bar
                self.build_top_nav(theme_colors),
                
                # Main content area
                self.build_main_content(theme_colors),
                
            ], expand=True, scroll=True)

            return main_layout
            
        except Exception as e:
            logger.error(f"Error building UI: {str(e)}")
            raise

    def build_top_nav(self, theme_colors):
        """Build top navigation bar"""
        # Get first name from current user
        first_name = self.backend.current_user.get('first_name', '')
        
        return ft.Container(
            content=ft.Column([
                # Top row with logo and title
                ft.Row([
                    # Left - Logo and title
                    ft.Row([
                        ft.Image(
                            src="assets/icon.png",
                            width=100,  # Increased from 60 to 100
                            height=100,  # Increased from 60 to 100
                            fit=ft.ImageFit.CONTAIN,
                            scale=1.0,  # Changed from 0.8 to 1.0 for full size
                        ),
                        ft.Text(
                            "Universal Translator",
                            size=20,  # Increased from 14 to 20
                            weight=ft.FontWeight.BOLD,
                            color=theme_colors["text_color"]
                        )
                    ], spacing=10),  # Increased spacing from 5 to 10
                ], alignment=ft.MainAxisAlignment.CENTER),
                
                # Bottom row with welcome text and actions
                ft.Row([
                    # Welcome text
                    ft.Text(
                        f"Welcome, {first_name}" if first_name else "Welcome",
                        color=theme_colors["text_color"],
                        size=16,  # Increased from 14 to 16
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER
                    ),
                    
                    # Actions
                    ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.DARK_MODE,
                            icon_color=theme_colors["text_color"],
                            icon_size=24,  # Increased from 20 to 24
                            tooltip="Toggle theme",
                            on_click=self.toggle_theme
                        ),
                        ft.IconButton(
                            icon=ft.Icons.LOGOUT,
                            icon_color=ft.Colors.RED_400,
                            icon_size=24,  # Increased from 20 to 24
                            tooltip="Sign Out",
                            on_click=self.handle_logout
                        )
                    ], spacing=10)  # Increased spacing from 5 to 10
                ], 
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
            ], spacing=15),  # Increased spacing from 10 to 15
            padding=ft.padding.symmetric(horizontal=20, vertical=15),  # Increased padding
            bgcolor=theme_colors["card_bg"],
            border_radius=ft.border_radius.only(bottom_left=10, bottom_right=10)
        )

    def build_main_content(self, theme_colors):
        """Build main content area"""
        return ft.Container(
            content=ft.Column([
                # Translator header with improved mobile layout
                ft.Container(
                    content=ft.Column([
                        # Title and clear button row
                        ft.Row([
                            ft.Row([
                                ft.Icon(ft.Icons.TRANSLATE, 
                                      color=ft.Colors.BLUE_400, 
                                      size=20),
                                ft.Text(
                                    "Translations", 
                                    size=16, 
                                    weight=ft.FontWeight.BOLD,
                                    color=theme_colors["text_color"]
                                )
                            ]),
                            # Clear button - Made more visible
                            ft.IconButton(
                                icon=ft.Icons.DELETE_FOREVER,
                                icon_color=ft.Colors.RED_400,
                                icon_size=24,
                                tooltip="Clear All",
                                on_click=self.handle_clear
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        
                        # Controls row with better spacing
                        ft.Row([
                            ft.Container(
                                content=ft.Text(
                                    f"Credits: {self.backend.current_user.get('translations_remaining', 0)}",
                                    color=ft.Colors.WHITE,
                                    size=12,
                                    weight=ft.FontWeight.BOLD
                                ),
                                bgcolor=ft.Colors.BLUE_400,
                                border_radius=15,
                                padding=ft.padding.symmetric(horizontal=10, vertical=5)
                            ),
                            ft.Container(
                                content=ft.Row([
                                    ft.Text(
                                        "Auto-translate",
                                        size=12,
                                        color=theme_colors["text_color"]
                                    ),
                                    ft.Switch(
                                        value=True,
                                        on_change=self.handle_translation_toggle,
                                        scale=0.8
                                    ),
                                ]),
                                padding=ft.padding.only(left=10, right=10)
                            ),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], spacing=10),
                    padding=10,
                    bgcolor=theme_colors["card_bg"],
                    border_radius=8,
                    margin=ft.margin.only(bottom=10)
                ),

                # Language Selection Row
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text("Source Language", size=14, weight=ft.FontWeight.BOLD),
                            self.input_language
                        ], expand=True),
                        ft.Column([
                            ft.Text("Target Language", size=14, weight=ft.FontWeight.BOLD),
                            self.target_language
                        ], expand=True),
                    ], spacing=20),
                    padding=10,
                    bgcolor=theme_colors["card_bg"],
                    border_radius=8,
                    margin=ft.margin.only(bottom=10)
                ),

                # Recording Button
                ft.Container(
                    content=ft.ElevatedButton(
                        "Start Recording",
                        icon=ft.Icons.MIC,
                        style=self.get_button_style(),
                        width=float("inf"),
                        on_click=self.toggle_recording
                    ),
                    margin=ft.margin.only(bottom=10)
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

                # Add Summary Section
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.Icon(
                                    ft.Icons.SUMMARIZE,
                                    color=ft.Colors.BLUE_400,
                                    size=20
                                ),
                                ft.Text(
                                    "Conversation Summary",
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme_colors["text_color"]
                                )
                            ]),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        
                        ft.Container(
                            content=self.summary_text,
                            bgcolor=theme_colors["card_bg"],
                            border_radius=8,
                            padding=10,
                            margin=ft.margin.only(top=10, bottom=10)
                        ),
                        
                        ft.ElevatedButton(
                            "Generate Summary",
                            style=self.get_button_style(),
                            width=float("inf"),
                            on_click=self.generate_summary
                        )
                    ]),
                    padding=10,
                    bgcolor=theme_colors["card_bg"],
                    border_radius=8,
                    margin=ft.margin.only(top=10, bottom=10)
                ),

                # AI Assistant Section with improved responsiveness
                ft.Container(
                    content=ft.Column([
                        ft.Row([
                            ft.Row([
                                ft.Icon(
                                    ft.Icons.SMART_TOY,
                                    color=ft.Colors.BLUE_400,
                                    size=20
                                ),
                                ft.Text(
                                    "AI Assistant",
                                    size=16,
                                    weight=ft.FontWeight.BOLD,
                                    color=theme_colors["text_color"]
                                ),
                            ]),
                            ft.Container(
                                content=ft.Text(
                                    "Using medical history",
                                    size=12,
                                    color=ft.Colors.GREEN_400,
                                    weight=ft.FontWeight.BOLD
                                ),
                                bgcolor=ft.colors.with_opacity(0.1, ft.Colors.GREEN_400),
                                border_radius=15,
                                padding=ft.padding.symmetric(horizontal=10, vertical=5)
                            )
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        
                        # Chat history with improved scrolling
                        ft.Container(
                            content=self.chat_history,
                            bgcolor=theme_colors["card_bg"],
                            border_radius=8,
                            padding=10,
                            margin=ft.margin.only(top=10, bottom=10),
                            height=300,  # Increased height
                            border=ft.border.all(1, theme_colors["border_color"])
                        ),
                        
                        # Input area with improved layout
                        ft.Container(
                            content=ft.Row([
                                ft.TextField(
                                    ref=self.chat_input,
                                    hint_text="Ask about the medical conversation...",
                                    border_color=ft.Colors.BLUE_400,
                                    multiline=True,
                                    min_lines=1,
                                    max_lines=3,
                                    expand=True,
                                    text_size=14
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.SEND,
                                    icon_color=ft.Colors.BLUE_400,
                                    icon_size=24,
                                    tooltip="Send message",
                                    on_click=self.handle_chat
                                )
                            ], spacing=10),
                            padding=10
                        )
                    ]),
                    padding=10,
                    bgcolor=theme_colors["card_bg"],
                    border_radius=8,
                    margin=ft.margin.only(top=10),
                    border=ft.border.all(1, theme_colors["border_color"])
                )
            ]),
            padding=10,
            bgcolor=theme_colors["bg_color"],
            expand=True
        )

    def set_button_loading(self, button, is_loading: bool, loading_text: str = None, original_text: str = None):
        """Set button loading state"""
        if is_loading:
            button.disabled = True
            button.content = ft.Row(
                [
                    ft.ProgressRing(width=16, height=16, stroke_width=2),
                    ft.Text(loading_text or "Loading...")
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10
            )
        else:
            button.disabled = False
            button.content = None
            button.text = original_text
        self.page.update()

    def handle_login(self, e):
        """Handle login button click"""
        try:
            email = self.email_field.current.value
            unique_user_id = self.unique_user_id_field.current.value
            password = self.password_field.current.value
            
            if not all([email, unique_user_id, password]):
                self.show_error_dialog("Please fill in all fields")
                return
            
            # Show loading state
            self.set_button_loading(e.control, True, "Logging in...")
            
            # Call backend login
            success, data = self.backend.login(email, unique_user_id, password)
            
            if success:
                self.show_main_view()
                self.load_previous_translations()
            else:
                self.show_error_dialog(data.get('error', 'Login failed'))
                
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            self.show_error_dialog(f"Login error: {str(e)}")
        finally:
            # Reset button state
            self.set_button_loading(e.control, False, original_text="Login")

    def show_login_view(self):
        """Show the login view"""
        try:
            # Clear the page
            self.page.clean()
            
            # Create login form
            login_form = ft.ResponsiveRow([
                ft.Container(
                    col={"sm": 12, "md": 8, "lg": 6, "xl": 4},
                    content=ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                # Logo
                                ft.Image(
                                    src="assets/icon.png",
                                    width=150,  # Increased from 120 to 150
                                    height=150,  # Increased from 120 to 150
                                    fit=ft.ImageFit.CONTAIN,
                                    scale=1.0,  # Changed from 0.8 to 1.0
                                ),
                                ft.Text(
                                    "Healthcare Translator", 
                                    size=24, 
                                    weight=ft.FontWeight.BOLD,
                                    color=self.colors[self.current_theme]["text_color"]
                                ),
                                ft.TextField(
                                    ref=self.email_field,
                                    label="Email",
                                    border_color=ft.Colors.BLUE_400,
                                    expand=True,
                                    autofocus=True
                                ),
                                ft.TextField(
                                    ref=self.unique_user_id_field,
                                    label="Unique User ID",
                                    border_color=ft.Colors.BLUE_400,
                                    expand=True
                                ),
                                ft.TextField(
                                    ref=self.password_field,
                                    label="Password",
                                    password=True,
                                    can_reveal_password=True,
                                    border_color=ft.Colors.BLUE_400,
                                    expand=True
                                ),
                                ft.ElevatedButton(
                                    text="Login",
                                    style=self.get_button_style(),
                                    width=None,
                                    expand=True,
                                    height=45,
                                    on_click=self.handle_login
                                ),
                                ft.TextButton(
                                    "Don't have an account? Register",
                                    on_click=lambda _: self.show_register_view()
                                )
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=20),
                            padding=30,
                        ),
                        elevation=4,
                    ),
                    margin=ft.margin.all(10),
                    expand=True
                )
            ])
            
            # Add the login form to the page
            self.page.add(login_form)
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error showing login view: {str(e)}")
            self.show_error_dialog(f"Error showing login view: {str(e)}")

    def show_error_dialog(self, message):
        """Show error dialog"""
        self.page.dialog = ft.AlertDialog(
            title=ft.Text("Error"),
            content=ft.Text(message),
            actions=[
                ft.TextButton("OK", on_click=lambda _: setattr(self.page.dialog, 'is_open', False))
            ]
        )
        self.page.dialog.is_open = True
        self.page.update()

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

    def show_main_view(self):
        """Show main application view"""
        try:
            logger.info("Showing main view...")
            
            # Clear the page first
            self.page.clean()
            
            # Build and add main UI
            main_content = self.build_ui()
            if main_content:
                self.page.add(main_content)
                self.page.update()
                logger.info("Main view loaded successfully")
            else:
                raise Exception("Failed to build main UI")
            
        except Exception as e:
            logger.error(f"Error showing main view: {str(e)}")
            self.show_error_dialog(f"Error loading main view: {str(e)}")

    def load_previous_translations(self):
        """Load previous translations from backend"""
        try:
            success, data = self.backend.get_translations()
            if success and data.get('translations'):
                for translation in data['translations']:
                    self.add_translation_to_list(
                        translation['original_text'],
                        translation['translated_text'],
                        translation['detected_language'],
                        translation['timestamp']
                    )
        except Exception as e:
            logger.error(f"Error loading translations: {str(e)}")
            self.show_error_dialog("Failed to load previous translations")

    def toggle_theme(self, e):
        """Toggle between light and dark theme"""
        self.current_theme = "dark" if self.current_theme == "light" else "light"
        theme_colors = self.colors[self.current_theme]
        
        # Set page theme
        self.page.bgcolor = theme_colors["bg_color"]
        self.page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=ft.Colors.BLUE_400,
                secondary=ft.Colors.BLUE_200,
                background=theme_colors["bg_color"],
            )
        )
        
        # Rebuild UI with new theme
        self.show_main_view()
        self.page.update()

    def handle_logout(self, e):
        """Handle logout button click"""
        try:
            # Clear user data
            self.backend.current_user = None
            self.backend.current_session = None
            
            # Clear UI
            self.translations_list.controls.clear()
            self.chat_history.controls.clear()
            
            # Show login view
            self.show_login_view()
            
        except Exception as e:
            logger.error(f"Error handling logout: {str(e)}")
            self.show_error_dialog(f"Error logging out: {str(e)}")

    def add_translation_to_list(self, original_text, translated_text, detected_language, timestamp):
        """Add a translation to the translations list"""
        try:
            theme_colors = self.colors[self.current_theme]
            
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
                            f"{detected_language}",
                            size=12,
                            color=ft.Colors.BLUE_400
                        )
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(
                        original_text, 
                        selectable=True,
                        color=theme_colors["text_color"]
                    ),
                    ft.Text(
                        translated_text, 
                        selectable=True,
                        color=ft.Colors.BLUE_400
                    )
                ]),
                padding=10,
                bgcolor=theme_colors["card_bg"],
                border_radius=8,
                margin=ft.margin.only(bottom=10)
            )
            
            # Add to list
            self.translations_list.controls.insert(0, translation_card)
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error adding translation to list: {str(e)}")

    def handle_translation_toggle(self, e):
        """Handle translation toggle switch"""
        try:
            success, _ = self.backend.toggle_translations(e.control.value)
            if success:
                if e.control.value:
                    self.show_snackbar("Translations enabled")
                else:
                    self.show_snackbar("Translations disabled")
            else:
                self.show_error_dialog("Failed to toggle translations")
        except Exception as e:
            logger.error(f"Error handling translation toggle: {str(e)}")
            self.show_error_dialog(f"Error: {str(e)}")

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

    def toggle_recording(self, e):
        """Handle recording button click"""
        try:
            self.is_recording = not self.is_recording
            
            if self.is_recording:
                e.control.text = "Stop Recording"
                e.control.icon = ft.Icons.STOP
                e.control.style.bgcolor = ft.Colors.RED_400
                self.show_snackbar("Started recording...")
                self.page.launch_url("javascript:window.startRecording()")
            else:
                e.control.text = "Start Recording"
                e.control.icon = ft.Icons.MIC
                e.control.style.bgcolor = ft.Colors.BLUE_400
                self.page.launch_url("javascript:window.stopRecording()")
            
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error toggling recording: {str(e)}")
            self.show_error_dialog(f"Error: {str(e)}")

    def generate_summary(self, e):
        """Handle generate summary button click"""
        try:
            # Show loading state
            self.set_button_loading(e.control, True, "Generating...")
            
            # Call backend
            success, data = self.backend.generate_summary()
            
            if success and data.get('summary'):
                # Update summary text
                self.summary_text.value = data['summary']
                self.page.update()
            else:
                error_msg = data.get('error', 'Failed to generate summary')
                logger.error(f"Summary generation failed: {error_msg}")
                self.show_error_dialog(error_msg)
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            self.show_error_dialog(f"Error: {str(e)}")
        finally:
            # Reset button state
            self.set_button_loading(e.control, False, original_text="Generate Summary")

    def get_chat_context(self):
        """Get context from both current session and database history"""
        context = []
        
        try:
            # Get current session translations from UI
            for control in self.translations_list.controls:
                if isinstance(control, ft.Card):
                    original = control.content.controls[0].value
                    translation = control.content.controls[1].value
                    timestamp = control.data
                    context.append({
                        "original": original,
                        "translation": translation,
                        "timestamp": timestamp,
                        "source": "current_session"
                    })
            
            # Get historical translations from database
            if self.backend.current_user and self.backend.current_user.get('id'):
                user_id = self.backend.current_user['id']
                success, data = self.backend.get_user_translations(user_id)
                
                if success and data.get('translations'):
                    for trans in data['translations']:
                        context.append({
                            "original": trans['original_text'],
                            "translation": trans['translated_text'],
                            "timestamp": trans['timestamp'],
                            "source": "database"
                        })
            
            # Sort all translations by timestamp
            context.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # Limit to last 10 translations to keep context relevant
            context = context[:10]
            
            return context
            
        except Exception as e:
            logger.error(f"Error getting chat context: {str(e)}")
            return []

    def format_context_for_ai(self, context):
        """Format translation history for AI context with improved structure"""
        try:
            if not context:
                return "No previous conversation history available."
            
            formatted_context = "Previous medical conversation history:\n\n"
            
            for item in context:
                timestamp = item['timestamp']
                if isinstance(timestamp, str):
                    # Parse string timestamp if needed
                    try:
                        timestamp = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    except:
                        pass
                        
                # Format timestamp
                if isinstance(timestamp, datetime):
                    time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    time_str = str(timestamp)
                    
                formatted_context += f"Time: {time_str}\n"
                formatted_context += f"Patient: {item['original']}\n"
                formatted_context += f"Translation: {item['translation']}\n\n"
            
            return formatted_context
            
        except Exception as e:
            logger.error(f"Error formatting context: {str(e)}")
            return "Error formatting conversation history."

    def handle_chat(self, e):
        """Handle chat send button click with improved context awareness"""
        try:
            message = self.chat_input.current.value
            if not message:
                return

            self.set_button_loading(e.control, True, "Sending...")

            # Get translations from the list (same as generate summary)
            translations = []
            for control in self.translations_list.controls:
                if isinstance(control, ft.Card):
                    original = control.content.controls[0].value
                    translation = control.content.controls[1].value
                    timestamp = control.data
                    translations.append({
                        "original": original,
                        "translation": translation,
                        "timestamp": timestamp
                    })

            # Format context similar to generate summary
            context = "Medical Conversation History:\n\n"
            for trans in translations:
                context += f"Time: {trans['timestamp']}\n"
                context += f"Patient: {trans['original']}\n"
                context += f"Translation: {trans['translation']}\n\n"

            # Add user message to chat
            self.add_chat_message(message, is_user=True)
            
            # Clear input and show loading
            self.chat_input.current.value = ""
            self.page.update()

            # Add loading message
            self.add_chat_message("", is_user=False, is_loading=True)

            # Prepare prompt similar to generate summary
            prompt = f"""
            {context}
            
            Based on the above medical conversation between the patient and healthcare provider,
            please help answer this question: {message}
            
            """

            # Get AI response
            success, data = self.backend.get_chat_response(prompt)
            
            # Remove loading message
            if hasattr(self, 'loading_container'):
                self.chat_history.controls.remove(self.loading_container)
            
            if success and data.get('response'):
                self.add_chat_message(data['response'], is_user=False)
            else:
                self.show_error_dialog(data.get('error', 'Failed to get AI response'))
            
        except Exception as e:
            logger.error(f"Error handling chat: {str(e)}")
            self.show_error_dialog(f"Error: {str(e)}")
            # Remove loading message in case of error
            if hasattr(self, 'loading_container'):
                self.chat_history.controls.remove(self.loading_container)
        finally:
            self.set_button_loading(e.control, False, original_text="Send")
            self.chat_history.update()

    def show_snackbar(self, message):
        """Show snackbar message"""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(message),
            duration=2000
        )
        self.page.snack_bar.open = True
        self.page.update()

    def get_button_style(self, is_primary=True):
        """Get button style with glow effect"""
        return ft.ButtonStyle(
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.BLUE_400,
            shadow_color=ft.Colors.BLUE_400,
            elevation=5 if is_primary else 2,
            animation_duration=300,
            side=ft.border.BorderSide(
                width=1,
                color=ft.Colors.BLUE_400,
            )
        )

    def add_chat_message(self, message, is_user=True, is_loading=False):
        """Add a message to the chat history"""
        try:
            theme_colors = self.colors[self.current_theme]
            
            if is_loading:
                # Create loading message with animation
                message_container = ft.Container(
                    content=ft.Row([
                        ft.ProgressRing(
                            width=16,
                            height=16,
                            stroke_width=2,
                            color=ft.Colors.BLUE_400,
                        ),
                        ft.Text(
                            "AI is thinking...",
                            color=theme_colors["text_color"],
                            size=14,
                            italic=True
                        )
                    ], spacing=10),
                    bgcolor=theme_colors["card_bg"],
                    border_radius=10,
                    padding=10,
                    margin=ft.margin.only(
                        left=10,
                        right=40,
                        bottom=5
                    ),
                    width=float("inf")
                )
            else:
                # Create regular message container
                message_container = ft.Container(
                    content=ft.Text(
                        message,
                        color=ft.Colors.WHITE if is_user else theme_colors["text_color"],
                        selectable=True,
                        size=14
                    ),
                    bgcolor=ft.Colors.BLUE_400 if is_user else theme_colors["card_bg"],
                    border_radius=10,
                    padding=10,
                    margin=ft.margin.only(
                        left=40 if is_user else 10,
                        right=10 if is_user else 40,
                        bottom=5
                    ),
                    width=float("inf")
                )
            
            if is_loading:
                # Store the loading container reference
                self.loading_container = message_container
            
            # Add to chat history
            self.chat_history.controls.append(message_container)
            self.chat_history.update()
            
        except Exception as e:
            logger.error(f"Error adding chat message: {str(e)}")

    def show_register_view(self):
        """Show the registration view"""
        try:
            # Clear the page
            self.page.clean()
            
            # Initialize registration fields
            self.reg_first_name_field = ft.Ref[ft.TextField]()
            self.reg_last_name_field = ft.Ref[ft.TextField]()
            self.reg_email_field = ft.Ref[ft.TextField]()
            self.reg_password_field = ft.Ref[ft.TextField]()
            
            # Create registration form
            register_form = ft.ResponsiveRow([
                ft.Container(
                    col={"sm": 12, "md": 8, "lg": 6, "xl": 4},
                    content=ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                # Logo
                                ft.Image(
                                    src="assets/icon.png",
                                    width=150,  # Increased from 120 to 150
                                    height=150,  # Increased from 120 to 150
                                    fit=ft.ImageFit.CONTAIN,
                                    scale=1.0,  # Changed from 0.8 to 1.0
                                ),
                                ft.Text(
                                    "Register", 
                                    size=20, 
                                    weight=ft.FontWeight.BOLD,
                                    color=self.colors[self.current_theme]["text_color"]
                                ),
                                # Form fields
                                ft.Container(
                                    content=ft.Column([
                                        # First Name
                                        ft.TextField(
                                            ref=self.reg_first_name_field,
                                            label="First Name",
                                            border_color=ft.Colors.BLUE_400,
                                            expand=True,
                                            autofocus=True,
                                            text_size=14
                                        ),
                                        # Last Name
                                        ft.TextField(
                                            ref=self.reg_last_name_field,
                                            label="Last Name",
                                            border_color=ft.Colors.BLUE_400,
                                            expand=True,
                                            text_size=14
                                        ),
                                        # Email
                                        ft.TextField(
                                            ref=self.reg_email_field,
                                            label="Email Address",
                                            border_color=ft.Colors.BLUE_400,
                                            expand=True,
                                            helper_text="Enter a valid email address",
                                            keyboard_type=ft.KeyboardType.EMAIL,
                                            text_size=14
                                        ),
                                        # Password
                                        ft.TextField(
                                            ref=self.reg_password_field,
                                            label="Password",
                                            password=True,
                                            can_reveal_password=True,
                                            border_color=ft.Colors.BLUE_400,
                                            expand=True,
                                            keyboard_type=ft.KeyboardType.VISIBLE_PASSWORD,
                                            text_size=14
                                        ),
                                    ],
                                    spacing=15,
                                    expand=True
                                    )
                                ),
                                # Buttons container
                                ft.Container(
                                    content=ft.Column([
                                        ft.ElevatedButton(
                                            text="Register",
                                            style=self.get_button_style(),
                                            expand=True,
                                            height=45,
                                            on_click=self.handle_register
                                        ),
                                        ft.TextButton(
                                            "Already have an account? Login",
                                            on_click=lambda _: self.show_login_view()
                                        )
                                    ],
                                    spacing=10,
                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER
                                    ),
                                    margin=ft.margin.only(top=20)
                                )
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=20),
                            padding=ft.padding.all(20)
                        ),
                        elevation=4
                    ),
                    margin=ft.margin.all(10),
                    expand=True
                )
            ])
            
            # Add the registration form to the page
            self.page.add(register_form)
            self.page.update()
            
        except Exception as e:
            logger.error(f"Error showing registration view: {str(e)}")
            self.show_error_dialog(f"Error showing registration view: {str(e)}")

    def handle_register(self, e):
        """Handle registration button click"""
        try:
            # Get values from text fields
            first_name = self.reg_first_name_field.current.value
            last_name = self.reg_last_name_field.current.value
            email = self.reg_email_field.current.value
            password = self.reg_password_field.current.value
            
            # Store button reference
            button = e.control
            
            # Validate input
            if not all([first_name, last_name, email, password]):
                self.show_error_dialog("Please fill in all fields")
                return
            
            # Show loading state
            self.set_button_loading(button, True, "Registering...")
            
            # Call backend register
            success, data = self.backend.register(email, password, first_name, last_name)
            
            if success and data.get('unique_user_id'):
                unique_id = data['unique_user_id']
                logger.info(f"Registration successful. Generated ID: {unique_id}")
                
                # Reset button state
                self.set_button_loading(button, False, original_text="Register")
                
                # Clear the page
                self.page.clean()
                
                # Create success message
                success_container = ft.Container(
                    content=ft.Card(
                        content=ft.Container(
                            content=ft.Column([
                                ft.Text(
                                    "Registration Successful! 🎉",
                                    size=24,
                                    weight=ft.FontWeight.BOLD,
                                    color=ft.Colors.GREEN_400,
                                    text_align=ft.TextAlign.CENTER
                                ),
                                ft.Container(
                                    content=ft.Column([
                                        ft.Text(
                                            "Your Unique User ID:",
                                            size=16,
                                            weight=ft.FontWeight.BOLD,
                                            text_align=ft.TextAlign.CENTER
                                        ),
                                        ft.Container(
                                            content=ft.Row([
                                                ft.Text(
                                                    unique_id,
                                                    size=28,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=ft.Colors.BLUE_400,
                                                    selectable=True
                                                ),
                                                ft.IconButton(
                                                    icon=ft.Icons.COPY,
                                                    icon_color=ft.Colors.BLUE_400,
                                                    tooltip="Copy to clipboard",
                                                    on_click=lambda _: (
                                                        self.page.set_clipboard(unique_id),
                                                        self.show_snackbar("ID copied to clipboard!")
                                                    )
                                                )
                                            ],
                                            alignment=ft.MainAxisAlignment.CENTER),
                                            padding=20,
                                            bgcolor=ft.Colors.BLUE_50,
                                            border_radius=10,
                                            margin=ft.margin.symmetric(vertical=10)
                                        ),
                                        ft.Text(
                                            "⚠️ IMPORTANT: Save this ID - you'll need it to login!",
                                            size=14,
                                            color=ft.Colors.RED_400,
                                            weight=ft.FontWeight.BOLD,
                                            text_align=ft.TextAlign.CENTER
                                        )
                                    ],
                                    spacing=10),
                                    margin=ft.margin.only(top=20, bottom=20)
                                ),
                                ft.ElevatedButton(
                                    "Continue to Login",
                                    style=self.get_button_style(),
                                    width=300,
                                    height=50,
                                    on_click=lambda _: self.show_login_view()
                                )
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10),
                            padding=30
                        ),
                        elevation=4
                    ),
                    alignment=ft.alignment.center,
                    margin=ft.margin.all(20)
                )
                
                # Add success message to page
                self.page.add(success_container)
                self.page.update()
                
            else:
                error_msg = data.get('error', 'Registration failed')
                logger.error(f"Registration failed: {error_msg}")
                self.show_error_dialog(error_msg)
                # Reset button state
                self.set_button_loading(button, False, original_text="Register")
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            self.show_error_dialog(f"Registration error: {str(e)}")
            # Reset button state using the stored button reference
            if 'button' in locals():
                self.set_button_loading(button, False, original_text="Register")

def main(page: ft.Page):
    HealthcareTranslatorUI(page)

if __name__ == '__main__':
    ft.app(target=main) 