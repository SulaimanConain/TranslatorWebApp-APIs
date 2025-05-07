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
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from dotenv import load_dotenv
import hashlib
import concurrent.futures
import asyncio
import aiohttp
import time

# Load environment variables
load_dotenv()

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

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('DEL_EMAIL').strip("',")
app.config['MAIL_PASSWORD'] = os.getenv('PASSWORD').strip("',")
app.config['MAIL_DEFAULT_SENDER'] = ('Healthcare Translator', os.getenv('DEL_EMAIL').strip("',"))
app.config['MAIL_MAX_EMAILS'] = 5  # Limit number of emails per connection
app.config['MAIL_ASCII_ATTACHMENTS'] = False

# Initialize extensions
db = SQLAlchemy(app)
mail = Mail(app)

# Create serializer for token generation
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])

# DeepSeek API Configuration
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', 'sk-e04d98d1b66440f194203818f43443a6')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_API_TIMEOUT = 15  # Reduced timeout for faster response
MAX_RETRIES = 2  # Add retries for failed requests

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

# Translation cache
TRANSLATION_CACHE = {}
MAX_CACHE_SIZE = 1000

def get_cache_key(source_lang, target_lang, text):
    """Generate a unique cache key for a translation."""
    key_string = f"{source_lang}:{target_lang}:{text}"
    return hashlib.md5(key_string.encode()).hexdigest()

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
    is_verified = db.Column(db.Boolean, default=False)

    def __init__(self, first_name, last_name, email, unique_user_id, password_hash, translations_remaining=100, is_verified=False):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.unique_user_id = unique_user_id
        self.password_hash = password_hash
        self.translations_remaining = translations_remaining
        self.is_verified = is_verified

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
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('Invalid email or password', 'error')
            return render_template('login.html')
            
        if not user.is_verified:
            flash('Please verify your email before logging in. Check your inbox for the verification link.', 'warning')
            return render_template('login.html')
            
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('index'))
        
        flash('Invalid email or password', 'error')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Check if passwords match
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        
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
            translations_remaining=100,
            is_verified=False
        )
        
        db.session.add(user)
        db.session.commit()
        
        # Generate token and send verification email
        token = generate_confirmation_token(email)
        try:
            send_verification_email(email, token)
            flash('Registration successful! Please check your email to verify your account.', 'success')
        except Exception as e:
            logger.error(f"Failed to send verification email: {str(e)}")
            flash('Registration successful, but failed to send verification email. Please contact support.', 'warning')
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/verify-email/<token>')
def verify_email(token):
    try:
        email = confirm_token(token)
        if not email:
            flash('The verification link is invalid or has expired.', 'error')
            return redirect(url_for('login'))
            
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('User not found.', 'error')
            return redirect(url_for('login'))
            
        if user.is_verified:
            flash('Account already verified. Please login.', 'info')
            return redirect(url_for('login'))
        else:
            user.is_verified = True
            db.session.commit()
            return render_template('verification_success.html')
            
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        flash('An error occurred during verification.', 'error')
        return redirect(url_for('login'))

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
        # Simple test request to check API connectivity
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "user", "content": "Hello"}
            ]
        }
        
        logger.info("Testing DeepSeek API connection...")
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=5
        )
        
        # Attempt to parse response
        try:
            response.json()
            logger.info(f"API connection test result: {response.status_code}")
            return response.status_code < 400
        except Exception as e:
            logger.error(f"API response parse error: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"API connection check failed: {str(e)}")
        return False

@app.route('/process_patient', methods=['POST'])
@login_required
def process_patient():
    try:
        # Check LLM connection first
        if not check_llm_connection():
            return jsonify({
                'error': 'Translation service is not available. Please try again later.',
                'details': 'There may be an issue with the DeepSeek API service.'
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
                # Check cache first
                cache_key = get_cache_key(detected_language, target_language, transcript)
                start_time = time.time()
                
                if cache_key in TRANSLATION_CACHE:
                    logger.info(f"Using cached translation")
                    translated_text = TRANSLATION_CACHE[cache_key]
                else:
                    try:
                        # Try optimized translation first
                        logger.info(f"Using optimized translation method")
                        target_lang_name = LANGUAGE_CODES.get(target_language, 'English')
                        
                        # Make sure to pass strings, not language names
                        logger.info(f"Beginning translation from {detected_language} to {target_lang_name}")
                        result = run_async(process_translations_batch(
                            [transcript], 
                            detected_code,  # Using detected language code, not name
                            target_language  # Using target language code, not name
                        ))
                        
                        # Check if result dictionary contains our text key
                        if transcript in result:
                            translated_text = result[transcript]
                            
                            # Check if translation failed
                            if translated_text and not translated_text.startswith("Translation failed"):
                                logger.info(f"Optimized translation succeeded")
                            else:
                                # Fall back to standard translation
                                logger.info(f"Optimized translation returned error, falling back to standard")
                                prompt = get_translation_prompt(detected_language, target_lang_name, transcript)
                                translated_text = call_deepseek_api(prompt)
                        else:
                            # If key not found, fall back
                            logger.error(f"Translation result did not contain original text key")
                            prompt = get_translation_prompt(detected_language, target_lang_name, transcript)
                            translated_text = call_deepseek_api(prompt)
                    except Exception as e:
                        logger.error(f"Optimized translation failed: {str(e)}")
                        # Fallback to standard translation
                        target_lang_name = LANGUAGE_CODES.get(target_language, 'English')
                        prompt = get_translation_prompt(detected_language, target_lang_name, transcript)
                        translated_text = call_deepseek_api(prompt)
                
                logger.info(f"Translation completed in {time.time() - start_time:.2f} seconds")
                        
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
            
            result = {
                'timestamp': translation.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'transcript': transcript,
                'language': detected_language,
                'translated_text': translated_text,
                'session_id': current_session.id,
                'translations_remaining': user.translations_remaining
            }
            
            if translations_enabled and 'start_time' in locals():
                result['translation_time'] = f"{time.time() - start_time:.2f} seconds"
                
            return jsonify(result)
            
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
        
        try:
            summary = call_deepseek_api(prompt)
            return jsonify({'summary': summary})
        except Exception as e:
            logger.error(f"DeepSeek API error in summary generation: {str(e)}")
            return jsonify({'error': 'Unable to generate summary. The translation service is temporarily unavailable.'}), 503
        
    except Exception as e:
        logger.error(f"Error generating summary: {str(e)}")
        return jsonify({'error': 'Failed to generate summary. Please try again later.'}), 500

@app.route('/chat_with_ai', methods=['POST']) # this is for website
@login_required
def chat_with_ai():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
            
        message = data.get('message')
        session_id = data.get('session_id')
        user_id = session.get('user_id')  # Get user_id from the session
        
        if not session_id:
            return jsonify({'error': 'No session ID provided'}), 400
            
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Get conversation context
        translations = db.session.query(Translation).join(
            TranslationSession
        ).filter(
            TranslationSession.user_id == user_id
        ).order_by(
            Translation.timestamp
        ).all()
        
        context = "\n".join([f"Original: {t.original_text}\nTranslation: {t.translated_text}" for t in translations])
        
        prompt = get_chat_prompt(context, message)
        
        logger.info(f"Calling DeepSeek API for chat response with user_id: {user_id}")
        
        try:
            response = call_deepseek_api(prompt)
                
            if not response:
                return jsonify({'error': 'The AI assistant could not generate a response. Please try again.'}), 500
                
            return jsonify({'response': response})
            
        except Exception as e:
            logger.error(f"Chat API error: {str(e)}")
            return jsonify({'error': 'The AI assistant is temporarily unavailable. Please try again later.'}), 503
            
    except Exception as e:
        logger.error(f"Error in AI chat: {str(e)}")
        return jsonify({'error': 'Failed to process your message. Please try again.'}), 500

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
        password = data.get('password')
        
        if not all([email, password]):
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
            
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid email or password'
            }), 401
            
        if not user.is_verified:
            return jsonify({
                'success': False,
                'error': 'Please verify your email before logging in',
                'needs_verification': True
            }), 401
            
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
                'error': 'Invalid email or password'
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
        confirm_password = data.get('confirm_password')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        
        if not all([email, password, first_name, last_name]):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400
            
        # Check if passwords match
        if password != confirm_password and confirm_password is not None:
            return jsonify({
                'success': False,
                'error': 'Passwords do not match'
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
                translations_remaining=100,
                is_verified=False
            )
            
            # Save to database
            db.session.add(new_user)
            db.session.commit()
            
            # Generate token and send verification email
            token = generate_confirmation_token(email)
            try:
                send_verification_email(email, token)
                message = 'Registration successful! Please check your email to verify your account.'
            except Exception as e:
                logger.error(f"Failed to send verification email: {str(e)}")
                message = 'Registration successful, but failed to send verification email. Please contact support.'
            
            return jsonify({
                'success': True,
                'unique_user_id': unique_user_id,
                'message': message,
                'needs_verification': True
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

@app.route('/api/resend-verification', methods=['POST'])
def api_resend_verification():
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'Email is required'
            }), 400
            
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({
                'success': False,
                'error': 'Email not found'
            }), 404
            
        if user.is_verified:
            return jsonify({
                'success': False,
                'error': 'Email already verified'
            }), 400
            
        # Generate new token and send verification email
        token = generate_confirmation_token(email)
        send_verification_email(email, token)
        
        return jsonify({
            'success': True,
            'message': 'Verification email sent successfully'
        })
        
    except Exception as e:
        logger.error(f"Resend verification error: {str(e)}")
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
        
        # Check cache first
        cache_key = get_cache_key(source_lang, target_lang, text)
        if cache_key in TRANSLATION_CACHE:
            logger.info(f"Cache hit for translation")
            translated_text = TRANSLATION_CACHE[cache_key]
            
            # Save translation to database
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
                    'timestamp': translation.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'cached': True
                },
                'translations_remaining': user.translations_remaining
            })
        
        # No cache hit, use the optimized translation
        start_time = time.time()
        try:
            # Use the batch processor even for a single translation for consistency
            result = run_async(process_translations_batch([text], source_lang, target_lang))
            translated_text = result.get(text, "Translation failed")
            
            if translated_text.startswith("Translation failed"):
                raise Exception(translated_text)
                
            logger.info(f"Translation completed in {time.time() - start_time:.2f} seconds")
            
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
                    'timestamp': translation.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'cached': False,
                    'translation_time': f"{time.time() - start_time:.2f} seconds"
                },
                'translations_remaining': user.translations_remaining
            })
        except Exception as e:
            logger.error(f"Optimized translation API error: {str(e)}")
            
            # Fallback to standard translation if the optimized version fails
            logger.info(f"Falling back to standard translation")
            prompt = get_api_translation_prompt(source_lang, target_lang, text)
            translated_text = call_deepseek_api(prompt)
            
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
                    'timestamp': translation.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'fallback': True
                },
                'translations_remaining': user.translations_remaining
            })
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
            
        # Create prompt for summary
        prompt = get_summary_prompt(conversation_text)
        logger.info("Calling DeepSeek API for summary generation")
        
        try:
            summary = call_deepseek_api(prompt)
            
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
        except Exception as e:
            logger.error(f"DeepSeek API error: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Summary generation failed',
                'details': str(e)
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
        user_id = request.json.get('user_id') if request.json else request.form.get('user_id')
        message = data.get('message')
        logger.info(f"Generating AI Assistant response for user id: {user_id}")

        if not all([session_id, message]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400

        # Get conversation context
        translations = db.session.query(Translation).join(
            TranslationSession
        ).filter(
            TranslationSession.user_id == user_id
        ).order_by(
            Translation.timestamp
        ).all()

        context = [
            f"Original ({t.detected_language}): {t.original_text}\nTranslated: {t.translated_text}"
            for t in translations
        ]

        prompt = get_chat_prompt("\n".join(context), message)
        logger.info(f"Chat prompt prepared")

        try:
            response = call_deepseek_api(prompt)
            return jsonify({'success': True, 'response': response})
        except Exception as e:
            logger.error(f"Chat API error: {str(e)}")
            return jsonify({'success': False, 'error': f'Chat response generation failed: {str(e)}'}), 500

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

# Email verification functions
def generate_confirmation_token(email):
    return serializer.dumps(email, salt='email-confirm')

def generate_reset_token(email):
    return serializer.dumps(email, salt='password-reset')

def confirm_token(token, expiration=3600, salt='email-confirm'):
    try:
        email = serializer.loads(token, salt=salt, max_age=expiration)
        return email
    except:
        return False

def send_verification_email(email, token):
    # Create a message with proper headers
    msg = Message(
        'Healthcare Translator - Email Verification',
        recipients=[email],
        sender=('Healthcare Translator', app.config['MAIL_USERNAME'])
    )
    verification_url = url_for('verify_email', token=token, _external=True)
    msg.body = f'''Welcome to Healthcare Translator! 

Please click the link below to verify your email address:

{verification_url}

This link will expire in 1 hour.

If you didn't register for an account, please ignore this email.

Thank you,
Healthcare Translator Team
support@healthcaretranslator.com
'''

    # Add HTML content with better formatting
    msg.html = f'''
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <style>
            @media only screen and (max-width: 620px) {{
                table.body h1 {{
                    font-size: 28px !important;
                    margin-bottom: 10px !important;
                }}
                table.body p,
                table.body ul,
                table.body ol,
                table.body td,
                table.body span,
                table.body a {{
                    font-size: 16px !important;
                }}
                table.body .wrapper,
                table.body .article {{
                    padding: 10px !important;
                }}
                table.body .content {{
                    padding: 0 !important;
                }}
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 0;
                color: #333333;
                background-color: #f6f6f6;
                line-height: 1.5;
            }}
            .wrapper {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #ffffff;
                border-radius: 5px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .header {{
                padding: 20px;
                text-align: center;
                border-bottom: 1px solid #eeeeee;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                color: #333333;
            }}
            .content {{
                padding: 20px;
            }}
            .button {{
                display: inline-block;
                background-color: #4CAF50;
                color: white !important;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                margin: 20px 0;
            }}
            .footer {{
                font-size: 12px;
                color: #777777;
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eeeeee;
            }}
        </style>
    </head>
    <body>
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="body" width="100%">
            <tr>
                <td>&nbsp;</td>
                <td class="container">
                    <div class="wrapper">
                        <div class="header">
                            <h1>Healthcare Translator</h1>
                        </div>
                        <div class="content">
                            <h2>Welcome to Healthcare Translator!</h2>
                            <p>Thank you for registering with us. To complete your registration and verify your email address, please click the button below:</p>
                            <div style="text-align: center;">
                                <a href="{verification_url}" class="button">Verify Email Address</a>
                            </div>
                            <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
                            <p><a href="{verification_url}">{verification_url}</a></p>
                            <p>This link will expire in 1 hour.</p>
                            <p>If you didn't register for an account, please ignore this email.</p>
                            <p>Best regards,<br>Healthcare Translator Team</p>
                        </div>
                        <div class="footer">
                            <p>&copy; {datetime.now().year} Healthcare Translator. All rights reserved.</p>
                            <p>This is a one-time email sent to verify your account.</p>
                            <p><a href="mailto:support@healthcaretranslator.com">support@healthcaretranslator.com</a></p>
                        </div>
                    </div>
                </td>
                <td>&nbsp;</td>
            </tr>
        </table>
    </body>
    </html>
    '''
    
    # Add some headers to improve deliverability
    msg.extra_headers = {
        'List-Unsubscribe': f'<mailto:unsubscribe@healthcaretranslator.com?subject=Unsubscribe {email}>',
        'X-Priority': '1',  # High priority
        'Precedence': 'bulk',
        'Auto-Submitted': 'auto-generated'
    }
    
    try:
        mail.send(msg)
        logger.info(f"Verification email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        raise

def send_password_reset_email(email, token):
    # Create a message with proper headers
    msg = Message(
        'Healthcare Translator - Password Reset Request',
        recipients=[email],
        sender=('Healthcare Translator', app.config['MAIL_USERNAME'])
    )
    reset_url = url_for('reset_password', token=token, _external=True)
    msg.body = f'''You requested a password reset for your Healthcare Translator account.

Please click the link below to reset your password:

{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, please ignore this email and your password will remain unchanged.

Thank you,
Healthcare Translator Team
support@healthcaretranslator.com'''

    # Add HTML content with better formatting
    msg.html = f'''
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
        <style>
            @media only screen and (max-width: 620px) {{
                table.body h1 {{
                    font-size: 28px !important;
                    margin-bottom: 10px !important;
                }}
                table.body p,
                table.body ul,
                table.body ol,
                table.body td,
                table.body span,
                table.body a {{
                    font-size: 16px !important;
                }}
                table.body .wrapper,
                table.body .article {{
                    padding: 10px !important;
                }}
                table.body .content {{
                    padding: 0 !important;
                }}
            }}
            body {{
                font-family: Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 0;
                color: #333333;
                background-color: #f6f6f6;
                line-height: 1.5;
            }}
            .wrapper {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #ffffff;
                border-radius: 5px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            .header {{
                padding: 20px;
                text-align: center;
                border-bottom: 1px solid #eeeeee;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
                color: #333333;
            }}
            .content {{
                padding: 20px;
            }}
            .button {{
                display: inline-block;
                background-color: #4CAF50;
                color: white !important;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                margin: 20px 0;
            }}
            .footer {{
                font-size: 12px;
                color: #777777;
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eeeeee;
            }}
        </style>
    </head>
    <body>
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" class="body" width="100%">
            <tr>
                <td>&nbsp;</td>
                <td class="container">
                    <div class="wrapper">
                        <div class="header">
                            <h1>Healthcare Translator</h1>
                        </div>
                        <div class="content">
                            <h2>Password Reset Request</h2>
                            <p>We received a request to reset your password for your Healthcare Translator account. To create a new password, please click the button below:</p>
                            <div style="text-align: center;">
                                <a href="{reset_url}" class="button">Reset Your Password</a>
                            </div>
                            <p>If the button doesn't work, you can copy and paste this link into your browser:</p>
                            <p><a href="{reset_url}">{reset_url}</a></p>
                            <p>This link will expire in 1 hour.</p>
                            <p>If you didn't request a password reset, you can safely ignore this email - your password will remain unchanged.</p>
                            <p>Best regards,<br>Healthcare Translator Team</p>
                        </div>
                        <div class="footer">
                            <p>&copy; {datetime.now().year} Healthcare Translator. All rights reserved.</p>
                            <p>This email was sent in response to your password reset request.</p>
                            <p><a href="mailto:support@healthcaretranslator.com">support@healthcaretranslator.com</a></p>
                        </div>
                    </div>
                </td>
                <td>&nbsp;</td>
            </tr>
        </table>
    </body>
    </html>
    '''
    
    # Add some headers to improve deliverability
    msg.extra_headers = {
        'List-Unsubscribe': f'<mailto:unsubscribe@healthcaretranslator.com?subject=Unsubscribe {email}>',
        'X-Priority': '1',  # High priority
        'Precedence': 'bulk',
        'Auto-Submitted': 'auto-generated'
    }
    
    try:
        mail.send(msg)
        logger.info(f"Password reset email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        raise

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:
            flash('Email is required', 'error')
            return render_template('forgot_password.html')
            
        user = User.query.filter_by(email=email).first()
        
        # Always show success message even if email doesn't exist (security best practice)
        if user:
            token = generate_reset_token(email)
            try:
                send_password_reset_email(email, token)
                logger.info(f"Password reset email sent to {email}")
            except Exception as e:
                logger.error(f"Failed to send password reset email: {str(e)}")
                # Still show success to user for security reasons
        
        flash('If your email is registered, you will receive password reset instructions.', 'success')
        return redirect(url_for('login'))
        
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or not confirm_password:
            flash('Both password fields are required', 'error')
            return render_template('reset_password.html', token=token)
            
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('reset_password.html', token=token)
            
        email = confirm_token(token, salt='password-reset')
        if not email:
            flash('The password reset link is invalid or has expired.', 'error')
            return redirect(url_for('forgot_password'))
            
        user = User.query.filter_by(email=email).first()
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('login'))
            
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        
        flash('Your password has been updated! You can now log in with your new password.', 'success')
        return redirect(url_for('login'))
        
    # GET request handling
    email = confirm_token(token, salt='password-reset')
    if not email:
        flash('The password reset link is invalid or has expired.', 'error')
        return redirect(url_for('forgot_password'))
        
    return render_template('reset_password.html', token=token)

@app.route('/api/forgot-password', methods=['POST'])
def api_forgot_password():
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({
                'success': False,
                'error': 'Email is required'
            }), 400
            
        user = User.query.filter_by(email=email).first()
        
        # Always show success message even if email doesn't exist (security best practice)
        if user:
            token = generate_reset_token(email)
            try:
                send_password_reset_email(email, token)
                logger.info(f"Password reset email sent to {email}")
            except Exception as e:
                logger.error(f"Failed to send password reset email: {str(e)}")
                # Still return success for security reasons
        
        return jsonify({
            'success': True,
            'message': 'If your email is registered, you will receive password reset instructions'
        })
        
    except Exception as e:
        logger.error(f"API forgot password error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while processing your request'
        }), 500

@app.route('/api/reset-password', methods=['POST'])
def api_reset_password():
    try:
        data = request.get_json()
        token = data.get('token')
        password = data.get('password')
        confirm_password = data.get('confirm_password')
        
        if not all([token, password, confirm_password]):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400
            
        if password != confirm_password:
            return jsonify({
                'success': False,
                'error': 'Passwords do not match'
            }), 400
            
        email = confirm_token(token, salt='password-reset')
        if not email:
            return jsonify({
                'success': False,
                'error': 'The password reset link is invalid or has expired'
            }), 400
            
        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
            
        user.password_hash = generate_password_hash(password)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Your password has been updated successfully'
        })
        
    except Exception as e:
        logger.error(f"API reset password error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An error occurred while processing your request'
        }), 500

def setup_gmail_settings():
    """
    Print instructions for setting up Gmail for better email deliverability
    """
    print("\n========== Gmail Setup for Better Email Deliverability ==========")
    print("1. Make sure you've enabled 'Less secure app access' or created an App Password")
    print("2. Verify your Gmail account has completed the following:")
    print("   - Set up SPF records in your DNS if you have a custom domain")
    print("   - Add a profile picture to your Gmail account")
    print("   - Use a recognizable sender name ('Healthcare Translator')")
    print("   - Ensure your account is in good standing with Google")
    print("3. For the recipient:")
    print("   - Add sender email to contacts")
    print("   - Mark any received emails as 'Not Spam'")
    print("   - Create a filter to always allow emails from this sender")
    print("===================================================================\n")

# DeepSeek API function
def call_deepseek_api(prompt, use_cache=True):
    # For translation prompts, try to use cache
    if use_cache and "Task: Translate the following" in prompt:
        # Extract text to translate and languages from prompt
        text_match = re.search(r"Text to translate: (.+?)(?:\n|$)", prompt)
        from_match = re.search(r"from (\w+) to (\w+)", prompt)
        
        if text_match and from_match:
            text = text_match.group(1)
            source_lang = from_match.group(1)
            target_lang = from_match.group(2)
            
            # Check cache
            cache_key = get_cache_key(source_lang, target_lang, text)
            if cache_key in TRANSLATION_CACHE:
                logger.info(f"Using cached translation for text: {text[:30]}...")
                return TRANSLATION_CACHE[cache_key]
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "You are a medical translation assistant, providing accurate and contextually appropriate translations and summaries."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    try:
        logger.info(f"Calling DeepSeek API with model: {DEEPSEEK_MODEL}")
        response = requests.post(
            DEEPSEEK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        # Log response status and headers for debugging
        logger.info(f"DeepSeek API response status: {response.status_code}")
        logger.info(f"DeepSeek API response headers: {response.headers}")
        
        # Check if response is successful
        if response.status_code >= 400:
            error_message = f"DeepSeek API returned status code {response.status_code}"
            try:
                if response.headers.get('Content-Type', '').startswith('application/json'):
                    error_data = response.json()
                    if 'error' in error_data:
                        error_message += f": {error_data['error']}"
            except:
                error_message += f": {response.text[:200]}"
            logger.error(error_message)
            raise Exception(error_message)
            
        # Parse JSON response
        try:
            response_data = response.json()
        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            logger.error(f"Response content: {response.text[:500]}")
            raise Exception(f"Invalid JSON response from DeepSeek API: {str(e)}")
        
        # Check if response has expected format
        if "choices" not in response_data or not response_data["choices"]:
            logger.error(f"Unexpected response format: {response_data}")
            raise Exception("Unexpected response format from DeepSeek API")
        
        if "message" not in response_data["choices"][0]:
            logger.error(f"Missing message in response: {response_data}")
            raise Exception("Missing message in response from DeepSeek API")
            
        result = response_data["choices"][0]["message"]["content"].strip()
        
        # Store in cache if it's a translation
        if use_cache and "Task: Translate the following" in prompt and text_match and from_match:
            cache_key = get_cache_key(source_lang, target_lang, text)
            # Limit cache size
            if len(TRANSLATION_CACHE) >= MAX_CACHE_SIZE:
                # Remove a random key to prevent it from growing indefinitely
                TRANSLATION_CACHE.pop(next(iter(TRANSLATION_CACHE)))
            TRANSLATION_CACHE[cache_key] = result
            logger.info(f"Stored translation in cache, key: {cache_key[:10]}...")
        
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        raise Exception(f"Failed to connect to DeepSeek API: {str(e)}")
        
    except Exception as e:
        logger.error(f"Unknown error: {str(e)}")
        raise

# Add a function to validate API key at startup
def validate_deepseek_api_key():
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == 'sk-e04d98d1b66440f194203818f43443a6':
        logger.warning("⚠️ Using default DeepSeek API key. Set DEEPSEEK_API_KEY environment variable for production use.")
    logger.info(f"Using DeepSeek API URL: {DEEPSEEK_API_URL}")
    logger.info(f"Using DeepSeek model: {DEEPSEEK_MODEL}")

# Add a function for batch processing
async def process_translations_batch(texts, source_lang, target_lang):
    """Process multiple translations concurrently for faster responses."""
    async def translate_single(text):
        try:
            logger.info(f"Starting translation for text: {text[:30]}...")
            cache_key = get_cache_key(source_lang, target_lang, text)
            if cache_key in TRANSLATION_CACHE:
                logger.info(f"Cache hit for key: {cache_key[:10]}...")
                return text, TRANSLATION_CACHE[cache_key]
                
            target_lang_name = LANGUAGE_CODES.get(target_lang, target_lang)
            source_lang_name = LANGUAGE_CODES.get(source_lang, source_lang)
            prompt = f"Task: Translate the following text from {source_lang_name} to {target_lang_name}.\n"
            prompt += f"Text to translate: {text}\n"
            prompt += "Instructions:\n1. Maintain accuracy\n2. Preserve the original meaning\n3. Return only the translated text"
            
            # Make API call
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
            }
            
            payload = {
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a fast medical translation assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,  # Lower temperature for faster and more deterministic responses
                "max_tokens": 300  # Limit response length for faster processing
            }
            
            logger.info(f"Making async API call to DeepSeek for text: {text[:30]}...")
            
            # Use aiohttp for async API call
            async with aiohttp.ClientSession() as session:
                for attempt in range(MAX_RETRIES + 1):
                    try:
                        logger.info(f"Attempt {attempt+1}/{MAX_RETRIES+1} for translation")
                        async with session.post(
                            DEEPSEEK_API_URL,
                            headers=headers,
                            json=payload,
                            timeout=DEEPSEEK_API_TIMEOUT
                        ) as response:
                            logger.info(f"API Response status: {response.status}")
                            if response.status == 200:
                                data = await response.json()
                                logger.info("Successfully parsed response JSON")
                                
                                if "choices" not in data or not data["choices"] or "message" not in data["choices"][0]:
                                    logger.error(f"Invalid response format: {data}")
                                    if attempt < MAX_RETRIES:
                                        await asyncio.sleep(0.5)
                                        continue
                                    else:
                                        return text, f"Translation failed: Invalid API response format"
                                        
                                result = data["choices"][0]["message"]["content"].strip()
                                logger.info(f"Translation successful: {result[:30]}...")
                                TRANSLATION_CACHE[cache_key] = result
                                return text, result
                            else:
                                response_text = await response.text()
                                logger.error(f"API error: {response.status}, Response: {response_text[:200]}")
                                if attempt < MAX_RETRIES:
                                    logger.info(f"Retrying translation after error...")
                                    await asyncio.sleep(0.5)
                                    continue
                                else:
                                    return text, f"Translation failed: API error {response.status}"
                    except asyncio.TimeoutError:
                        logger.error(f"Timeout during API call (attempt {attempt+1})")
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(1)  # Longer delay after timeout
                            continue
                        else:
                            return text, "Translation failed: API timeout"
                    except Exception as e:
                        logger.error(f"Error during API call: {str(e)}")
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(0.5)
                            continue
                        else:
                            return text, f"Translation failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected error in translate_single: {str(e)}")
            return text, f"Translation failed: {str(e)}"
    
    try:
        # Process all translations concurrently
        logger.info(f"Starting batch translation for {len(texts)} texts")
        tasks = [translate_single(text) for text in texts]
        results = await asyncio.gather(*tasks)
        logger.info(f"Batch translation completed")
        return dict(results)
    except Exception as e:
        logger.error(f"Batch translation error: {str(e)}")
        # Fallback to returning empty results
        return {text: f"Translation failed: {str(e)}" for text in texts}
    
# Helper function to run async code from sync context
def run_async(coroutine):
    """Run an async function from a synchronous context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If no event loop exists, create one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coroutine)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        setup_gmail_settings()
        validate_deepseek_api_key()
    app.run(host='0.0.0.0', port=8800, debug=True)
