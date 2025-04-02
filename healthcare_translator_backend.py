import requests
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

FLASK_API_URL = "https://app.advanceailab.com"
API_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

class HealthcareTranslatorBackend:
    def __init__(self):
        self.current_user = None
        self.current_session = None
        self.translations_enabled = True

    def login(self, email, unique_user_id, password):
        """Handle login request"""
        try:
            response = requests.post(
                f"{FLASK_API_URL}/api/login",
                headers=API_HEADERS,
                json={
                    "email": email,
                    "unique_user_id": unique_user_id,
                    "password": password
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.current_user = data['user']
                    self.current_session = data['session_id']
                    return True, data
            
            return False, response.json()
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return False, {"error": str(e)}

    def translate_text(self, text, source_lang, target_lang):
        """Handle translation request"""
        try:
            response = requests.post(
                f"{FLASK_API_URL}/api/translate",
                headers=API_HEADERS,
                json={
                    "text": text,
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "session_id": self.current_session,
                    "user_id": self.current_user['id']
                }
            )
            
            return response.status_code == 200, response.json()
            
        except Exception as e:
            logger.error(f"Translation error: {str(e)}")
            return False, {"error": str(e)}

    def get_chat_response(self, message):
        """Handle chat request"""
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
            
            return response.status_code == 200, response.json()
            
        except Exception as e:
            logger.error(f"Chat error: {str(e)}")
            return False, {"error": str(e)}

    def generate_summary(self):
        """Handle summary generation request"""
        try:
            if not self.current_user or not self.current_session:
                return False, {"error": "No active session"}
            
            response = requests.post(
                f"{FLASK_API_URL}/api/generate_summary",
                headers=API_HEADERS,
                json={
                    "session_id": self.current_session,
                    "user_id": self.current_user['id']
                },
                timeout=30  # Increased timeout for summary generation
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('summary'):
                    return True, data
                return False, {"error": "No summary generated"}
            
            return False, {"error": f"Failed to generate summary: {response.status_code}"}
            
        except requests.Timeout:
            logger.error("Summary generation timed out")
            return False, {"error": "Summary generation timed out"}
        except Exception as e:
            logger.error(f"Summary error: {str(e)}")
            return False, {"error": str(e)}

    def get_translations(self):
        """Get previous translations"""
        try:
            if not self.current_user or not self.current_session:
                return False, {"error": "No active session"}
            
            response = requests.get(
                f"{FLASK_API_URL}/api/translations",
                headers=API_HEADERS,
                params={
                    "user_id": self.current_user['id'],
                    "session_id": self.current_session
                }
            )
            
            if response.status_code == 200:
                return True, response.json()
            
            return False, response.json()
            
        except Exception as e:
            logger.error(f"Error getting translations: {str(e)}")
            return False, {"error": str(e)}

    def toggle_translations(self, enabled: bool):
        """Toggle translations on/off"""
        self.translations_enabled = enabled
        return True, {"success": True}

    def register(self, email, password, first_name, last_name):
        """Handle registration request"""
        try:
            # Log request details
            logger.info(f"Sending registration request for email: {email}")
            
            # Prepare request data
            request_data = {
                "email": email,
                "password": password,
                "first_name": first_name,
                "last_name": last_name
            }
            logger.info(f"Request data: {request_data}")
            
            try:
                response = requests.post(
                    f"{FLASK_API_URL}/api/register",
                    headers=API_HEADERS,
                    json=request_data,
                    timeout=10
                )
                
                # Log response details
                logger.info(f"Registration response status: {response.status_code}")
                logger.info(f"Registration response content: {response.text}")
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get('success') and data.get('unique_user_id'):
                            logger.info(f"Registration successful. Unique ID: {data['unique_user_id']}")
                            return True, data
                        else:
                            logger.error("Registration response missing success or unique_user_id")
                            return False, {"error": "Invalid response format"}
                    except ValueError as e:
                        logger.error(f"Failed to parse JSON response: {e}")
                        return False, {"error": "Invalid response format"}
                else:
                    error_msg = f"Registration failed with status {response.status_code}"
                    try:
                        error_data = response.json()
                        if error_data.get('error'):
                            error_msg = error_data['error']
                    except:
                        pass
                    logger.error(error_msg)
                    return False, {"error": error_msg}
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {str(e)}")
                return False, {"error": f"Connection error: {str(e)}"}
            
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return False, {"error": str(e)}

    def get_user_translations(self, user_id):
        """Get user's translation history from database"""
        try:
            with self.get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Get last 20 translations for the user
                    query = """
                    SELECT original_text, translated_text, timestamp 
                    FROM translations 
                    WHERE user_id = %s 
                    ORDER BY timestamp DESC 
                    LIMIT 20
                    """
                    cursor.execute(query, (user_id,))
                    rows = cursor.fetchall()
                    
                    translations = []
                    for row in rows:
                        translations.append({
                            'original_text': row[0],
                            'translated_text': row[1],
                            'timestamp': row[2]
                        })
                    
                    return True, {'translations': translations}
                    
        except Exception as e:
            logger.error(f"Error fetching user translations: {str(e)}")
            return False, {'error': str(e)}

    # ... other backend methods ... 