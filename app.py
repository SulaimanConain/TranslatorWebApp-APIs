import logging
import requests
import os
import re
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash
from datetime import datetime
from flask_cors import CORS
from langdetect import detect, LangDetectException
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import uuid
import base64
import random
from sqlalchemy.orm import joinedload

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:sherlock@localhost/healthcare_translator'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# LLM API Configuration
LLM_API_URL = "http://localhost:11434/api/generate"
LLM_MODEL = "mannix/llamax3-8b-alpaca"

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

# Models
class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    unique_user_id = db.Column(db.String(20), unique=True, nullable=False)
    translations_remaining = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    last_login = db.Column(db.TIMESTAMP, nullable=True)

    def __init__(self, first_name, last_name, email, unique_user_id, password_hash, translations_remaining=100):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.unique_user_id = unique_user_id
        self.password_hash = password_hash
        self.translations_remaining = translations_remaining

class TranslationSession(db.Model):
    __tablename__ = 'translation_sessions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    input_language = db.Column(db.String(10), nullable=False)
    target_language = db.Column(db.String(10), nullable=False)
    translations = db.relationship('Translation', backref='session', lazy=True, cascade='all, delete-orphan')

class Translation(db.Model):
    __tablename__ = 'translations'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('translation_sessions.id'), nullable=False)
    original_text = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)
    detected_language = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
@login_required
def index():
    user = db.session.get(User, session['user_id'])
    return render_template('index.html', user=user)

@app.route('/get_previous_conversations')
@login_required
def get_previous_conversations():
    try:
        user_id = session.get('user_id')
        if not user_id:
            logger.error("No user_id in session")
            return jsonify({
                'success': False,
                'error': 'Not logged in'
            }), 401

        logger.info(f"Fetching conversations for user_id: {user_id}")

        # Get all translations for this user across all sessions
        translations = db.session.query(Translation).join(
            TranslationSession
        ).filter(
            TranslationSession.user_id == user_id
        ).order_by(
            Translation.timestamp.desc()
        ).all()

        logger.info(f"Found {len(translations)} translations")

        conversations = []
        for t in translations:
            conversations.append({
                'timestamp': t.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'transcript': t.original_text,
                'language': t.detected_language,
                'translated_text': t.translated_text,
                'session_id': t.session_id
            })

        # Get the latest session for language settings
        latest_session = db.session.query(TranslationSession).filter_by(
            user_id=user_id
        ).order_by(TranslationSession.start_time.desc()).first()

        return jsonify({
            'success': True,
            'conversations': conversations,
            'session_id': latest_session.id if latest_session else None,
            'input_language': latest_session.input_language if latest_session else 'en',
            'target_language': latest_session.target_language if latest_session else 'en'
        })

    except Exception as e:
        logger.error(f"Error fetching previous conversations: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to fetch conversations: {str(e)}"
        }), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        unique_user_id = request.form.get('unique_user_id')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email, unique_user_id=unique_user_id).first()
        
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('index'))
        
        flash('Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return redirect(url_for('register'))
        
        # Generate unique user ID
        unique_id = generate_unique_id(first_name, last_name)
        
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            unique_user_id=unique_id,
            password_hash=generate_password_hash(password),
            translations_remaining=100  # Set initial translations
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'Registration successful! Your Unique User ID is: {unique_id}', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    # End the current session if exists
    if 'user_id' in session:
        current_session = TranslationSession.query.filter_by(
            user_id=session['user_id'],
            end_time=None
        ).first()
        
        if current_session:
            current_session.end_time = datetime.utcnow()
            db.session.commit()
    
    session.pop('user_id', None)
    return redirect(url_for('login'))

# Add error handling for LLM connection
def check_llm_connection():
    try:
        response = requests.get("http://localhost:11434/api/version")
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False

@app.route('/process_patient', methods=['POST'])
@login_required
def process_patient():
    try:
        # Check LLM connection first
        if not check_llm_connection():
            return jsonify({
                'error': 'Translation service is not available. Please ensure Ollama is running.',
                'details': 'To start Ollama, open a new terminal and run: ollama serve'
            }), 503
            
        data = request.get_json()
        user = db.session.get(User, session['user_id'])
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        transcript = data.get('transcript', "").strip()
        input_language = data.get('input_language', "en-US").split('-')[0]
        target_language = data.get('target_language', 'en')
        translations_enabled = data.get('translations_enabled', True)
        
        if not transcript:
            return jsonify({'error': 'No transcript provided'}), 400

        # If translations are disabled, force target language to be same as input
        if not translations_enabled:
            target_language = input_language

        # Check if user has translations remaining
        if translations_enabled and user.translations_remaining <= 0:
            return jsonify({
                'error': 'No translations remaining',
                'translations_remaining': 0
            }), 400

        # Get or create translation session
        current_session = TranslationSession.query.filter_by(
            user_id=session['user_id'],
            end_time=None
        ).first()
        
        if not current_session:
            current_session = TranslationSession(
                user_id=session['user_id'],
                input_language=input_language,
                target_language=target_language
            )
            db.session.add(current_session)
            db.session.commit()

        try:
            detected_code = detect(transcript)
            detected_language = LANGUAGE_CODES.get(detected_code, detected_code.capitalize())
        except LangDetectException as e:
            logger.error(f"Language detection failed: {str(e)}")
            detected_language = "Unknown"

        try:
            if translations_enabled:
                target_lang_name = LANGUAGE_CODES.get(target_language, 'English')
                prompt = get_translation_prompt(detected_language, target_lang_name, transcript)
                
                llm_response = requests.post(
                    LLM_API_URL,
                    json={
                        "model": LLM_MODEL,
                        "prompt": prompt,
                        "stream": False
                    },
                    timeout=30  # Add timeout
                )
                llm_response.raise_for_status()
                translated_text = llm_response.json().get("response", "").strip()
                
                # Decrease translations remaining count
                user.translations_remaining -= 1
                db.session.commit()
            else:
                translated_text = "Translations were disabled"

            # Save to database
            translation = Translation(
                session_id=current_session.id,
                original_text=transcript,
                translated_text=translated_text,
                detected_language=detected_language
            )
            db.session.add(translation)
            db.session.commit()
            
            return jsonify({
                'timestamp': translation.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'transcript': transcript,
                'language': detected_language,
                'translated_text': translated_text,
                'session_id': current_session.id,
                'translations_remaining': user.translations_remaining
            })
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Translation API error: {str(e)}")
            return jsonify({'error': 'Translation service temporarily unavailable'}), 503
            
    except Exception as e:
        logger.error(f"An unexpected error occurred: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/generate_summary', methods=['POST'])
@login_required
def generate_summary():
    try:
        session_id = request.json.get('session_id')
        translations = Translation.query.filter_by(session_id=session_id).order_by(Translation.timestamp).all()
        
        if not translations:
            return jsonify({'error': 'No translations found for this session'}), 404
            
        conversation = []
        for t in translations:
            conversation.append(f"Original: {t.original_text}")
            conversation.append(f"Translation: {t.translated_text}")
            
        conversation_text = "\n".join(conversation)
        
        prompt = get_summary_prompt(conversation_text)
        
        llm_response = requests.post(
            LLM_API_URL,
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False
            }
        )
        llm_response.raise_for_status()
        summary = llm_response.json().get("response", "").strip()
        
        return jsonify({'summary': summary})
        
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return jsonify({'error': 'Failed to generate summary'}), 500

@app.route('/chat_with_ai', methods=['POST']) # this is for website
@login_required
def chat_with_ai():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
            
        message = data.get('message')
        session_id = data.get('session_id')
        user_id = request.get('user_id')
        
        if not session_id:
            return jsonify({'error': 'No session ID provided'}), 400
        
        # Get conversation context
        translations = translations = db.session.query(Translation).join(TranslationSession).filter(TranslationSession.user_id == user_id).order_by(Translation.timestamp).all()
        context = "\n".join([f"Original: {t.original_text}\nTranslation: {t.translated_text}" for t in translations])
        
        prompt = get_chat_prompt(context, message)
        
        try:
            llm_response = requests.post(
                LLM_API_URL,
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30
            )
            llm_response.raise_for_status()
            response = llm_response.json().get("response", "").strip()
            
            if not response:
                raise ValueError("Empty response from LLM")
                
            return jsonify({'response': response})
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM API error: {str(e)}")
            return jsonify({'error': 'AI service temporarily unavailable'}), 503
            
    except Exception as e:
        logger.error(f"Error in AI chat: {str(e)}")
        return jsonify({'error': 'Failed to process chat message'}), 500



@app.route('/clear_conversation', methods=['POST'])
@login_required
def clear_conversation():
    try:
        user_id = session.get('user_id')

        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401

        # Get all active and past translation sessions for the user
        user_sessions = TranslationSession.query.filter_by(user_id=user_id).all()

        if user_sessions:
            session_ids = [s.id for s in user_sessions]

            # Delete all translations linked to these sessions
            Translation.query.filter(Translation.session_id.in_(session_ids)).delete(synchronize_session=False)

            # Commit translation deletions first
            db.session.commit()

            # Now delete all the translation sessions of the user
            TranslationSession.query.filter(TranslationSession.id.in_(session_ids)).delete(synchronize_session=False)

            # Commit final deletion of sessions
            db.session.commit()

            return jsonify({'success': True, 'message': 'All user translations and transcriptions cleared successfully'})

        return jsonify({'success': True, 'message': 'No active or past conversation found'})

    except Exception as e:
        logger.error(f"Error clearing user's conversation: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Failed to clear conversation', 'message': str(e)}), 500


@app.route('/api/clear_conversation', methods=['POST'])
def api_clear_conversation():
    try:
        # Support multiple ways of getting user_id from the request
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id')
        
        # Also try to get user_id from form data or query parameters if not in JSON
        if not user_id:
            user_id = request.form.get('user_id')
        if not user_id:
            user_id = request.args.get('user_id')
            
        logger.info(f"Clear conversation request received with data: {data}")
        logger.info(f"Request content type: {request.content_type}")
        
        if not user_id:
            logger.error("No user_id provided in request")
            return jsonify({
                'success': False, 
                'error': 'User ID required'
            }), 400

        logger.info(f"Clearing conversations for user_id: {user_id}")

        # Get all active and past translation sessions for the user
        user_sessions = TranslationSession.query.filter_by(user_id=user_id).all()
        
        if not user_sessions:
            logger.info(f"No sessions found for user {user_id}")
            return jsonify({
                'success': True, 
                'message': 'No active or past conversation found'
            })

        # Continue with session deletion
        session_ids = [s.id for s in user_sessions]
        logger.info(f"Found {len(session_ids)} sessions to clear for user {user_id}")
        
        try:
            # Delete all translations linked to these sessions
            deleted_translations = Translation.query.filter(
                Translation.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            
            logger.info(f"Deleted {deleted_translations} translations")

            # Commit translation deletions first
            db.session.commit()
            
            # Now delete all the translation sessions of the user
            deleted_sessions = TranslationSession.query.filter(
                TranslationSession.id.in_(session_ids)
            ).delete(synchronize_session=False)
            
            logger.info(f"Deleted {deleted_sessions} sessions")

            # Commit final deletion of sessions
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'message': f'Cleared {deleted_translations} translations across {deleted_sessions} sessions'
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error while clearing conversations: {str(e)}")
            return jsonify({
                'success': False, 
                'error': f'Database error: {str(e)}'
            }), 500

    except Exception as e:
        logger.error(f"Error clearing user's conversation: {str(e)}")
        # Ensure we rollback any partial changes
        try:
            db.session.rollback()
        except:
            pass
            
        return jsonify({
            'success': False, 
            'error': f'Failed to clear conversation: {str(e)}'
        }), 500

@app.route('/get_translations_remaining', methods=['GET'])
@login_required
def get_translations_remaining():
    user = db.session.get(User, session['user_id'])
    return jsonify({'translations_remaining': user.translations_remaining})

@app.route('/privacy-policy')
def privacy_policy():
    return render_template('privacy_policy.html')

# API Endpoints for Flet app

@app.route('/api/login', methods=['POST'])
def api_login():
    try:
        data = request.json
        logger.info(f"Login attempt for email: {data.get('email')}")
        
        email = data.get('email')
        unique_user_id = data.get('unique_user_id')
        password = data.get('password')
        
        if not all([email, unique_user_id, password]):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400
            
        user = User.query.filter_by(email=email, unique_user_id=unique_user_id).first()
        
        if user and check_password_hash(user.password_hash, password):
            # Create new session
            new_session = TranslationSession(
                user_id=user.id,
                input_language='en',
                target_language='en'
            )
            db.session.add(new_session)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'unique_user_id': user.unique_user_id,
                    'translations_remaining': user.translations_remaining
                },
                'session_id': new_session.id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid credentials'
            }), 401
            
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/register', methods=['POST'])
def api_register():
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        
        if not all([email, password, first_name, last_name]):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400
            
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return jsonify({
                'success': False,
                'error': 'Email already registered'
            }), 400
            
        try:
            # Generate unique user ID
            unique_user_id = generate_unique_id(first_name, last_name)
            
            # Create new user
            new_user = User(
                email=email,
                password_hash=generate_password_hash(password),
                unique_user_id=unique_user_id,
                first_name=first_name,
                last_name=last_name,
                translations_remaining=100
            )
            
            # Save to database
            db.session.add(new_user)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'unique_user_id': unique_user_id,
                'message': 'Registration successful'
            }), 200
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Database error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Registration failed'
            }), 500
            
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/translate', methods=['POST'])
def api_translate():
    try:
        data = request.json
        session_id = data.get('session_id')
        text = data.get('text')
        source_lang = data.get('source_lang', 'en')
        target_lang = data.get('target_lang', 'en')
        
        if not all([session_id, text]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
            
        # Get session and user
        session = TranslationSession.query.get(session_id)
        if not session:
            return jsonify({
                'success': False,
                'error': 'Invalid session'
            }), 404
            
        user = User.query.get(session.user_id)
        if user.translations_remaining <= 0:
            return jsonify({
                'success': False,
                'error': 'No translations remaining'
            }), 403
            
        # Updated prompt for mannix/llamax3-8b-alpaca
        prompt = get_api_translation_prompt(source_lang, target_lang, text)
            
        # Call LLM API with updated model
        llm_response = requests.post(
            LLM_API_URL,
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.3,  # Lower temperature for more accurate translations
                "max_tokens": 500
            }
        )
        
        if llm_response.status_code == 200:
            translated_text = llm_response.json().get('response', '')
            
            # Save translation
            translation = Translation(
                session_id=session_id,
                original_text=text,
                translated_text=translated_text,
                detected_language=source_lang
            )
            db.session.add(translation)
            
            # Update translations remaining
            user.translations_remaining -= 1
            db.session.commit()
            
            return jsonify({
                'success': True,
                'translation': {
                    'original_text': text,
                    'translated_text': translated_text,
                    'detected_language': source_lang,
                    'timestamp': translation.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                },
                'translations_remaining': user.translations_remaining
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Translation service error'
            }), 500
            
    except Exception as e:
        logger.error(f"Translation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/generate_summary', methods=['POST'])
def api_generate_summary():
    try:
        data = request.json
        if not data:
            logger.error("No data provided")
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        session_id = data.get('session_id')
        user_id = data.get('user_id')
        logger.info(f"LLM user id:  {session_id}, {user_id}")
        logger.info(f"Generating summary for session {session_id} and user {user_id}")
        
        if not all([session_id, user_id]):
            logger.error("Missing session_id or user_id")
            return jsonify({
                'success': False,
                'error': 'Session ID and User ID required'
            }), 400
            
        # Get all translations for this user's sessions
        translations = db.session.query(Translation).join(
            TranslationSession
        ).filter(
            TranslationSession.user_id == user_id
        ).order_by(
            Translation.timestamp
        ).all()

        if not translations:
            logger.error(f"No translations found for user {user_id}")
            return jsonify({
                'success': False,
                'error': 'No translations found'
            }), 404
            
        # Prepare conversation history
        conversation = []
        for t in translations:
            conversation.append(f"Original ({t.detected_language}): {t.original_text}")
            conversation.append(f"Translated: {t.translated_text}")
            
        conversation_text = '\n'.join(conversation)
        
        #logger.info(f"Prepared conversation with {len(translations)} translations")
            
        # Create prompt for summary
        prompt = get_summary_prompt(conversation_text)
        logger.info(f"converstaion_text:{prompt} ")
            
        # Call LLM API
        logger.info("Calling LLM API for summary generation")
        llm_response = requests.post(
            LLM_API_URL,
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.3,
                "max_tokens": 300
            }
        )
        
        logger.info(f"LLM response status: {llm_response.status_code}")
        logger.info(f"LLM response: {llm_response.text}")
        
        if llm_response.status_code == 200:
            response_data = llm_response.json()
            summary = response_data.get('response', '')
            if not summary:
                logger.error("Empty summary from LLM")
                return jsonify({
                    'success': False,
                    'error': 'Empty response from LLM'
                }), 500

            logger.info("Successfully generated summary")
            return jsonify({
                'success': True,
                'summary': summary
            })
        else:
            logger.error(f"LLM API error: {llm_response.status_code}")
            return jsonify({
                'success': False,
                'error': 'Summary generation failed',
                'details': f"LLM API returned status code {llm_response.status_code}"
            }), 500
            
    except Exception as e:
        logger.error(f"Summary generation error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f"Failed to generate summary: {str(e)}"
        }), 500


@app.route('/api/chat', methods=['POST'])
def api_chat():
    try:
        data = request.json  # Read JSON from request
        print("FULL REQUEST JSON IN /api/chat:", data) 
        if not data:
            logger.error("No data provided")
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400

        session_id = data.get('session_id')
        user_id = request.json.get('user_id') if request.json else request.form.get('user_id')# Try both :( This was really frustrating :( 


        message = data.get('message')
        logger.info(f"Generating AI Asisstant respones for  user id -----------------------------------------------------------------------------------------------------------------------------------------------------------------------> {user_id}")

        if not all([session_id, message]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        # Get conversation context
        translations = db.session.query(Translation).join(
            TranslationSession, Translation.session_id == TranslationSession.id
        ).filter(
            TranslationSession.user_id == user_id
        ).order_by(
            TranslationSession.user_id
        ).all()

        context = [
            f"Original ({t.detected_language}): {t.original_text}\nTranslated: {t.translated_text}"
            for t in translations
        ]

        # Updated prompt for mannix/llamax3-8b-alpaca
        prompt = get_chat_prompt("\n".join(context), message)
        logger.info(f"LLM prompt: {prompt}")

        llm_response = requests.post(
            LLM_API_URL,
            json={
                "model": LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.4,
                "max_tokens": 400
            }
        )

        if llm_response.status_code == 200:
            response = llm_response.json().get('response', '')
            return jsonify({'success': True, 'response': response})
        else:
            return jsonify({'success': False, 'error': 'Chat response generation failed'}), 500

    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/translations', methods=['GET'])
def api_get_translations():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'User ID required'
            }), 400
            
        # Get all translations for this user across all sessions
        translations = db.session.query(Translation).join(
            TranslationSession
        ).filter(
            TranslationSession.user_id == user_id
        ).order_by(
            Translation.timestamp.desc()
        ).all()
        
        logger.info(f"Found {len(translations)} translations for user {user_id}")
        
        return jsonify({
            'success': True,
            'translations': [{
                'original_text': t.original_text,
                'translated_text': t.translated_text,
                'detected_language': t.detected_language,
                'timestamp': t.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'session_id': t.session_id
            } for t in translations]
        })
        
    except Exception as e:
        logger.error(f"Error fetching translations: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Helper functions for prompts
def get_translation_prompt(detected_language, target_lang_name, transcript):
    prompt = f"Task: Translate the following text from {detected_language} to {target_lang_name}.\n"
    prompt += f"Text to translate: {transcript}\n"
    prompt += "Instructions:\n"
    prompt += "1. Maintain accuracy\n"
    prompt += "2. Preserve the original meaning\n"
    prompt += "3. Use appropriate context\n"
    prompt += "4. Return only the translated text"
    return prompt

def get_summary_prompt(conversation_text):
    prompt = "Task: Generate a concise summary of the following conversation.\n\n"
    prompt += f"Conversation:\n{conversation_text}\n\n"
    prompt += "Instructions:\n"
    prompt += "1. Focus on key information\n"
    prompt += "2. Include important points\n"
    prompt += "3. Maintain accuracy\n"
    prompt += "4. Structure the summary clearly\n"
    prompt += "5. Keep it concise but comprehensive"
    return prompt

def get_chat_prompt(context, message):
    prompt = "Task: Act as an AI assistant and provide a helpful response to the user's question using context only.\n\n"
    prompt += "Context:\n"
    prompt += f"Conversation history:\n{context}\n\n"
    prompt += f"User question: {message}\n\n"
   
    return prompt

def get_api_translation_prompt(source_lang, target_lang, text):
    prompt = f"Task: Translate the following medical text from {LANGUAGE_CODES.get(source_lang, source_lang)} "
    prompt += f"to {LANGUAGE_CODES.get(target_lang, target_lang)}.\n"
    prompt += f"Text to translate: {text}\n\n"
    prompt += "Instructions:\n"
    prompt += "1. Maintain accuracy\n"
    prompt += "2. Preserve the original meaning\n"
    prompt += "3. Use appropriate context\n"
    prompt += "4. Return only the translated text"
    return prompt

def generate_unique_id(first_name, last_name):
    """Generate a unique user ID using first name, last name and random numbers"""
    try:
        # Take first 2 chars of first name and last name
        first_part = first_name[:2].lower()
        last_part = last_name[:2].lower()
        
        # Generate random 4-digit number
        random_num = str(random.randint(1000, 9999))
        
        # Combine parts
        base_id = f"{first_part}{last_part}{random_num}"
        
        # Remove any non-alphanumeric characters
        base_id = ''.join(c for c in base_id if c.isalnum())
        
        # Check if ID exists and generate new one if it does
        while User.query.filter_by(unique_user_id=base_id).first():
            random_num = str(random.randint(1000, 9999))
            base_id = f"{first_part}{last_part}{random_num}"
            
        logger.info(f"Generated unique ID: {base_id}")
        return base_id
        
    except Exception as e:
        logger.error(f"Error generating unique ID: {str(e)}")
        raise

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8800, debug=True)